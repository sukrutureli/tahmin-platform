import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.mjs';
const env = {PANEL_PASSWORD: 'Synthetic-password-123456', SESSION_SECRET: 'synthetic-session-secret-of-32-chars-minimum', GITHUB_TOKEN: 'synthetic-github-secret'};
const origin = 'https://example.workers.dev';
let ip = 0;
const get = (path, cookie, method = 'GET') => new Request(origin + path, {method, headers: cookie ? {Cookie: cookie} : {}});
const post = (password, options = {}) => new Request(origin + '/login', {method: 'POST', headers: {
  Origin: origin, 'Content-Type': 'application/x-www-form-urlencoded', 'CF-Connecting-IP': 'test-' + ++ip, ...options
}, body: new URLSearchParams({password}).toString()});
async function cookie() {
  const response = await worker.fetch(post(env.PANEL_PASSWORD), env);
  assert.equal(response.status, 303);
  return response.headers.get('Set-Cookie').split(';')[0];
}
test('incomplete configuration fails closed without echoing secrets', async () => {
  const response = await worker.fetch(get('/futbol/'), {...env, SESSION_SECRET: ''});
  assert.equal(response.status, 503);
  assert.ok(!(await response.text()).includes(env.PANEL_PASSWORD));
});
test('anonymous HTML and JSON requests cannot call GitHub', async () => {
  const old = globalThis.fetch;
  globalThis.fetch = () => { throw Error('Unexpected upstream access'); };
  try {
    for (const path of ['/', '/futbol/', '/basketbol/', '/futbol/data/Match-2026-10-18.json']) {
      const response = await worker.fetch(get(path), env);
      assert.equal(response.status, 303); assert.equal(response.headers.get('Location'), '/login');
    }
  } finally { globalThis.fetch = old; }
});
test('login page contains no report data or credentials', async () => {
  const response = await worker.fetch(get('/login'), env), html = await response.text();
  assert.equal(response.status, 200); assert.ok(html.includes('type="password"'));
  for (const value of Object.values(env)) assert.ok(!html.includes(value));
});
test('wrong password does not create a session', async () => {
  const response = await worker.fetch(post('wrong'), env);
  assert.equal(response.headers.get('Set-Cookie'), null);
  assert.equal(response.headers.get('Location'), '/login?error=1');
});
test('correct password creates secure cookie and opens dashboard', async () => {
  const response = await worker.fetch(post(env.PANEL_PASSWORD), env);
  const header = response.headers.get('Set-Cookie');
  for (const option of ['Secure', 'HttpOnly', 'SameSite=Strict', 'Path=/']) assert.ok(header.includes(option));
  const home = await worker.fetch(get('/', header.split(';')[0]), env);
  assert.equal(home.status, 200);assert.ok((await home.text()).includes('Basketbol'));
});
test('tampered cookie and password/session rotation revoke access', async () => {
  const session = await cookie();
  const parts = session.split('.');parts[1] = String(Number(parts[1]) + 1);
  assert.equal((await worker.fetch(get('/', parts.join('.')), env)).status, 303);
  for (const override of [{PANEL_PASSWORD: 'new-synthetic-password'}, {SESSION_SECRET: 'rotated-session-secret-of-at-least-32-characters'}]) {
    assert.equal((await worker.fetch(get('/', session), {...env, ...override})).status, 303);
  }
});
test('expired cookie rejected', async () => {
  const realNow = Date.now; let session;
  try { Date.now = () => realNow() - 8 * 86400 * 1000;session = await cookie(); }
  finally { Date.now = realNow; }
  assert.equal((await worker.fetch(get('/', session), env)).status, 303);
});
test('cross-origin login and logout rejected', async () => {
  assert.equal((await worker.fetch(post(env.PANEL_PASSWORD, {Origin: 'https://evil.example'}), env)).status, 403);
  const response = await worker.fetch(new Request(origin + '/logout', {method: 'POST', headers: {Origin: 'https://evil.example'}}), env);
  assert.equal(response.status, 403);
});
test('authenticated fixed report proxy sends token upstream only', async () => {
  const session = await cookie(), old = globalThis.fetch; let called = false;
  globalThis.fetch = async (url, options) => {
    called = true;
    assert.equal(url, 'https://api.github.com/repos/sukrutureli/fathertahmin/contents/futbol/futbol.html?ref=main');
    assert.equal(options.headers.Authorization, 'Bearer ' + env.GITHUB_TOKEN);
    assert.equal(options.redirect, 'manual');
    return new Response('<html>Synthetic report</html>');
  };
  try {
    const response = await worker.fetch(get('/futbol/', session), env);
    assert.equal(response.status, 200);assert.ok(called);
    assert.equal(await response.text(), '<html>Synthetic report</html>');
    assert.ok(!JSON.stringify([...response.headers]).includes(env.GITHUB_TOKEN));
    assert.equal(response.headers.get('Cache-Control'), 'private, no-store');
  } finally { globalThis.fetch = old; }
});
test('arbitrary repo, secret files and query proxy targets rejected', async () => {
  const session = await cookie();
  for (const path of ['/other/secret.json', '/futbol/.env', '/futbol/data/../.env', '/futbol/?url=https://evil.example']) {
    assert.equal((await worker.fetch(get(path, session), env)).status, 404);
  }
});
test('upstream error or redirect cannot expose bodies or token', async () => {
  const session = await cookie(), old = globalThis.fetch;
  try {
    for (const status of [302, 403, 404, 429, 500]) {
      globalThis.fetch = async () => new Response('upstream-secret-body', {status, headers: {Location: 'https://evil.example'}});
      const response = await worker.fetch(get('/basketbol/', session), env);
      assert.equal(response.status, 502);assert.ok(!(await response.text()).includes('upstream-secret-body'));
    }
  } finally { globalThis.fetch = old; }
});
test('logout expires cookie and responses disallow storage', async () => {
  const response = await worker.fetch(new Request(origin + '/logout', {method: 'POST', headers: {Origin: origin}}), env);
  assert.equal(response.status, 303);assert.ok(response.headers.get('Set-Cookie').includes('Max-Age=0'));
  assert.equal(response.headers.get('Cache-Control'), 'private, no-store');
});
test('same-IP rapid attempts are throttled', async () => {
  let response;
  for (let i = 0; i < 11; i++) response = await worker.fetch(post('wrong', {'CF-Connecting-IP': 'rate-limit-test'}), env);
  assert.equal(response.status, 429);
});
