"""Live EURC invoice on Arc mainnet: buyer swaps a little USDC to EURC via KyberSwap,
merchant creates a EURC invoice, buyer approves and pays it. Run step by step."""
import json, os, sys, time, urllib.request
sys.path.insert(0, "tools")
try:
    from arc_rpc import rpc  # local relay, not in the repo
except ImportError:
    from rpc import rpc
from eth_account import Account
from web3 import Web3
W = os.path.expanduser(os.environ.get("WALLET_DIR", "~/arc-grant-wallet")) + "/"
USDC = "0x3600000000000000000000000000000000000000"
EURC = "0xbEf5f6d51CB62b58e6A8f77868681825C6fe21c1"
KYBER = "https://aggregator-api.kyberswap.com/arc/api/v1"
dep = json.load(open("deployment.json")); C = Web3.to_checksum_address(dep["address"])
merchant = Account.from_key(open(W + "deployer.key").read().strip())
buyer = Account.from_key(open(W + "buyer.key").read().strip())
w3 = Web3()
abi = json.load(open("out/TallyInvoices.sol/TallyInvoices.json"))["abi"]
ct = w3.eth.contract(address=C, abi=abi)
ERC20 = [{"name": "approve", "type": "function", "inputs": [{"type": "address"}, {"type": "uint256"}], "outputs": [{"type": "bool"}], "stateMutability": "nonpayable"},
         {"name": "balanceOf", "type": "function", "inputs": [{"type": "address"}], "outputs": [{"type": "uint256"}], "stateMutability": "view"}]
erc = lambda a: w3.eth.contract(address=Web3.to_checksum_address(a), abi=ERC20)

def http(url, body=None):
    hdr = {"User-Agent": "tally-invoices", "Accept": "application/json", "Content-Type": "application/json", "x-client-id": "tally-invoices"}
    req = urllib.request.Request(url, json.dumps(body).encode() if body else None, hdr)
    return json.load(urllib.request.urlopen(req, timeout=45))

def send(acct, to, data="0x", value=0, gas=None):
    nonce = int(rpc("eth_getTransactionCount", [acct.address, "pending"]), 16)
    gp = int(rpc("eth_gasPrice", []), 16)
    if not gas:
        gas = int(int(rpc("eth_estimateGas", [{"from": acct.address, "to": to, "data": data, "value": hex(value)}]), 16) * 1.3)
    raw = acct.sign_transaction({"chainId": 5042, "nonce": nonce, "gas": gas, "gasPrice": gp, "to": Web3.to_checksum_address(to), "data": data, "value": value}).raw_transaction.hex()
    h = rpc("eth_sendRawTransaction", ["0x" + raw.removeprefix("0x")])
    for _ in range(40):
        r = rpc("eth_getTransactionReceipt", [h])
        if r:
            if r["status"] != "0x1": raise RuntimeError("reverted " + h)
            return h, r
        time.sleep(1)
    raise RuntimeError("no receipt " + h)

def bal(token, who):
    return int(rpc("eth_call", [{"to": token, "data": erc(token).encode_abi("balanceOf", args=[who])}, "latest"]), 16) / 1e6

step = sys.argv[1]
if step == "fund":
    h, _ = send(merchant, buyer.address, value=int(1e18)); print("funded buyer 1 USDC", h)
elif step == "swap":
    amt = int(float(sys.argv[2]) * 1e6)
    r = http(f"{KYBER}/routes?tokenIn={USDC}&tokenOut={EURC}&amountIn={amt}")
    built = http(f"{KYBER}/route/build", {"routeSummary": r["data"]["routeSummary"], "sender": buyer.address, "recipient": buyer.address, "slippageTolerance": 100})["data"]
    router = built["routerAddress"]
    h1, _ = send(buyer, USDC, erc(USDC).encode_abi("approve", args=[Web3.to_checksum_address(router), amt])); print("approve USDC", h1)
    h2, _ = send(buyer, router, built["data"], gas=int(int(built.get("gas") or 400000) * 1.5)); print("swap", h2)
elif step == "create":
    amt = int(float(sys.argv[2]) * 1e6)
    h, r = send(merchant, C, ct.encode_abi("createInvoice", args=[Web3.to_checksum_address(EURC), amt, sys.argv[3]]))
    print("created invoice", int(r["logs"][0]["topics"][1], 16), h)
elif step == "pay":
    inv = int(sys.argv[2]); amt = int(float(sys.argv[3]) * 1e6)
    m0 = bal(EURC, merchant.address)
    h1, _ = send(buyer, EURC, erc(EURC).encode_abi("approve", args=[C, amt])); print("approve EURC", h1)
    h2, _ = send(buyer, C, ct.encode_abi("pay", args=[inv])); print("paid", inv, h2, "merchant EURC +", round(bal(EURC, merchant.address) - m0, 6))
print("buyer USDC", int(rpc("eth_getBalance", [buyer.address, "latest"]), 16) / 1e18, "EURC", bal(EURC, buyer.address), "| merchant EURC", bal(EURC, merchant.address))
