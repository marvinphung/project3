import { chromium } from '../frontend/node_modules/@playwright/test/index.mjs';

const baseUrl = process.env.UI_BASE_URL || 'http://192.168.1.4:8443';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1365, height: 900 } });

const consoleErrors = [];
const failedRequests = [];
const apiResponses = [];

page.on('console', (msg) => {
  if (['error', 'warning'].includes(msg.type())) {
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
  const links = await page.locator('a').evaluateAll((nodes) =>
    nodes.slice(0, 20).map((node) => ({
      text: node.textContent?.trim().replace(/\s+/g, ' ').slice(0, 80),
      href: node.getAttribute('href'),
    })),
  );
  const buttons = await page.locator('button').evaluateAll((nodes) =>
    nodes.map((node) => ({
      text: node.textContent?.trim().replace(/\s+/g, ' ').slice(0, 80),
      disabled: node.hasAttribute('disabled'),
    })),
  );
  return {
    label,
    url: page.url(),
    h1: await visibleText('h1'),
    emptyStates: text
      .split('\n')
      .filter((line) =>
        /Không thể|Không tìm thấy|Chưa có|Đang tải|Nhập từ khóa|API đang không khả dụng/.test(line),
      ),
    topEntityCards: await page.locator('a[href^="/entity/"]').count(),
    directoryCards: await page.locator('a[href^="/clb/"], a[href^="/cau-thu/"], a[href^="/hlv/"]').count(),
    articleRows: await page.locator('a[href^="/bai-viet/"]').count(),
    links,
    buttons,
  };
}

const results = [];

async function gotoAndCapture(path, label) {
  await page.goto(`${baseUrl}${path}`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(500);
  results.push(await snapshot(label));
}

await gotoAndCapture('/', 'home');

const firstEntityHref = await page.locator('a[href^="/entity/"]').first().getAttribute('href').catch(() => null);
if (firstEntityHref) {
  await gotoAndCapture(firstEntityHref, 'home first top entity detail');
}

await gotoAndCapture('/tim-kiem', 'search empty');
await page.locator('input#public-search').fill('Arsenal');
await page.locator('button[type="submit"]').click();
await page.waitForLoadState('networkidle');
await page.waitForTimeout(500);
results.push(await snapshot('search Arsenal'));

const firstSearchHref = await page.locator('a[href^="/entity/"]').first().getAttribute('href').catch(() => null);
if (firstSearchHref) {
  await gotoAndCapture(firstSearchHref, 'search first entity detail');
}

for (const [path, label] of [
  ['/tin-moi', 'latest news'],
  ['/clb', 'clubs directory'],
  ['/cau-thu', 'players directory'],
  ['/hlv', 'coaches directory'],
]) {
  await gotoAndCapture(path, label);
}

console.log(JSON.stringify({ baseUrl, results, apiResponses, failedRequests, consoleErrors }, null, 2));

await browser.close();
