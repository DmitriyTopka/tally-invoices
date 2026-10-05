import { createPublicClient, createWalletClient, custom, http, fallback, parseUnits, formatUnits, decodeEventLog, defineChain, getAddress } from "viem";

// ---- config ---------------------------------------------------------------
const CONTRACT = "0xF8c0cD6eD0a111d64661cB090498921753A565cf";
const DEPLOY_BLOCK = 24371534n;
const EXPLORER = "https://www.arcexplorer.org";
const NATIVE = "0x0000000000000000000000000000000000000000";
const EURC = "0xbEf5f6d51CB62b58e6A8f77868681825C6fe21c1";
const TOKENS = { USDC: { address: NATIVE, decimals: 18, label: "USDC" }, EURC: { address: EURC, decimals: 6, label: "EURC" } };
const tokenByAddr = a => a.toLowerCase() === NATIVE ? TOKENS.USDC : a.toLowerCase() === EURC.toLowerCase() ? TOKENS.EURC : { address: a, decimals: 18, label: "token" };

const arc = defineChain({
  id: 5042, name: "Arc",
  nativeCurrency: { name: "USDC", symbol: "USDC", decimals: 18 },
  rpcUrls: { default: { http: ["https://rpc.mainnet.arc.io"] } },
  blockExplorers: { default: { name: "Arc Explorer", url: EXPLORER } },
});

const ABI = [
  { type: "function", name: "createInvoice", stateMutability: "nonpayable", inputs: [{ name: "token", type: "address" }, { name: "amount", type: "uint256" }, { name: "memo", type: "string" }], outputs: [{ type: "uint256" }] },
  { type: "function", name: "pay", stateMutability: "payable", inputs: [{ name: "id", type: "uint256" }], outputs: [] },
  { type: "function", name: "getInvoice", stateMutability: "view", inputs: [{ name: "id", type: "uint256" }], outputs: [{ type: "tuple", components: [
    { name: "merchant", type: "address" }, { name: "token", type: "address" }, { name: "amount", type: "uint256" }, { name: "status", type: "uint8" },
    { name: "payer", type: "address" }, { name: "createdAt", type: "uint64" }, { name: "paidAt", type: "uint64" }, { name: "memo", type: "string" }] }] },
  { type: "function", name: "invoiceCount", stateMutability: "view", inputs: [], outputs: [{ type: "uint256" }] },
  { type: "event", name: "InvoiceCreated", inputs: [{ name: "id", type: "uint256", indexed: true }, { name: "merchant", type: "address", indexed: true }, { name: "token", type: "address" }, { name: "amount", type: "uint256" }, { name: "memo", type: "string" }] },
  { type: "event", name: "InvoicePaid", inputs: [{ name: "id", type: "uint256", indexed: true }, { name: "payer", type: "address", indexed: true }, { name: "merchant", type: "address", indexed: true }, { name: "token", type: "address" }, { name: "amount", type: "uint256" }] },
];
const ERC20 = [
  { type: "function", name: "allowance", stateMutability: "view", inputs: [{ type: "address" }, { type: "address" }], outputs: [{ type: "uint256" }] },
  { type: "function", name: "approve", stateMutability: "nonpayable", inputs: [{ type: "address" }, { type: "uint256" }], outputs: [{ type: "bool" }] },
];

// Our read-only proxy first (works from every region); the public endpoint is the fallback.
const pub = createPublicClient({ chain: arc, transport: fallback([http("/api/rpc"), http("https://rpc.mainnet.arc.io")]) });

// ---- helpers --------------------------------------------------------------
const $ = id => document.getElementById(id);
const short = a => a.slice(0, 6) + "…" + a.slice(-4);
const fmt = (v, t) => Number(formatUnits(v, t.decimals)).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 6 });
const when = s => s ? new Date(Number(s) * 1000).toLocaleString() : "";
const say = (el, text, cls = "") => { el.textContent = text; el.className = "msg " + cls; };
const link = (path, text) => `<a href="${EXPLORER}/${path}" target="_blank" rel="noopener">${text}</a>`;

async function wallet() {
  if (!window.ethereum) throw new Error("No browser wallet found. Install MetaMask or Rabby.");
  const [account] = await window.ethereum.request({ method: "eth_requestAccounts" });
  try {
    await window.ethereum.request({ method: "wallet_switchEthereumChain", params: [{ chainId: "0x13b2" }] });
  } catch (e) {
    if (e.code !== 4902) throw e;
    await window.ethereum.request({ method: "wallet_addEthereumChain", params: [{ chainId: "0x13b2", chainName: "Arc", nativeCurrency: { name: "USDC", symbol: "USDC", decimals: 18 }, rpcUrls: ["https://rpc.mainnet.arc.io"], blockExplorerUrls: [EXPLORER] }] });
  }
  return { account: getAddress(account), client: createWalletClient({ account: getAddress(account), chain: arc, transport: custom(window.ethereum) }) };
}

