"""Minimal JSON-RPC helper for Arc mainnet. Set ARC_RPC to override the endpoint."""
import json, os, urllib.request
URL = os.environ.get("ARC_RPC", "https://rpc.mainnet.arc.io")
def rpc(method, params):
    req = urllib.request.Request(URL, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                 headers={"content-type": "application/json", "user-agent": "tally-invoices"})
    r = json.load(urllib.request.urlopen(req, timeout=30))
    if "error" in r: raise RuntimeError(r["error"])
    return r["result"]
