const { chromium } = require(process.env.QR_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const net = require('node:net');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { randomBytes } = require('node:crypto');

const root = path.resolve(__dirname, '..');
const output = path.resolve(process.argv[2] || path.join(root, 'evidence', 'completion'));
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'qr-completion-'));
const username = 'synthetic-staff';
const password = randomBytes(24).toString('hex');
const authorization = 'Basic ' + Buffer.from(username + ':' + password).toString('base64');
const passed = [];
const errors = [];
let server;
let browser;
let serverLog = '';

async function reservePort() {
  const socket = net.createServer();
  await new Promise((resolve, reject) => { socket.once('error', reject); socket.listen(0, '127.0.0.1', resolve); });
  const port = socket.address().port;
  await new Promise(resolve => socket.close(resolve));
  return port;
}

async function startServer(port) {
  server = spawn(process.env.QR_PYTHON || 'python', [
    '-m', 'flask', '--app', path.join(root, 'app.py'), 'run',
    '--host', '127.0.0.1', '--port', String(port), '--no-reload',
  ], {
    cwd: temporary,
    windowsHide: true,
    env: { ...process.env, QR_DATABASE_PATH: path.join(temporary, 'synthetic.db'),
      QR_ADMIN_USER: username, QR_ADMIN_PASSWORD: password,
      FLASK_DEBUG: '0', PYTHONIOENCODING: 'utf-8', PYTHONUNBUFFERED: '1' },
  });
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Isolated Flask startup timed out')), 45000);
    const record = data => {
      serverLog += data.toString();
      if (serverLog.includes('Running on http://127.0.0.1:' + port)) { clearTimeout(timer); resolve(); }
    };
    server.stdout.on('data', record);
    server.stderr.on('data', record);
    server.once('error', error => { clearTimeout(timer); reject(error); });
    server.once('exit', code => { clearTimeout(timer); reject(new Error('Isolated Flask exited: ' + code + '\n' + serverLog)); });
  });
}

async function waitReload(page, action) {
  await Promise.all([page.waitForNavigation(), action()]);
}

