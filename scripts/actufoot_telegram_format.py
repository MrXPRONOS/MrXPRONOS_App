"""Presentation commune des publications Actu Foot sur Telegram.

Ne modifie jamais les faits, les URLs ni les reçus D1: uniquement le HTML
affiché, avec une ligne vide entre titre, citation et source. Compatible
avec sendRichMessage et avec le parse_mode HTML du Bot API historique.
"""
from __future__ import annotations

import html
import re

_BREAKS = re.compile(r"<br\s*/?>", re.IGNORECASE)
_PARAGRAPH_OPEN = re.compile(r"<p(?:\s[^>]*)?>", re.IGNORECASE)
_PARAGRAPH_CLOSE = re.compile(r"</p\s*>", re.IGNORECASE)
_TITLE = re.compile(r"^(?P<title>(?:[^\n<]{0,12}\s*)?<b>.+?</b>)(?:\n+|$)", re.DOTALL)
_SOURCE = re.compile(r"\bsource\s*:", re.IGNORECASE)


def normalize_paragraphs(markup: str) -> str:
    """Normalize rich-message layout into explicit Telegram-compatible lines."""
    text = str(markup or "").replace("\r\n", "\n").replace("\r", "\n")
    text = _BREAKS.sub("\n", text)
    text = _PARAGRAPH_OPEN.sub("\n\n", text)
    text = _PARAGRAPH_CLOSE.sub("\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def quote_excerpt(content: str) -> str:
    """A sourced paragraph is rendered as a real Telegram blockquote."""
    body = normalize_paragraphs(html.escape(str(content or "").strip(), quote=True))
    if not body:
        return ""
    return "<blockquote>" + body + "</blockquote>"


def source_footer(source: str, *, category: str = "") -> str:
    parts = []
    if category.strip():
        parts.append("🏷 Catégorie : " + html.escape(category.strip(), quote=False))
    parts.append("📰 Source : " + html.escape(source.strip() or "Source football", quote=False))
    return "<i>" + "\n".join(parts) + "</i>"


def news_markup(title: str, content: str, category: str, source: str) -> str:
    """Title / blank line / quoted RSS description / blank line / attribution."""
    return "\n\n".join([
        "<b>" + html.escape(title.strip(), quote=False) + "</b>",
        quote_excerpt(content),
        source_footer(source, category=category),
    ])


def editorial_markup(markup: str, *, source: str = "", title_fallback: str = "") -> str:
    """Enrich existing main-channel templates without removing valid HTML.

    Already-quoted content is preserved. For plain templates, only the
    information after the first bold heading is put in a quote block.
    Existing explicit source attributions are not duplicated.
    """
    text = normalize_paragraphs(markup)
    if not text:
        return ""
    if title_fallback and not _TITLE.match(text) and not text.lstrip().startswith(("<h2>", "<h3>")):
        text = "<b>" + html.escape(title_fallback.strip(), quote=False) + "</b>\n\n" + text
    if "<blockquote" not in text.lower():
        match = _TITLE.match(text)
        if match:
            lead = match.group("title")
            rest = text[match.end():].strip()
            if rest:
                text = lead + "\n\n<blockquote>" + rest + "</blockquote>"
        else:
            # No recognizable title: do not invent one or hide unknown text.
            text = re.sub(r"\n{3,}", "\n\n", text)
    else:
        # The initial heading should remain separated even if an old template
        # used one newline rather than a blank line before the quote.
        match = _TITLE.match(text)
        if match:
            text = match.group("title") + "\n\n" + text[match.end():].strip()
    if source and not _SOURCE.search(html.unescape(text)):
        cleaned = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(source))).strip()[:90]
        if cleaned:
            text += "\n\n" + source_footer(cleaned)
    return normalize_paragraphs(text)
