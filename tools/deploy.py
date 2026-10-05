"""Deploy TallyInvoices to Arc mainnet. Signs locally, broadcasts via the relay."""
import json, os, sys, time
sys.path.insert(0, "tools")
try:
    from arc_rpc import rpc  # local relay, not in the repo
except ImportError:
    from rpc import rpc
from eth_account import Account
KEY = open(os.path.expanduser(os.environ.get("DEPLOYER_KEY_FILE", "~/arc-grant-wallet/deployer.key"))).read().strip()
acct = Account.from_key(KEY)
art = json.load(open("out/TallyInvoices.sol/TallyInvoices.json"))
code = art["bytecode"]["object"]
nonce = int(rpc("eth_getTransactionCount", [acct.address, "pending"]), 16)
gas_price = int(rpc("eth_gasPrice", []), 16)
gas = int(int(rpc("eth_estimateGas", [{"from": acct.address, "data": code}]), 16) * 1.2)
print(f"deployer {acct.address} nonce {nonce} gas {gas} price {gas_price} cost ~{gas*gas_price/1e18:.4f} USDC")
tx = {"chainId": 5042, "nonce": nonce, "gas": gas, "gasPrice": gas_price, "data": code, "value": 0}
raw = acct.sign_transaction(tx).raw_transaction.hex()
h = rpc("eth_sendRawTransaction", ["0x" + raw.removeprefix("0x")])
print("tx", h)
for _ in range(30):
    r = rpc("eth_getTransactionReceipt", [h])
    if r:
        print("status", r["status"], "contract", r["contractAddress"], "block", int(r["blockNumber"], 16))
        json.dump({"address": r["contractAddress"], "block": int(r["blockNumber"], 16), "tx": h}, open("deployment.json", "w"), indent=2)
        break
    time.sleep(2)
