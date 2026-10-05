const { chromium } = require('playwright'); const fs=require('fs');
const css=`*{box-sizing:border-box;margin:0}body{width:1280px;height:720px;background:#0f1a17;font-family:-apple-system,"SF Pro Display","Segoe UI",Roboto,sans-serif;color:#e8efec;overflow:hidden;position:relative}
.cap{position:absolute;left:0;right:0;bottom:0;padding:22px 48px 26px;background:linear-gradient(transparent,rgba(5,12,10,.92) 30%);font-size:30px;font-weight:650;letter-spacing:-.01em}
.cap small{display:block;font-size:19px;font-weight:450;color:#9fb3ac;margin-top:6px}
.shot{position:absolute;left:50%;top:34px;transform:translateX(-50%);width:1040px;border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.5);border:1px solid #23312c}
.center{display:flex;flex-direction:column;justify-content:center;height:100%;padding:0 110px}
.logo{width:76px;height:76px;border-radius:18px;background:#0f766e;color:#fff;font-size:46px;font-weight:800;display:grid;place-items:center;margin-bottom:30px}
h1{font-size:64px;letter-spacing:-.02em;line-height:1.05}h2{font-size:44px;letter-spacing:-.02em;line-height:1.15;margin-bottom:22px}
p{font-size:26px;color:#a9bcb5;line-height:1.45;margin-top:14px}.mono{font-family:ui-monospace,Menlo,monospace;font-size:20px;color:#7fe0cf}
.tg{width:640px;margin:0 auto;background:#17212b;border-radius:16px;padding:26px 30px;font-size:24px;line-height:1.5;color:#e9eef2}
.tg .who{color:#6ab3f3;font-weight:600;margin-bottom:6px}.tg a{color:#6ab3f3;text-decoration:none}.row{display:flex;gap:16px;align-items:baseline}`;
const S=[
 ['00_title',`<div class="center"><div class="logo">T</div><h1>Tally Invoices</h1><p>Payment links for USDC and EURC on Arc mainnet.<br>One transaction. The money goes straight to the merchant.</p></div>`],
 ['00b_why',`<div class="center"><h2>Why Arc</h2><p>On most chains a buyer who owes 25 USDC also needs a second coin for gas.</p><p>On Arc, USDC is the gas. The buyer needs nothing but the USDC they owe.</p></div>`],
 ['s1',`<img class="shot" src="01_create.png"><div class="cap">1. The merchant creates an invoice in USDC or EURC<small>tally-invoices.vercel.app · no sign-up, no custody</small></div>`],
 ['s2',`<img class="shot" src="02_waiting.png"><div class="cap">2. The client opens the link<small>Amount, purpose and status are visible without a wallet</small></div>`],
 ['s3',`<div class="center"><h2>3. The client pays from their wallet</h2><p>EURC invoice #3, live on Arc mainnet:</p><p class="mono">approve EURC &nbsp;0x3da63eee…f816bc</p><p class="mono">pay(3) &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0x8ee6569a…1877f5</p><p>The contract forwards 0.50 EURC to the merchant in the same call and keeps nothing.<br>USDC invoices are a single transaction, no approve.</p></div>`],
 ['s4',`<img class="shot" src="03_paid.png"><div class="cap">4. Paid. Payer, time and transaction are public<small>Anyone can verify it, wallet or not</small></div>`],
 ['s5',`<img class="shot" src="04_explorer.png"><div class="cap">5. Verifiable on Arc mainnet<small>arcexplorer.org · fee for the payment: 0.002138 USDC</small></div>`],
 ['s6',`<div class="center"><h2>6. The merchant gets pinged in Telegram</h2><div class="tg"><div class="who">Tally Invoices</div>✅ <b>Invoice #3 paid</b><br>0.50 EURC from <span style="font-family:ui-monospace,Menlo,monospace;color:#6ab3f3">0xCC8E…78c8</span><br><a>transaction</a> · <a>invoice</a></div><p style="text-align:center">@TallyInvoicesBot reads contract events. It never holds keys.</p></div>`],
 ['s7',`<div class="center"><h2>Built and running</h2><p>3 invoices paid on Arc mainnet: 2 in USDC, 1 in EURC</p><p>Contract source verified on Sourcify (exact match)</p><p>13 Foundry tests, including re-entrancy and a 256-run fuzz</p><p>Next: partial payments, due dates, pay a EURC invoice with USDC</p></div>`],
 ['s8',`<div class="center"><div class="logo">T</div><h2>Tally Invoices</h2><p class="mono">tally-invoices.vercel.app</p><p class="mono">github.com/DmitriyTopka/tally-invoices</p><p class="mono">t.me/TallyInvoicesBot</p><p class="mono">contract 0xF8c0cD6eD0a111d64661cB090498921753A565cf</p></div>`],
];
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1.5});
for(const [n,h] of S){fs.writeFileSync(`${n}.html`,`<!doctype html><meta charset=utf-8><style>${css}</style><body>${h}</body>`);await p.goto('file://'+__dirname+`/${n}.html`);await p.waitForTimeout(300);await p.screenshot({path:`f_${n}.png`});}
await b.close();console.log('frames',S.length)})();
