import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.mjs';

test('new report requires login before reading private dated files',async()=>{
  const old=globalThis.fetch;globalThis.fetch=async()=>{throw Error('unexpected upstream')};
  try{assert.equal((await worker.fetch(get('/futbol-yeni/'),env)).status,303)}finally{globalThis.fetch=old;}
});
test('new report reads its exact dated snapshot and keeps new-system day navigation',async()=>{
  const old=globalThis.fetch,oldNow=Date.now;const calls=[];
  try{
    Date.now=()=>Date.parse('2026-10-18T08:00:00Z');const session=await cookie();
    globalThis.fetch=async(url)=>{calls.push(url);return url.includes('new-report-manifest')?Response.json({targetDate:'2026-10-18',reports:{futbol:{file:'futbol-yeni.html'}}}):new Response('<body>new frozen report</body>')};
    const r=await worker.fetch(get('/futbol-yeni/',session),env),s=await r.text();assert.equal(r.status,200);
    assert.ok(calls.every(x=>x.includes('/deney/reports/2026-10-18/')));assert.ok(s.includes('/futbol-yeni/?date=2026-10-17'));assert.ok(s.includes('new frozen report'));
  }finally{globalThis.fetch=old;Date.now=oldNow;}
});
test('missing or wrong-date new report cannot fall back to old or another day',async()=>{
  const old=globalThis.fetch,oldNow=Date.now;
  try{
    Date.now=()=>Date.parse('2026-10-18T08:00:00Z');const session=await cookie();
    globalThis.fetch=async()=>new Response('secret-upstream',{status:404});
    let r=await worker.fetch(get('/basketbol-yeni/',session),env);assert.equal(r.status,404);assert.ok(!(await r.text()).includes('secret-upstream'));
    globalThis.fetch=async()=>Response.json({targetDate:'2026-10-17',reports:{basketbol:{file:'basketbol-yeni.html'}}});
    r=await worker.fetch(get('/basketbol-yeni/',session),env);assert.equal(r.status,502);
  }finally{globalThis.fetch=old;Date.now=oldNow;}
});
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
  const old=globalThis.fetch;globalThis.fetch=async()=>Response.json([]);
  try {const home=await worker.fetch(get('/',header.split(';')[0]),env);assert.equal(home.status,200);assert.ok((await home.text()).includes('Tahminlerim'));}finally{globalThis.fetch=old;}
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
    if (url.includes('/commits?')) return Response.json([{sha:'a'.repeat(40)}]);
    called = true;
    assert.equal(url, 'https://api.github.com/repos/sukrutureli/fathertahmin/contents/futbol/futbol.html?ref='+'a'.repeat(40));
    assert.equal(options.headers.Authorization, 'Bearer ' + env.GITHUB_TOKEN);
    assert.equal(options.redirect, 'manual');
    return new Response('<html>Synthetic report</html>');
  };
  try {
    const response = await worker.fetch(get('/futbol/', session), env);
    assert.equal(response.status, 200);assert.ok(called);
    const html=await response.text();
    assert.ok(html.includes('Synthetic report'));assert.ok(html.includes('Bugün'));assert.ok(html.includes('Dün'));
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

test('form pages preserve same-origin POST Origin and error text declares UTF-8', async () => {
  const login = await worker.fetch(get('/login'), env);
  assert.equal(login.headers.get('Referrer-Policy'), 'same-origin');
  const rejected = await worker.fetch(post('wrong', {Origin: 'null'}), env);
  assert.equal(rejected.status, 403);
  assert.equal(rejected.headers.get('Content-Type'), 'text/plain; charset=utf-8');
  assert.equal(rejected.headers.get('Referrer-Policy'), 'same-origin');
  assert.equal(await rejected.text(), 'İstek reddedildi.');
});

test('Istanbul midnight selects today snapshot even when latest root report is yesterday', async () => {
  const oldNow=Date.now, oldFetch=globalThis.fetch;let calls=[];
  try {
    Date.now=()=>Date.parse('2026-10-17T21:05:00Z');
    const session=await cookie();
    globalThis.fetch=async(url)=>{
      calls.push(url);
      if(url.includes('/commits?'))return Response.json([{sha:'b'.repeat(40)}]);
      return new Response('<body><div class="day-title">2026-10-18</div></body>');
    };
    let result=await worker.fetch(get('/basketbol/',session),env);
    assert.equal(result.status,200);assert.ok((await result.text()).includes('2026-10-18'));
    assert.ok(decodeURIComponent(calls[0]).includes('PredictionData-2026-10-18.json'));
    assert.ok(calls[1].endsWith('ref='+'b'.repeat(40)));
    calls=[];
    result=await worker.fetch(get('/basketbol/?date=2026-10-17',session),env);
    assert.equal(result.status,200);assert.ok(decodeURIComponent(calls[0]).includes('PredictionData-2026-10-17.json'));
  }finally{Date.now=oldNow;globalThis.fetch=oldFetch;}
});
test('missing current-day input never silently falls back to yesterday', async()=>{
  const oldFetch=globalThis.fetch,session=await cookie();
  try{
    globalThis.fetch=async()=>Response.json([]);
    const result=await worker.fetch(get('/futbol/',session),env);
    assert.equal(result.status,404);assert.ok((await result.text()).includes('henüz hazır değil'));
  }finally{globalThis.fetch=oldFetch;}
});
test('invalid duplicate or out-of-range date rejected without upstream access',async()=>{
  const session=await cookie();
  for(const path of ['/futbol/?date=invalid','/futbol/?date=2000-01-01','/futbol/?date=2026-10-18&date=2026-10-17'])
    assert.equal((await worker.fetch(get(path,session),env)).status,404);
});


test('dynamic archive discovers new HTML without worker edits and keeps only today yesterday',async()=>{
 const old=globalThis.fetch,now=Date.now;try{
 Date.now=()=>Date.parse('2026-10-18T08:00:00Z');const session=await cookie();let calls=[];
 globalThis.fetch=async(url)=>{calls.push(url);return Response.json(url.includes('/2026-10-18?')?[{name:'yeni-deneme.html',type:'file'},{name:'secret.json',type:'file'},{name:'fake.html',type:'symlink'}]:['2026-10-16','2026-10-17','2026-10-18'].map(name=>({name,type:'dir'})))};
 let r=await worker.fetch(get('/',session),env),html=await r.text();assert.ok(html.includes('2026-10-18'));assert.ok(html.includes('2026-10-17'));assert.ok(!html.includes('2026-10-16'));
 r=await worker.fetch(get('/?date=2026-10-18',session),env);html=await r.text();assert.ok(html.includes('/raporlar/2026-10-18/yeni-deneme.html'));assert.ok(!html.includes('secret.json'));assert.ok(!html.includes('fake.html'));
 }finally{globalThis.fetch=old;Date.now=now;}
});
test('dynamic HTML proxy is authenticated date scoped and supports inline report controls',async()=>{
 const old=globalThis.fetch,now=Date.now;try{
 Date.now=()=>Date.parse('2026-10-18T08:00:00Z');let calls=[];globalThis.fetch=async(url)=>{calls.push(url);return new Response('<body><script>function sort(){}</script>custom report</body>')};
 assert.equal((await worker.fetch(get('/raporlar/2026-10-18/new.html'),env)).status,303);assert.equal(calls.length,0);
 const session=await cookie();for(const p of ['/raporlar/2026-10-16/new.html','/raporlar/2026-10-18/secret.json','/raporlar/2026-10-18/a%2Fb.html','/raporlar/2026-10-18/a.html?ref=other'])assert.equal((await worker.fetch(get(p,session),env)).status,404);
 assert.equal(calls.length,0);const r=await worker.fetch(get('/raporlar/2026-10-18/new.html',session),env);assert.equal(r.status,200);assert.ok((await r.text()).includes('<script>function sort()'));assert.ok(calls[0].includes('contents/raporlar/2026-10-18/new.html?ref=main'));
 }finally{globalThis.fetch=old;Date.now=now;}
});
