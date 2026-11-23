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


# 2026-11 : la catégorie rédigée par Mr XPRONOS n'est pas le gros
# titre en tête ; elle vient juste au-dessus de l'attribution.
_BOTTOM_FOOTER = re.compile(
    r"(?:\n+)?<b>🏷 [^<]+</b>\n<i>📰 Source : [^<]+</i>\s*$",
    re.IGNORECASE,
)
_EXISTING_SOURCE = re.compile(
    r"(?:\n+)?<i>(?:📰\s*)?Source\s*:\s*([^<]+)</i>\s*$",
    re.IGNORECASE,
)


def _visible(value: str, limit: int = 120) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", html.unescape(str(value or "")))).strip()[:limit]


def match_header(card: dict | None) -> str:
    """Start with *verified* teams/score/time supplied by the publication."""
    card = card or {}
    if not isinstance(card, dict):
        return ""
    home = _visible(card.get("home") or card.get("home_team"), 70)
    away = _visible(card.get("away") or card.get("away_team"), 70)
    if not home or not away:
        matches = card.get("matches")
        first = matches[0] if isinstance(matches, list) and matches else {}
        if isinstance(first, dict):
            home = _visible(first.get("home"), 70)
            away = _visible(first.get("away"), 70)
            if not card.get("time"):
                card = {**card, "time": first.get("time")}
    if not home or not away:
        return ""
    score = _visible(card.get("score"), 20)
    pair = card.get("scores")
    if not score and isinstance(pair, (tuple, list)) and len(pair) >= 2:
        if all(v is not None and str(v).strip() for v in pair[:2]):
            score = f"{pair[0]}–{pair[1]}"
    score = score.replace("-", "–") if re.fullmatch(r"\d+\s*[-–]\s*\d+", score) else ""
    minute = _visible(card.get("minute_text") or card.get("minute"), 18)
    if minute and re.fullmatch(r"\d{1,3}(?:\+\d{1,2})?", minute):
        minute += "'"
    time = _visible(card.get("time"), 18)
    names = (
        html.escape(home, quote=False) + " "
        + (html.escape(score, quote=False) if score else "—")
        + " " + html.escape(away, quote=False)
    )
    if minute:
        names += " · " + html.escape(minute, quote=False)
    elif time:
        names += " · " + html.escape(time, quote=False)
    return "<b>⚽ " + names + "</b>"


def editorial_bottom_markup(
    markup: str,
    *,
    category: str,
    source: str,
    card: dict | None = None,
    genuine_news_headline: bool = False,
) -> str:
    """Match-first, quote, editorial category, source; idempotent on retries.

    Source-originated article headlines remain at the top. Editorial labels
    such as SCORE LIVE, GOAL, PROGRAMME are always moved to the bottom.
    Already-existing blockquotes remain real blockquotes (not nested).
    """
    text = normalize_paragraphs(markup)
    if not text:
        return ""
    if _BOTTOM_FOOTER.search(text):
        return text

    current_source = _EXISTING_SOURCE.search(text)
    if current_source:
        if not source.strip():
            source = _visible(current_source.group(1), 90)
        text = text[:current_source.start()].rstrip()
    source = _visible(source, 90) or "Mr XPRONOS"

    match = _TITLE.match(text)
    current_heading = match.group("title") if match else ""
    body = text[match.end():].strip() if match else text
    if not body and current_heading:
        body = current_heading
        current_heading = ""

    # Genuine sourced news is distinct from a label invented by the channel.
    if genuine_news_headline and current_heading:
        header = current_heading
    else:
        header = match_header(card)
        if not header and body.lstrip().startswith("<b>"):
            # The first bold line may be a verified match/result statement.
            body_match = _TITLE.match(body)
            if body_match and re.search(r"\d+\s*[-–]\s*\d+|(?:\s[-–]\s| vs )", _visible(body_match.group("title")), re.I):
                header = body_match.group("title")
                body = body[body_match.end():].strip()
        if not header and current_heading and not body:
            body = current_heading

    if not body:
        body = "<i>Informations complémentaires non communiquées.</i>"
    if "<blockquote" not in body.lower():
        body = "<blockquote>" + body + "</blockquote>"
    if header and header.strip() == body.strip():
        header = ""

    clean_category = _visible(category, 85) or "⚽ ACTU FOOT"
    footer = (
        "<b>🏷 " + html.escape(clean_category, quote=False) + "</b>\n"
        + "<i>📰 Source : " + html.escape(source, quote=False) + "</i>"
    )
    return normalize_paragraphs("\n\n".join(x for x in (header, body, footer) if x))
