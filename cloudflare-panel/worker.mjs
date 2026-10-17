// Paste into the Cloudflare Worker editor. Secrets: PANEL_PASSWORD, SESSION_SECRET, GITHUB_TOKEN.
const encoder = new TextEncoder();
const COOKIE = '__Host-tahmin_session';
const TTL = 7 * 24 * 60 * 60;
const REPO = 'https://api.github.com/repos/sukrutureli/fathertahmin/contents/';
const attempts = new Map(); // Best-effort per-isolate throttle; not a global rate limiter.
const STYLE = 'body{font:17px system-ui;background:#0d1523;color:#edf4ff;margin:0;padding:24px}main{max-width:600px;margin:6vh auto}a,button{display:block;box-sizing:border-box;background:#264d85;color:white;text-decoration:none;padding:20px;margin:16px 0;border:0;border-radius:14px;font:inherit;width:100%;cursor:pointer}input{box-sizing:border-box;width:100%;padding:16px;border-radius:12px;border:1px solid #667b99;font:inherit;background:#18283f;color:white}small{color:#b9c9de}';
function response(body, status = 200, type = 'text/html; charset=utf-8', extra = {}) {
  return new Response(body, {status, headers: {
    'Content-Type': type, 'Cache-Control': 'private, no-store',
    'X-Robots-Tag': 'noindex, nofollow, noarchive', 'Referrer-Policy': 'no-referrer',
    'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
    'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    ...extra
  }});
}
function page(content) {
  return '<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Tahminlerim</title><style>' + STYLE + '</style><main>' + content + '</main></html>';
}
function redirect(path, cookie) {
  return response(null, 303, 'text/plain', {...(cookie ? {'Set-Cookie': cookie} : {}), Location: path});
}
function b64(bytes) {
  return btoa(String.fromCharCode(...new Uint8Array(bytes))).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '');
}
function unb64(value) {
  const text = value.replaceAll('-', '+').replaceAll('_', '/');
  return Uint8Array.from(atob(text + '='.repeat((4 - text.length % 4) % 4)), c => c.charCodeAt(0));
}
async function signingKey(env) {
  // Changing either secret invalidates all existing sessions.
  return crypto.subtle.importKey('raw', encoder.encode(env.SESSION_SECRET + '\n' + env.PANEL_PASSWORD),
    {name: 'HMAC', hash: 'SHA-256'}, false, ['sign', 'verify']);
}
async function session(env) {
  const nonce = b64(crypto.getRandomValues(new Uint8Array(16)));
  const payload = 'v1.' + (Math.floor(Date.now() / 1000) + TTL) + '.' + nonce;
  return payload + '.' + b64(await crypto.subtle.sign('HMAC', await signingKey(env), encoder.encode(payload)));
}
async function authorized(request, env) {
  try {
    const value = (request.headers.get('Cookie') || '').split(';').map(x => x.trim())
      .find(x => x.startsWith(COOKIE + '='))?.slice(COOKIE.length + 1) || '';
    if (!/^v1\.\d{10,12}\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}$/.test(value)) return false;
    const parts = value.split('.');
    const now = Math.floor(Date.now() / 1000), expires = Number(parts[1]);
    if (expires <= now || expires > now + TTL) return false;
    return await crypto.subtle.verify('HMAC', await signingKey(env), unb64(parts[3]), encoder.encode(parts.slice(0, 3).join('.')));
  } catch { return false; }
}
async function passwordMatches(value, expected) {
  const [a, b] = await Promise.all([value, expected].map(x => crypto.subtle.digest('SHA-256', encoder.encode(x))));
  const x = new Uint8Array(a), y = new Uint8Array(b); let different = 0;
  for (let i = 0; i < x.length; i++) different |= x[i] ^ y[i];
  return different === 0;
}
function allowAttempt(ip) {
  const now = Date.now();
  if (attempts.size > 4096) for (const [key, item] of attempts) if (item.until <= now) attempts.delete(key);
  if (attempts.size > 4096) return false;
  let item = attempts.get(ip);
  if (!item || item.until <= now) { item = {count: 0, until: now + 60_000}; attempts.set(ip, item); }
  return ++item.count <= 10;
}
function reportPath(path) {
  if (path === '/futbol/' || path === '/futbol') return 'futbol/futbol.html';
  if (path === '/basketbol/' || path === '/basketbol') return 'basketbol/basketbol.html';
  // Only these report/data paths are readable; never an arbitrary URL or repository.
  return /^\/(futbol|basketbol)\/(?:[A-Za-z0-9_-]+\.html|data\/[A-Za-z0-9_-]+\.(?:json|html))$/.test(path) ? path.slice(1) : null;
}
export default {
  async fetch(request, env) {
    try {
      if (typeof env.PANEL_PASSWORD !== 'string' || env.PANEL_PASSWORD.length < 12 ||
          typeof env.SESSION_SECRET !== 'string' || env.SESSION_SECRET.length < 32 ||
          typeof env.GITHUB_TOKEN !== 'string' || !env.GITHUB_TOKEN) {
        return response(page('<h1>Kurulum eksik</h1><p>PANEL_PASSWORD en az 12, SESSION_SECRET en az 32 karakter olmalı. GITHUB_TOKEN Secret olarak eklenmeli.</p>'), 503);
      }
      const url = new URL(request.url), path = url.pathname;
      if (url.protocol !== 'https:') return response('HTTPS gerekli.', 400, 'text/plain');
      if (request.method === 'POST') {
        if (request.headers.get('Origin') !== url.origin) return response('İstek reddedildi.', 403, 'text/plain');
        if (path === '/logout') return redirect('/login', COOKIE + '=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Strict');
        if (path !== '/login') return response('Bulunamadı.', 404, 'text/plain');
        if (!allowAttempt(request.headers.get('CF-Connecting-IP') || 'unknown'))
          return response('Çok fazla deneme. Bir dakika sonra tekrar dene.', 429, 'text/plain', {'Retry-After': '60'});
        if (!(request.headers.get('Content-Type') || '').startsWith('application/x-www-form-urlencoded')) return response('Geçersiz form.', 400, 'text/plain');
        if (Number(request.headers.get('Content-Length')) > 4096) return response('Form çok büyük.', 413, 'text/plain');
        const body = await request.text();
        if (body.length > 4096) return response('Form çok büyük.', 413, 'text/plain');
        const password = new URLSearchParams(body).get('password') || '';
        if (!await passwordMatches(password, env.PANEL_PASSWORD)) return redirect('/login?error=1');
        return redirect('/', COOKIE + '=' + await session(env) + '; Path=/; Max-Age=' + TTL + '; Secure; HttpOnly; SameSite=Strict');
      }
      if (request.method !== 'GET' && request.method !== 'HEAD') return response('Yöntem desteklenmiyor.', 405, 'text/plain');
      const loggedIn = await authorized(request, env);
      if (path === '/login') {
        if (loggedIn) return redirect('/');
        return response(request.method === 'HEAD' ? null : page('<h1>Tahminlerim</h1><p>Özel paneline giriş yap.</p>' +
          (url.searchParams.has('error') ? '<p>Şifre doğru değil.</p>' : '') +
          '<form method="post" action="/login"><input name="password" type="password" autocomplete="current-password" placeholder="Panel şifren" required maxlength="1024"><button>Giriş yap</button></form>'));
      }
      // Every report and JSON request passes authentication before any upstream call.
      if (!loggedIn) return redirect('/login');
      if (path === '/') return response(request.method === 'HEAD' ? null : page('<h1>Tahminlerim</h1><small>Raporu seç</small><a href="/futbol/">⚽ Futbol</a><a href="/basketbol/">🏀 Basketbol</a><form method="post" action="/logout"><button>Çıkış yap</button></form>'));
      const file = reportPath(path);
      if (!file || url.search) return response('Bulunamadı.', 404, 'text/plain');
      const upstream = await fetch(REPO + file + '?ref=main', {
        headers: {Authorization: 'Bearer ' + env.GITHUB_TOKEN, Accept: 'application/vnd.github.raw+json',
          'User-Agent': 'private-tahmin-panel', 'X-GitHub-Api-Version': '2022-11-28', 'Cache-Control': 'no-cache'},
        redirect: 'manual', signal: AbortSignal.timeout(20000)
      });
      if (upstream.status !== 200) {
        return response('Rapor okunamadı. GitHub token yetkisini ve dosyanın varlığını kontrol et.', 502, 'text/plain');
      }
      return response(request.method === 'HEAD' ? null : upstream.body, 200,
        file.endsWith('.json') ? 'application/json; charset=utf-8' : 'text/html; charset=utf-8');
    } catch {
      // Never echo upstream bodies, request passwords or tokens into responses or logs.
      return response('Panel şu an yanıt veremiyor. Biraz sonra tekrar dene.', 503, 'text/plain');
    }
  }
};
