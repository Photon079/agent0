import puppeteer from 'puppeteer';

(async () => {
  const browser = await puppeteer.launch({ headless: "new" });
  const page = await browser.newPage();
  
  page.on('console', msg => console.log('BROWSER_LOG:', msg.text()));
  page.on('pageerror', error => console.log('BROWSER_ERROR:', error.message));
  
  await page.goto('http://localhost:5173');
  
  // Wait a bit
  await new Promise(r => setTimeout(r, 2000));
  
  // Type username
  await page.type('input', 'torvalds');
  
  // Click button
  const buttons = await page.$$('button');
  for (const btn of buttons) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text.includes('Ingest Profile')) {
          await btn.click();
      }
  }
  
  // Wait for ingestion
  await new Promise(r => setTimeout(r, 10000));
  
  await browser.close();
})();
