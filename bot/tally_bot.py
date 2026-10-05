"""Tally Invoices notifier for Telegram.

A merchant sends /watch <address>. The bot follows the TallyInvoices contract
on Arc mainnet and messages the merchant when one of their invoices is created
or paid. It only reads the chain; it never holds keys.
"""
import json
import logging
import os
import sqlite3
import threading
import time

import requests
from web3 import Web3

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
RPC = os.environ.get("ARC_RPC", "https://rpc.mainnet.arc.io")
CONTRACT = Web3.to_checksum_address(os.environ["TALLY_CONTRACT"])
START_BLOCK = int(os.environ.get("TALLY_START_BLOCK", "0"))
SITE = os.environ.get("TALLY_SITE", "https://tally-invoices.vercel.app")
EXPLORER = "https://www.arcexplorer.org"
DB = os.environ.get("TALLY_DB", os.path.join(os.path.dirname(__file__), "tally_bot.db"))
POLL_SECONDS = 3
MAX_RANGE = 2000

NATIVE = "0x0000000000000000000000000000000000000000"
EURC = "0xbEf5f6d51CB62b58e6A8f77868681825C6fe21c1".lower()

ABI = json.loads("""[
 {"type":"event","name":"InvoiceCreated","inputs":[{"name":"id","type":"uint256","indexed":true},{"name":"merchant","type":"address","indexed":true},{"name":"token","type":"address","indexed":false},{"name":"amount","type":"uint256","indexed":false},{"name":"memo","type":"string","indexed":false}]},
 {"type":"event","name":"InvoicePaid","inputs":[{"name":"id","type":"uint256","indexed":true},{"name":"payer","type":"address","indexed":true},{"name":"merchant","type":"address","indexed":true},{"name":"token","type":"address","indexed":false},{"name":"amount","type":"uint256","indexed":false}]}
]""")

log = logging.getLogger("tally")
w3 = Web3(Web3.HTTPProvider(RPC, request_kwargs={"timeout": 20}))
contract = w3.eth.contract(address=CONTRACT, abi=ABI)
TG = f"https://api.telegram.org/bot{TOKEN}"


def db():
    con = sqlite3.connect(DB)
    con.execute("create table if not exists watch(chat_id integer, merchant text, primary key(chat_id, merchant))")
    con.execute("create table if not exists state(k text primary key, v text)")
    return con


def send(chat_id, text):
    try:
        requests.post(f"{TG}/sendMessage", json={
            "chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True,
        }, timeout=20)
    except requests.RequestException as e:
        log.warning("send failed: %s", e)


def fmt_amount(token, amount):
    token = token.lower()
    if token == NATIVE:
        return f"{amount / 10**18:,.2f} USDC"
    if token == EURC:
        return f"{amount / 10**6:,.2f} EURC"
    return f"{amount} units of {token}"


def short(a):
    return a[:6] + "…" + a[-4:]


# ---- commands ----------------------------------------------------------------
HELP = (
    "<b>Tally Invoices</b> - payment links for USDC and EURC on Arc.\n\n"
    f"1. Create an invoice at {SITE}\n"
    "2. Send me <code>/watch 0xYourWallet</code>\n"
    "3. I message you the second a client pays.\n\n"
    "/list - addresses you watch\n/unwatch 0x... - stop"
)


def handle(msg):
    chat_id = msg["chat"]["id"]
    parts = (msg.get("text") or "").split()
    if not parts:
        return
    cmd = parts[0].split("@")[0].lower()
    con = db()
    if cmd in ("/start", "/help"):
        send(chat_id, HELP)
    elif cmd in ("/watch", "/unwatch"):
        if len(parts) < 2 or not Web3.is_address(parts[1]):
            send(chat_id, f"Send it like this: <code>{cmd} 0xYourWallet</code>")
            return
        addr = Web3.to_checksum_address(parts[1])
        if cmd == "/watch":
            con.execute("insert or ignore into watch values(?,?)", (chat_id, addr.lower()))
            send(chat_id, f"Watching {short(addr)}. I will tell you when its invoices are paid.")
        else:
            con.execute("delete from watch where chat_id=? and merchant=?", (chat_id, addr.lower()))
            send(chat_id, f"Stopped watching {short(addr)}.")
        con.commit()
    elif cmd == "/list":
        rows = con.execute("select merchant from watch where chat_id=?", (chat_id,)).fetchall()
        send(chat_id, "\n".join(short(Web3.to_checksum_address(r[0])) for r in rows) or "Nothing yet. Use /watch 0x...")
    con.close()


def telegram_loop():
    offset = 0
    while True:
        try:
            r = requests.get(f"{TG}/getUpdates", params={"timeout": 50, "offset": offset}, timeout=60).json()
            for u in r.get("result", []):
                offset = u["update_id"] + 1
                if "message" in u:
                    handle(u["message"])
        except Exception as e:  # keep the bot alive on network errors
            log.warning("telegram loop: %s", e)
            time.sleep(5)


# ---- chain watcher ---------------------------------------------------------------
def notify(event):
    a = event["args"]
    merchant = a["merchant"].lower()
    con = db()
    chats = [r[0] for r in con.execute("select chat_id from watch where merchant=?", (merchant,))]
    con.close()
    if not chats:
        return
    inv_id = a["id"]
    tx = event["transactionHash"].to_0x_hex()
    page = f"{SITE}/?i={inv_id}"
    if event["event"] == "InvoicePaid":
        text = (f"✅ <b>Invoice #{inv_id} paid</b>\n{fmt_amount(a['token'], a['amount'])} from "
                f"<code>{short(a['payer'])}</code>\n<a href=\"{EXPLORER}/tx/{tx}\">transaction</a> · <a href=\"{page}\">invoice</a>")
    else:
        text = (f"🧾 Invoice #{inv_id} created: {fmt_amount(a['token'], a['amount'])}\n"
                f"{a['memo']}\nShare: {page}")
    for chat_id in chats:
        send(chat_id, text)


def chain_loop():
    con = db()
    row = con.execute("select v from state where k='last_block'").fetchone()
    con.close()
    last = int(row[0]) if row else max(START_BLOCK, w3.eth.block_number - 1)
    while True:
        try:
            head = w3.eth.block_number
            if head > last:
                to = min(head, last + MAX_RANGE)
                events = []
                for ev in (contract.events.InvoiceCreated, contract.events.InvoicePaid):
                    events += ev.get_logs(from_block=last + 1, to_block=to)
                events.sort(key=lambda e: (e["blockNumber"], e["logIndex"]))
                for e in events:
                    notify(e)
                last = to
                con = db()
                con.execute("insert or replace into state values('last_block', ?)", (str(last),))
                con.commit()
                con.close()
        except Exception as e:
            log.warning("chain loop: %s", e)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    threading.Thread(target=chain_loop, daemon=True).start()
    telegram_loop()
