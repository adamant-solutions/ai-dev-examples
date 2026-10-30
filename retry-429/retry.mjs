// Call an HTTP API and retry on 429/5xx, honouring Retry-After. Node.js 18+ (built-in fetch), no dependencies.
const RETRYABLE = new Set([429, 500, 502, 503, 504]);

export function retryAfterMs(value) {
  if (!value) return null;
  const v = value.trim();
  if (/^\d+$/.test(v)) return Number(v) * 1000;          // seconds
  const date = Date.parse(v);                             // or an HTTP date
  return Number.isNaN(date) ? null : Math.max(0, date - Date.now());
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function postJson(url, payload, { headers = {}, maxAttempts = 5, baseMs = 500, capMs = 30_000 } = {}) {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...headers },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(60_000),
    });
    if (res.ok) return res.json();
    if (!RETRYABLE.has(res.status) || attempt === maxAttempts) {
      throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    }
    let wait = retryAfterMs(res.headers.get('retry-after'));
    if (wait === null) wait = Math.random() * Math.min(capMs, baseMs * 2 ** attempt); // full jitter
    wait = Math.min(wait, capMs);
    console.log(`HTTP ${res.status}, attempt ${attempt}/${maxAttempts}, waiting ${(wait / 1000).toFixed(1)}s`);
    await res.body?.cancel();
    await sleep(wait);
  }
}
