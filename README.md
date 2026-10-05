# Tally Invoices

Payment links for USDC and EURC on Arc mainnet.

A merchant creates an invoice and sends a link. The buyer opens it, pays from their wallet in one transaction, and the money goes straight to the merchant. The contract never holds funds. A Telegram bot tells the merchant "paid" a moment later.

- **Live app:** https://tally-invoices.vercel.app
- **Paid invoice you can open without a wallet:** https://tally-invoices.vercel.app/?i=1
- **Contract on Arc mainnet:** [`0xF8c0cD6eD0a111d64661cB090498921753A565cf`](https://www.arcexplorer.org/address/0xF8c0cD6eD0a111d64661cB090498921753A565cf)
- **Telegram notifier:** [@TallyInvoicesBot](https://t.me/TallyInvoicesBot)

## Why Arc

- **One coin is enough.** USDC is Arc's gas token, so a buyer who holds 25 USDC can pay a 25 USDC invoice. No second token to buy for fees, which is where most first-time payers give up on other chains.
- **One transaction, no approve.** A USDC invoice is paid with the native value of the call. The buyer signs once.
- **Fast enough for a checkout.** Invoice #1 was created and paid six seconds apart, and the merchant's balance moved in the same block as the payment.
- **Euro invoices.** EURC is supported for clients who think in euros. It is an ERC-20 on Arc, so it uses approve and pay.

## Proof it runs

| step | transaction |
|---|---|
| deploy | [`0xc053…ca97`](https://www.arcexplorer.org/tx/0xc053dec1752133a462b814b077421c93c8df04f99ac8f34a6bf46542cf06ca97) |
| invoice #1 created, 0.50 USDC | [`0x90f5…37af`](https://www.arcexplorer.org/tx/0x90f52d7e2ca0fd3a53f3ef6c634b7d316f9de78a71d8fe4a4bba76a71f7a37af) |
| invoice #1 paid by a different wallet | [`0xf7da…3919`](https://www.arcexplorer.org/tx/0xf7daedf6339f51c8f9d3b8b14272e3692705ec58859ee4352fc98503332f3919) |

After the payment the merchant was up exactly 0.50 USDC and the contract balance was 0. Deploying cost 0.034 USDC; paying the invoice cost the buyer about 0.0014 USDC in gas.

## How it works

```
merchant ──createInvoice(token, amount, memo)──▶ TallyInvoices ──InvoiceCreated──▶ bot
buyer    ──pay(id) {value: amount}─────────────▶ TallyInvoices ──USDC──▶ merchant
                                                               └─InvoicePaid──▶ bot ──▶ merchant's Telegram
```

- `src/TallyInvoices.sol` - the contract. Invoice states are Open, Paid and Cancelled. State changes before money moves, so a re-entrant call finds the invoice already paid. Token addresses without code are rejected, so an invoice can't be "paid" by a call that moves nothing.
- `web/` - a single static page (viem, no build step) plus a read-only RPC proxy for regions where the public endpoint is blocked. The invoice page shows amount, status, payer and the payment transaction to anyone, wallet or not.
- `bot/tally_bot.py` - the merchant sends `/watch <address>`, the bot follows the contract's events and messages them. It only reads the chain.

## Run it yourself

```bash
forge test                      # 13 tests, incl. re-entrancy and a 256-run fuzz
python3 tools/deploy.py         # deploy with your own key (DEPLOYER_KEY_FILE)
TELEGRAM_BOT_TOKEN=... TALLY_CONTRACT=0x... python3 bot/tally_bot.py
```

## Next

- Partial payments and invoices with a due date.
- Accept USDC for a EURC invoice with conversion in the same transaction.
- A small checkout widget a shop can drop into its site.

MIT licensed.