async function stopServer() {
  if (!server || server.exitCode !== null) return;
  if (process.platform === 'win32') {
    const stop = spawn('taskkill', ['/PID', String(server.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
    await new Promise((resolve, reject) => {
      stop.once('error', reject);
      stop.once('exit', code => code === 0 ? resolve() : reject(new Error('Test server tree cleanup failed: ' + code)));
    });
    return;
  }
  await new Promise(resolve => { server.once('exit', resolve); server.kill(); });
}

async function main() {
  fs.mkdirSync(output, { recursive: true });
  const port = await reservePort();
  const base = 'http://127.0.0.1:' + port;
  await startServer(port);
  browser = await chromium.launch({ channel: process.env.QR_BROWSER_CHANNEL || 'msedge', headless: process.env.QR_HEADLESS === '1' });
  const customer = await browser.newContext({ hasTouch: true, viewport: { width: 390, height: 844 } });
  const staff = await browser.newContext({ hasTouch: true, httpCredentials: { username, password }, viewport: { width: 820, height: 1180 } });
  for (const context of [customer, staff]) {
    await context.route('**/*', route => route.request().url().startsWith(base)
      ? route.continue() : route.fulfill({ status: 200, contentType: 'application/javascript', body: 'window.kakaoAdfit=[];window.PartnersCoupang={G:function(){}};' }));
  }
  const page = await customer.newPage();
  const admin = await staff.newPage();
  for (const surface of [page, admin]) surface.on('pageerror', error => errors.push(error.message));
  for (const endpoint of ['/admin', '/master-order', '/delete-order', '/delete-all-orders']) {
    const response = endpoint === '/admin' ? await customer.request.get(base + endpoint)
      : await customer.request.post(base + endpoint, { data: {} });
    assert.equal(response.status(), 401);
  }
  passed.push('Anonymous access denied on all four administrator routes (401)');
  await admin.goto(base + '/admin');
  const token = await admin.locator('meta[name="csrf-token"]').getAttribute('content');
  assert.ok(token);
  assert.equal((await staff.request.post(base + '/delete-all-orders', { headers: { Authorization: authorization } })).status(), 403);
  assert.equal((await staff.request.post(base + '/delete-all-orders', { headers: { Authorization: authorization, 'X-CSRF-Token': 'forged' } })).status(), 403);
  passed.push('Authenticated mutations denied without a genuine page token (403)');
  assert.equal((await customer.request.post(base + '/order?seat=1', { data: [] })).status(), 400);
  assert.equal((await customer.request.post(base + '/order?seat=1', { data: { drink: 'unknown' } })).status(), 400);
  passed.push('Malformed payload and unknown drink denied (400)');

  for (const width of [320, 360, 390, 430]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto(base + '/order?seat=7');
    assert.equal(await page.locator('.current-seat').innerText(), '7');
    assert.equal(await page.locator('input[name=drink]').count(), 14);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    if (width === 390) await page.screenshot({ path: path.join(output, 'order-390.png'), fullPage: true });
    passed.push('Phone ' + width + ': seat continuity, 14 menu choices, no horizontal overflow');
  }
  await page.locator('input[value="사과주스(Only ICE)"]').locator('..').tap();
  let postCount = 0;
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/order?seat=7', async route => {
    if (route.request().method() !== 'POST') return route.continue();
    postCount++;
    await gate;
    return route.continue();
  });
  await page.locator('#order-submit').tap();
  await page.waitForFunction(() => document.querySelector('#order-submit').disabled);
  await page.evaluate(() => document.querySelector('#order-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  assert.equal(postCount, 1);
  release();
  await page.waitForURL('**/order-complete?seat=7');
  await page.unroute('**/order?seat=7');
  passed.push('Customer touch order succeeded with repeated-submit lock');
  await admin.reload();
  assert.equal(await admin.locator('#seat-detail-7 .detail-order').count(), 1);
  await admin.locator('#master-toggle').tap();
  await admin.locator('#master-seat').selectOption('8');
  await admin.locator('#master-drink').selectOption('아메리카노(HOT)');
  await waitReload(admin, () => admin.locator('#master-form button').tap());
  assert.equal(await admin.locator('#seat-detail-8 .detail-order').count(), 1);
  passed.push('Authenticated UI manual order succeeded with CSRF header');
  admin.on('dialog', dialog => dialog.accept());
  await waitReload(admin, () => admin.locator('#seat-detail-8 .delete-one').tap());
  assert.equal(await admin.locator('#seat-detail-8 .detail-order').count(), 0);
  passed.push('Authenticated UI single deletion updated actual stored list');

  const fixtures = [['12', '캐모마일(HOT)'], ['11', '페퍼민트(COLD)'], ['10', '루이보스(HOT)'], ['10', '얼그레이(COLD)'], ['9', '핫초코(Only HOT)'], ['1', '아메리카노(COLD)'], ['1', '오렌지주스(Only ICE)'], ['2', '페퍼민트(HOT)'], ['3', '루이보스(COLD)'], ['4', '얼그레이(HOT)'], ['4', '핫초코(Only HOT)'], ['5', '사과주스(Only ICE)'], ['6', '아이스티(Only ICE)'], ['8', '캐모마일(COLD)']];
  for (const [seat, drink] of fixtures) assert.equal((await customer.request.post(base + '/order?seat=' + seat, { data: { drink } })).status(), 200);
  for (const [width, height] of [[768, 1024], [820, 1180], [1024, 768], [1180, 820]]) {
    await admin.setViewportSize({ width, height });
    await admin.goto(base + '/admin');
    assert.equal(await admin.locator('[data-overview-seat]').count(), 12);
    assert.equal(await admin.locator('.map-order').count(), 15);
    assert.equal(await admin.locator('.detail-order').count(), 15);
    assert.equal(await admin.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await admin.screenshot({ path: path.join(output, 'admin-' + width + 'x' + height + '.png'), fullPage: false });
    passed.push('Tablet ' + width + 'x' + height + ': 12 seats, all 15 stored orders, no horizontal overflow');
  }
  for (const mode of ['http', 'network']) {
    await page.goto(base + '/order?seat=7');
    await page.route('**/order?seat=7', route => route.request().method() !== 'POST' ? route.continue()
      : mode === 'http' ? route.fulfill({ status: 503, body: 'unavailable' }) : route.abort());
    await page.locator('#order-submit').tap();
    await page.locator('#order-error').waitFor({ state: 'visible' });
    assert.equal(page.url(), base + '/order?seat=7');
    assert.equal(await page.locator('#order-submit').isEnabled(), true);
    await page.unroute('**/order?seat=7');
    passed.push('Customer ' + mode + ' failure remained on order page with visible confirmation warning');
  }
  await admin.goto(base + '/admin');
  await waitReload(admin, () => admin.locator('#delete-all').tap());
  assert.equal(await admin.locator('.map-order').count(), 0);
  assert.equal(await admin.locator('.all-orders-empty').isVisible(), true);
  passed.push('Authenticated UI delete-all produced verified empty list');
  await admin.locator('#master-toggle').tap();
  await admin.route('**/master-order', route => route.fulfill({ status: 503, body: 'unavailable' }));
  await admin.locator('#master-form button').tap();
  await admin.locator('#admin-error').waitFor({ state: 'visible' });
  assert.equal(await admin.locator('#master-form button').isEnabled(), true);
  passed.push('Staff storage failure displayed an error without false completion');
  assert.deepEqual(errors, []);
  passed.push('No browser JavaScript errors; external advertising requests stubbed');
  fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify({ passed, errors, fixtures, syntheticDatabase: true, productionTouched: false }, null, 2));
  console.log(passed.join('\n'));
}

main().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => {
  if (browser) await browser.close();
  await stopServer();
  fs.mkdirSync(output, { recursive: true });
  fs.writeFileSync(path.join(output, 'synthetic-server.log'), serverLog);
  if (path.dirname(temporary) === path.resolve(os.tmpdir()) && path.basename(temporary).startsWith('qr-completion-')) {
    fs.rmSync(temporary, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 });
  }
});
