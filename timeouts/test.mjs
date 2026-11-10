import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { streamCompletion } from './client.mjs';

let proc, base;

before(async () => {
  const port = 8500 + Math.floor(Math.random() * 400);
  proc = spawn('python3', ['fake_server.py', String(port)], { stdio: ['ignore', 'pipe', 'inherit'] });
  await new Promise((resolve) => proc.stdout.once('data', resolve));  // "listening on <port>"
  base = `http://127.0.0.1:${port}`;
});
after(() => proc.kill());

const abandoned = async () => (await (await fetch(`${base}/stats`)).json()).abandoned;
async function waitFor(fn, ms = 5000) {
  for (let t = 0; t < ms; t += 100) {
    if (await fn()) return true;
    await new Promise((r) => setTimeout(r, 100));
  }
  return false;
}

test('total deadline stops a stream that never ends', async () => {
  const before = await abandoned();
  const got = [];
  await assert.rejects(
    streamCompletion(`${base}/drip`, {}, { totalMs: 1000, onToken: (l) => got.push(l) }),
    (err) => err.name === 'TimeoutError',
  );
  assert.ok(got.length > 3);
  assert.ok(await waitFor(async () => (await abandoned()) > before), 'server never saw the disconnect');
});

test('idle timeout fires when the upstream goes quiet', async () => {
  await assert.rejects(
    streamCompletion(`${base}/stall`, {}, { idleMs: 500, totalMs: 10_000, onToken: () => {} }),
    /no data for 500 ms/,
  );
});

test('caller abort (Stop button) closes the connection', async () => {
  const before = await abandoned();
  const stop = new AbortController();
  const p = streamCompletion(`${base}/drip`, {}, { signal: stop.signal, onToken: () => {} });
  setTimeout(() => stop.abort(), 500);
  await assert.rejects(p, (err) => err.name === 'AbortError');
  assert.ok(await waitFor(async () => (await abandoned()) > before), 'server never saw the disconnect');
});
