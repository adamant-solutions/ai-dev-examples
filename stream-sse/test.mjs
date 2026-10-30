// node test.mjs <app-url> <app-url-with-missing-model> <fake-ollama-url>
import assert from 'node:assert/strict';
import { readSSE, streamChat } from './static/sse-client.js';

const [app, appMissing, fake] = process.argv.slice(2);

// 1. Parser: events split across chunks, CRLF and CR line endings, comments, multi-line data.
function responseFrom(chunks) {
  const enc = new TextEncoder();
  return new Response(new ReadableStream({
    start(c) { for (const s of chunks) c.enqueue(enc.encode(s)); c.close(); },
  }));
}
const evs = [];
for await (const ev of readSSE(responseFrom([
  ': ping\n\nevent: tok', 'en\ndata: {"text":"a"}\r', '\n\r\ndata: line1\ndata:line2\nid: 7\n\n',
  'data: no blank line at the end',
]))) evs.push(ev);
assert.deepEqual(evs, [
  { event: 'token', data: '{"text":"a"}', id: null },
  { event: 'message', data: 'line1\nline2', id: '7' },
]);

// 2. End to end: browser code -> FastAPI -> fake Ollama.
let text = '';
const usage = await streamChat(`${app}/api/chat/stream`, 'why is the sky blue?', { onToken: (t) => { text += t; } });
assert.equal(text, 'Light is scattered by the air.\nBlue scatters more.');
assert.deepEqual(usage, { prompt_tokens: 12, output_tokens: 9 });

// 3. Upstream error (model not found) arrives as an "error" event inside a 200 stream.
await assert.rejects(streamChat(`${appMissing}/api/chat/stream`, 'hi', {}), /model error: .*404/);

// 4. Abort after the first token: the server must stop reading from the model.
const controller = new AbortController();
await assert.rejects(streamChat(`${app}/api/chat/stream`, 'slow please', {
  onToken: () => controller.abort(),
  signal: controller.signal,
}), { name: 'AbortError' });
let stats;
for (let i = 0; i < 30; i++) {
  await new Promise((r) => setTimeout(r, 200));
  stats = await (await fetch(`${fake}/stats`)).json();
  if (stats.client_closed > 0) break;
}
assert.equal(stats.client_closed, 1, `upstream not closed after abort: ${JSON.stringify(stats)}`);
console.log('stream-sse OK', usage, stats);
