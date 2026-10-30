// Count tokens and estimate the cost of a model call before you send it (Node.js 18+ or a bundler).
import { Tiktoken } from 'js-tiktoken/lite';
import o200k_base from 'js-tiktoken/ranks/o200k_base';

const enc = new Tiktoken(o200k_base); // load once: building the encoder is the slow part

export function countTiktoken(text) {
  return enc.encode(text).length;
}

// USD per million tokens, from https://platform.claude.com/docs/en/about-claude/pricing (checked 2026-10-30).
export const PRICES = {
  'claude-sonnet-5-5': { input: 2.0, output: 10.0 },
  'claude-opus-5-5': { input: 4.0, output: 20.0 },
};

export function estimateCost(inputTokens, maxOutputTokens, price) {
  const low = (inputTokens * price.input) / 1e6;
  return { low, high: low + (maxOutputTokens * price.output) / 1e6 };
}

// Anthropic's token counting endpoint (free, separate rate limit). Call it from your server, never
// from the browser: it needs your API key.
export async function countClaudeTokens({ model, messages, system, apiKey, baseUrl = 'https://api.anthropic.com' }) {
  const res = await fetch(`${baseUrl}/v1/messages/count_tokens`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-api-key': apiKey, 'anthropic-version': '2023-06-01' },
    body: JSON.stringify({ model, messages, ...(system ? { system } : {}) }),
  });
  if (!res.ok) throw new Error(`count_tokens HTTP ${res.status}: ${await res.text()}`);
  return (await res.json()).input_tokens;
}
