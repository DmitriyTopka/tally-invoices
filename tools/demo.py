"""Live mainnet check: merchant creates a USDC invoice, a separate buyer wallet pays it."""
import json, os, sys, time, os
sys.path.insert(0, "tools")
try:
    from arc_rpc import rpc  # local relay, not in the repo
except ImportError:
    from rpc import rpc
from eth_account import Account
from web3 import Web3
W = os.path.expanduser(os.environ.get("WALLET_DIR", "~/arc-grant-wallet")) + "/"
dep = json.load(open("deployment.json")); C = Web3.to_checksum_address(dep["address"])
merchant = Account.from_key(open(W + "deployer.key").read().strip())
if not os.path.exists(W + "buyer.key"):
    b = Account.create(); open(W + "buyer.key", "w").write(b.key.hex()); os.chmod(W + "buyer.key", 0o600)
buyer = Account.from_key(open(W + "buyer.key").read().strip())
w3 = Web3()
abi = json.load(open("out/TallyInvoices.sol/TallyInvoices.json"))["abi"]
ct = w3.eth.contract(address=C, abi=abi)
def send(acct, to, data="0x", value=0):
    nonce = int(rpc("eth_getTransactionCount", [acct.address, "pending"]), 16)
    gp = int(rpc("eth_gasPrice", []), 16)
    tx = {"from": acct.address, "to": to, "data": data, "value": hex(value)}
    gas = int(int(rpc("eth_estimateGas", [tx]), 16) * 1.3)
    raw = acct.sign_transaction({"chainId": 5042, "nonce": nonce, "gas": gas, "gasPrice": gp, "to": to, "data": data, "value": value}).raw_transaction.hex()
    h = rpc("eth_sendRawTransaction", ["0x" + raw.removeprefix("0x")])
    for _ in range(30):
        r = rpc("eth_getTransactionReceipt", [h])
        if r: return h, r
        time.sleep(1)
    raise RuntimeError("no receipt " + h)
bal = lambda a: int(rpc("eth_getBalance", [a, "latest"]), 16) / 1e18
step = sys.argv[1]
if step == "fund":
    h, r = send(merchant, buyer.address, value=int(1.0e18)); print("fund buyer", buyer.address, h, r["status"])
elif step == "create":
    amt = int(float(sys.argv[2]) * 1e18); memo = sys.argv[3]
    data = ct.encode_abi("createInvoice", args=["0x0000000000000000000000000000000000000000", amt, memo])
    h, r = send(merchant, C, data); log = ct.events.InvoiceCreated().process_log({**r["logs"][0], "topics": [bytes.fromhex(t[2:]) for t in r["logs"][0]["topics"]], "data": bytes.fromhex(r["logs"][0]["data"][2:]), "blockNumber": int(r["blockNumber"],16), "transactionHash": bytes.fromhex(h[2:]), "logIndex": 0, "transactionIndex": 0, "blockHash": bytes.fromhex(r["blockHash"][2:]), "address": C})
    print("created invoice", log["args"]["id"], h, r["status"])
elif step == "pay":
    inv_id = int(sys.argv[2]); amt = int(float(sys.argv[3]) * 1e18)
    m0 = bal(merchant.address)
    h, r = send(buyer, C, ct.encode_abi("pay", args=[inv_id]), value=amt)
    print("paid", inv_id, h, r["status"], "merchant +", round(bal(merchant.address) - m0, 6), "contract balance", bal(C))
print("merchant", bal(merchant.address), "buyer", bal(buyer.address))
