"""Artifact generation + sanitization.

Kinds: markdown | html. Generated HTML is UNTRUSTED:
- Server-side: bleach-clean with a tight allowlist; strip <script>, event
  handlers, javascript: URLs, iframes, forms, objects.
- Client-side: rendered only inside <iframe sandbox=""> (no allow-scripts),
  so even missed payloads cannot execute or touch parent state.
Tests cover <script>, onerror, javascript: hrefs.
"""
import logging
import re

import bleach

from ..config import get_settings
from .providers import get_provider

log = logging.getLogger("lenny.artifact")

ALLOWED_TAGS = ["h1", "h2", "h3", "h4", "p", "ul", "ol", "li", "b", "i", "strong",
                "em", "a", "code", "pre", "blockquote", "table", "thead", "tbody",
                "tr", "th", "td", "div", "span", "br", "hr", "style"]
ALLOWED_ATTRS = {"a": ["href", "title"], "div": ["class"], "span": ["class"],
                 "table": ["class"], "code": ["class"], "pre": ["class"], "style": []}

SYSTEM_MD = """You write reusable Markdown documents from a product/growth conversation.
Output ONLY Markdown (start with # title). Use headings, bullets, tables where useful.
Keep it practical and grounded in the conversation. No HTML, no code fences around the whole doc."""

SYSTEM_HTML = """You write a single self-contained HTML snippet (no <html>/<head> wrapper needed, but allowed).
Rules: inline <style> only; NO <script>, NO event handlers (onclick etc.), NO external URLs except https: links,
no iframes/forms/objects. Style cleanly with modern CSS. Output ONLY the HTML."""


def sanitize_html(dirty: str) -> str:
    dirty = re.sub(r"(?is)<script.*?</script>", "", dirty)
    dirty = re.sub(r"(?i)\s+on\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", dirty)
    clean = bleach.clean(dirty, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS,
                         protocols=["http", "https", "mailto"], strip=True)
    return clean


def detect_kind(prompt: str) -> str:
    return "html" if re.search(r"html|landing\s*page|web\s*page|styled|css", prompt, re.I) else "markdown"


def generate_artifact(prompt: str, conversation: str = "", kind: str | None = None) -> dict:
    s = get_settings()
    kind = (kind or detect_kind(prompt)).lower()
    if kind not in ("markdown", "html"):
        kind = "markdown"
    system = SYSTEM_HTML if kind == "html" else SYSTEM_MD
    full_prompt = f"Conversation context:\n{conversation[:3000]}\n\nTask: {prompt}\n\nOutput only the {kind}."
    res = get_provider().generate(system, full_prompt)
    content = res.text.strip().strip("`")
    if kind == "html":
        content = sanitize_html(content)
    log.info("artifact.ok kind=%s chars=%d", kind, len(content))
    title_m = re.search(r"^#\s+(.+)$", content, re.M) if kind == "markdown" else re.search(r"(?i)<h1[^>]*>(.+?)</h1>", content)
    title = (title_m.group(1).strip()[:120] if title_m else (prompt[:80] or "Untitled artifact"))
    title = re.sub(r"<[^>]+>", "", title)
    return {"kind": kind, "content": content, "title": title or "Untitled artifact",
            "provider": res.provider, "model": res.model}
