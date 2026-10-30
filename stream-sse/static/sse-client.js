// Reads a text/event-stream response from fetch(). Works in browsers and in Node.js 18+.
// Parsing follows the WHATWG HTML spec, "Interpreting an event stream":
// https://html.spec.whatwg.org/multipage/server-sent-events.html#event-stream-interpretation

export async function* readSSE(response) {
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';
  let type = '', data = [], id = null;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) return; // an event without its final blank line is discarded, as the spec says
      buffer += value;
      // Split on CRLF, LF or CR; a CR at the very end may be the first half of a CRLF, so keep it.
      const lines = buffer.split(/\r\n|\r(?!$)|\n/);
      buffer = lines.pop();
      for (const line of lines) {
        if (line === '') { // blank line: dispatch the event
          if (data.length) yield { event: type || 'message', data: data.join('\n'), id };
          type = ''; data = [];
          continue;
        }
        if (line.startsWith(':')) continue; // comment, e.g. keep-alive pings
        const i = line.indexOf(':');
        const field = i === -1 ? line : line.slice(0, i);
        let val = i === -1 ? '' : line.slice(i + 1);
        if (val.startsWith(' ')) val = val.slice(1);
        if (field === 'data') data.push(val);
        else if (field === 'event') type = val;
        else if (field === 'id' && !val.includes('\0')) id = val;
        // "retry" only matters for EventSource reconnection; other fields are ignored.
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// POSTs the prompt and calls onToken(text) for every piece of the answer.
// Pass an AbortSignal to stop: the server sees the disconnect and stops the model call.
export async function streamChat(url, prompt, { onToken, signal } = {}) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
    body: JSON.stringify({ text: prompt }),
    signal,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  for await (const ev of readSSE(res)) {
    const payload = JSON.parse(ev.data);
    if (ev.event === 'token') onToken?.(payload.text);
    else if (ev.event === 'error') throw new Error(`model error: ${JSON.stringify(payload)}`);
    else if (ev.event === 'done') return payload; // token counts reported by the model server
  }
  throw new Error('stream ended before the "done" event');
}
