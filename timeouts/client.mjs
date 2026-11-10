// Node.js 20.3+ (AbortSignal.any). No dependencies.
export async function streamCompletion(url, payload, { totalMs = 120_000, idleMs = 30_000, signal, onToken = console.log } = {}) {
  // One controller we abort ourselves when the stream goes quiet.
  const idle = new AbortController();
  let idleTimer;
  const armIdle = () => {
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => idle.abort(new Error(`no data for ${idleMs} ms`)), idleMs);
  };

  const signals = [AbortSignal.timeout(totalMs), idle.signal];  // total deadline + idle timeout
  if (signal) signals.push(signal);                              // + cancellation from the caller (a "Stop" button)

  const tokens = [];
  armIdle();
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
      signal: AbortSignal.any(signals),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const decoder = new TextDecoder();
    let buffer = '';
    for await (const chunk of res.body) {
      armIdle();                                                 // data arrived: restart the idle clock
      buffer += decoder.decode(chunk, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) { tokens.push(line); onToken(line); }
    }
    return tokens;
  } finally {
    clearTimeout(idleTimer);
  }
}
