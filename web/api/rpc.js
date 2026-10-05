// Read-only JSON-RPC proxy to Arc mainnet, used by the page as a fallback
// where the public endpoint is unreachable. Only read methods pass through.
const UPSTREAM = "https://rpc.mainnet.arc.io";
const ALLOWED = new Set([
  "eth_chainId", "eth_blockNumber", "eth_call", "eth_getLogs", "eth_getBalance",
  "eth_getTransactionReceipt", "eth_getTransactionByHash", "eth_getBlockByNumber",
  "eth_getCode", "net_version",
]);

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  const body = req.body;
  const calls = Array.isArray(body) ? body : [body];
  if (calls.length > 20 || calls.some(c => !c || !ALLOWED.has(c.method))) {
    return res.status(400).json({ error: "method not allowed" });
  }
  const r = await fetch(UPSTREAM, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  res.status(r.status).setHeader("content-type", "application/json");
  return res.send(await r.text());
}
