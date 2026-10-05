const { chromium } = require('playwright');
(async () => {
  const [url, out, waitFor] = process.argv.slice(2);
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 2, colorScheme: 'light' });
  await p.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  if (waitFor) await p.waitForFunction(w => document.body.innerText.includes(w), waitFor, { timeout: 60000 });
  await p.waitForTimeout(1500);
  await p.screenshot({ path: out });
  await b.close(); console.log('ok', out);
})();
