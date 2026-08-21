import { chromium } from '../frontend/node_modules/@playwright/test/index.mjs';

const baseUrl = process.env.UI_BASE_URL || 'http://127.0.0.1:8443';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1365, height: 900 } });

const consoleErrors = [];
const failedRequests = [];
const apiResponses = [];

page.on('console', (msg) => {
  if (['error'].includes(msg.type())) {
    consoleErrors.push({ type: msg.type(), text: msg.text() });
  }
});

page.on('requestfailed', (request) => {
  failedRequests.push({
    url: request.url(),
    method: request.method(),
    failure: request.failure()?.errorText,
  });
});

page.on('response', (response) => {
  const url = response.url();
  if (url.includes('/api/')) {
    apiResponses.push({ url, status: response.status() });
  }
});

async function visibleText(selector) {
  const locator = page.locator(selector);
  if ((await locator.count()) === 0) return null;
  return (await locator.first().innerText()).trim();
}

async function snapshot(label) {
  const text = await page.locator('body').innerText();
  const topEntityCards = await page.locator('a[href^="/entity/"]').count();
  const directoryCards = await page.locator('a[href^="/clb/"], a[href^="/cau-thu/"], a[href^="/hlv/"]').count();
  const articleRows = await page.locator('a[href^="/bai-viet/"]').count();
  return {
    label,
    url: page.url(),
    h1: await visibleText('h1'),
    emptyStates: text
      .split('\n')
      .filter((line) =>
        /Không thể|Không tìm thấy|API đang không khả dụng/.test(line),
      ),
    topEntityCards,
    directoryCards,
    articleRows,
  };
}

const results = [];

async function gotoAndCapture(path, label) {
  await page.goto(`${baseUrl}${path}`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(500);
  const snap = await snapshot(label);
  results.push(snap);
  return snap;
}

console.log(`Starting UI smoke verification on ${baseUrl}...`);

// 1. Home
const homeSnap = await gotoAndCapture('/', 'home');
if (homeSnap.topEntityCards === 0) {
  throw new Error('Home page did not render any top entity cards');
}

// 2. Entity timeline from home
const firstEntityHref = await page.locator('a[href^="/entity/"]').first().getAttribute('href').catch(() => null);
if (firstEntityHref) {
  const entitySnap = await gotoAndCapture(firstEntityHref, 'top entity detail');
  if (entitySnap.emptyStates.length > 0) {
    console.warn('Entity detail warning:', entitySnap.emptyStates);
  }
}

// 3. Search
await gotoAndCapture('/tim-kiem', 'search empty');
await page.locator('input#public-search').fill('Arsenal');
await page.locator('button[type="submit"]').click();
await page.waitForLoadState('networkidle');
await page.waitForTimeout(500);
const searchSnap = await snapshot('search Arsenal');
results.push(searchSnap);

const firstSearchHref = await page.locator('a[href^="/entity/"]').first().getAttribute('href').catch(() => null);
if (firstSearchHref) {
  await gotoAndCapture(firstSearchHref, 'search entity detail');
}

// 4. Latest News
const newsSnap = await gotoAndCapture('/tin-moi', 'latest news');
if (newsSnap.articleRows === 0) {
  throw new Error('Latest news page did not render any article rows');
}

// 5. Article Detail
const firstArticleHref = await page.locator('a[href^="/bai-viet/"]').first().getAttribute('href').catch(() => null);
if (firstArticleHref) {
  const artSnap = await gotoAndCapture(firstArticleHref, 'article detail');
  if (artSnap.emptyStates.length > 0) {
    throw new Error(`Article detail failed with empty states: ${artSnap.emptyStates.join(', ')}`);
  }
}

// 6. Directories
for (const [path, label] of [
  ['/clb', 'clubs directory'],
  ['/cau-thu', 'players directory'],
  ['/hlv', 'coaches directory'],
]) {
  await gotoAndCapture(path, label);
}

// 7. Footer static pages
for (const [path, label] of [
  ['/gioi-thieu', 'about page'],
  ['/nguon-tin', 'sources page'],
  ['/dieu-khoan', 'terms page'],
  ['/lien-he', 'contact page'],
]) {
  const staticSnap = await gotoAndCapture(path, label);
  if (staticSnap.emptyStates.includes('Không tìm thấy trang')) {
    throw new Error(`Static page ${path} returned 404`);
  }
}

await browser.close();

const fatalErrors = consoleErrors.filter(e => !e.text.includes('favicon'));
const failedApi = apiResponses.filter(r => r.status >= 500);

console.log(JSON.stringify({
  summary: 'Smoke test passed successfully!',
  totalSteps: results.length,
  failedApiCount: failedApi.length,
  consoleErrorCount: fatalErrors.length,
  results: results.map(r => ({ label: r.label, url: r.url, h1: r.h1, emptyStates: r.emptyStates }))
}, null, 2));

if (failedApi.length > 0 || fatalErrors.length > 0) {
  console.error('Smoke audit detected critical failures:', { failedApi, fatalErrors });
  process.exit(1);
}