// ---- invoice view -----------------------------------------------------------
async function showInvoice(id) {
  $("view").classList.remove("hidden");
  const inv = await pub.readContract({ address: CONTRACT, abi: ABI, functionName: "getInvoice", args: [id] });
  if (inv.status === 0) { $("v-amount").textContent = "Invoice not found"; return; }
  const t = tokenByAddr(inv.token);
  $("v-amount").textContent = `${fmt(inv.amount, t)} ${t.label}`;
  $("v-memo").textContent = inv.memo;
  const status = ["", "Waiting for payment", "Paid", "Cancelled"][inv.status];
  $("v-status").innerHTML = `<span class="badge ${["", "b-open", "b-paid", "b-cancel"][inv.status]}">${status}</span>`;
  document.title = `${fmt(inv.amount, t)} ${t.label} · Tally`;

  const rows = [
    ["Invoice", `#${id}`],
    ["Pay to", link(`address/${inv.merchant}`, short(inv.merchant))],
    ["Created", when(inv.createdAt)],
  ];
  if (inv.status === 2) {
    rows.push(["Paid by", link(`address/${inv.payer}`, short(inv.payer))], ["Paid at", when(inv.paidAt)]);
    const logs = await pub.getContractEvents({ address: CONTRACT, abi: ABI, eventName: "InvoicePaid", args: { id }, fromBlock: DEPLOY_BLOCK }).catch(() => []);
    if (logs[0]) rows.push(["Transaction", link(`tx/${logs[0].transactionHash}`, short(logs[0].transactionHash))]);
  }
  rows.push(["Contract", link(`address/${CONTRACT}`, short(CONTRACT))]);
  $("v-details").innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");

  if (inv.status !== 1) return;
  const btn = $("v-pay"); btn.classList.remove("hidden");
  btn.onclick = async () => {
    btn.disabled = true;
    try {
      const { account, client } = await wallet();
      if (inv.token !== NATIVE) {
        const allowed = await pub.readContract({ address: inv.token, abi: ERC20, functionName: "allowance", args: [account, CONTRACT] });
        if (allowed < inv.amount) {
          say($("v-msg"), `Step 1 of 2: allow ${t.label} for this invoice…`);
          const h = await client.writeContract({ address: inv.token, abi: ERC20, functionName: "approve", args: [CONTRACT, inv.amount] });
          await pub.waitForTransactionReceipt({ hash: h });
        }
      }
      say($("v-msg"), "Confirm the payment in your wallet…");
      const hash = await client.writeContract({ address: CONTRACT, abi: ABI, functionName: "pay", args: [id], value: inv.token === NATIVE ? inv.amount : 0n });
      say($("v-msg"), "Sent, waiting for the block…");
      const r = await pub.waitForTransactionReceipt({ hash });
      if (r.status !== "success") throw new Error("Transaction reverted");
      say($("v-msg"), "Paid. Thank you!", "ok");
      setTimeout(() => location.reload(), 1200);
    } catch (e) { say($("v-msg"), e.shortMessage || e.message, "err"); btn.disabled = false; }
  };
}

// ---- create view ------------------------------------------------------------
function showCreate() {
  $("create").classList.remove("hidden");
  $("c-go").onclick = async () => {
    const btn = $("c-go"); const msg = $("c-msg");
    const t = TOKENS[$("c-token").value];
    const raw = $("c-amount").value.trim().replace(",", ".");
    if (!/^\d+(\.\d{1,6})?$/.test(raw) || Number(raw) <= 0) return say(msg, "Enter an amount like 25 or 25.50", "err");
    btn.disabled = true;
    try {
      const { client } = await wallet();
      say(msg, "Confirm in your wallet…");
      const hash = await client.writeContract({ address: CONTRACT, abi: ABI, functionName: "createInvoice", args: [t.address, parseUnits(raw, t.decimals), $("c-memo").value.slice(0, 140)] });
      say(msg, "Creating…");
      const r = await pub.waitForTransactionReceipt({ hash });
      const ev = r.logs.map(l => { try { return decodeEventLog({ abi: ABI, ...l }); } catch { return null; } }).find(e => e && e.eventName === "InvoiceCreated");
      const url = `${location.origin}${location.pathname}?i=${ev.args.id}`;
      $("c-link").value = url; $("c-result").classList.remove("hidden");
      say(msg, `Invoice #${ev.args.id} is live. Send this link to your client.`, "ok");
    } catch (e) { say(msg, e.shortMessage || e.message, "err"); }
    btn.disabled = false;
  };
  $("c-copy").onclick = () => navigator.clipboard.writeText($("c-link").value).then(() => say($("c-msg"), "Link copied", "ok"));
}

// ---- boot ---------------------------------------------------------------------
const id = new URLSearchParams(location.search).get("i");
if (id && /^\d+$/.test(id)) showInvoice(BigInt(id)).catch(e => { $("v-amount").textContent = "Could not load invoice"; say($("v-msg"), e.shortMessage || e.message, "err"); });
else showCreate();
pub.readContract({ address: CONTRACT, abi: ABI, functionName: "invoiceCount" })
  .then(n => { $("foot").innerHTML = `${n} invoices created · contract ${link(`address/${CONTRACT}`, short(CONTRACT))} · <a href="https://github.com/DmitriyTopka/tally-invoices">source</a>`; })
  .catch(() => {});
