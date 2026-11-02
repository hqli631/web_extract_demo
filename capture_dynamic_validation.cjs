// Save one rendered, allowlisted page into the isolated blind-validation batch.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const root = path.resolve(__dirname);
const config = JSON.parse(fs.readFileSync(path.join(root, 'config/collection_blind.json'), 'utf8'));
const target = config.targets.find(item => item.name === process.argv[2]);
if (!target) throw new Error('Pass an allowlisted target name from config/collection_blind.json');
if (target.seeds.length !== 1 || target.max_pages !== 1) throw new Error('Capture expects one explicitly allowlisted URL');
const batch = path.resolve(root, process.argv[3] || 'validation_blind');
if (!batch.startsWith(root + path.sep)) throw new Error('Batch path must stay inside the project directory');

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe'
  });
  try {
    const page = await browser.newPage();
    await page.goto(target.seeds[0], { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForFunction(() => document.body && document.body.innerText.trim().length > 500, { timeout: 25000 });
    await page.waitForTimeout(2500);
    const details = await page.evaluate(() => ({ title: document.title, text: document.body.innerText, url: location.href }));
    const finalUrl = new URL(details.url);
    if (finalUrl.protocol !== 'https:' || !target.allowed_domains.includes(finalUrl.hostname)) {
      throw new Error('Rendered page redirected outside the HTTPS host allowlist');
    }
    if (!details.title || details.text.length < 500) throw new Error('Rendered page did not expose article text');

    const html = await page.content();
    const bytes = Buffer.from(html, 'utf8');
    const name = 'rendered_' + crypto.createHash('sha256').update(target.seeds[0]).digest('hex').slice(0, 16) + '.html';
    const samples = path.join(batch, 'samples');
    const reports = path.join(batch, 'reports');
    fs.mkdirSync(samples, { recursive: true });
    fs.mkdirSync(reports, { recursive: true });
    fs.writeFileSync(path.join(samples, name), bytes);

    const manifestPath = path.join(reports, 'collection_manifest.json');
    const manifest = fs.existsSync(manifestPath) ? JSON.parse(fs.readFileSync(manifestPath, 'utf8')) : [];
    const digest = value => crypto.createHash('sha256').update(value).digest('hex');
    const entry = {
      file: name,
      url: details.url,
      seed_url: target.seeds[0],
      domain: new URL(details.url).hostname,
      content_hash: digest(details.text),
      snapshot: digest(bytes),
      fetched_at: new Date().toISOString(),
      mode: 'rendered_browser',
      text_chars: details.text.length
    };
    fs.writeFileSync(manifestPath, JSON.stringify([...manifest.filter(item => item.file !== name), entry], null, 2));
    console.log(JSON.stringify({ ...entry, title: details.title }, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
