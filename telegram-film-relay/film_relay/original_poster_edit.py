"""Update the *existing* CinéX public photo in place, never repost it.

Telegram limitations:
- A bot may edit only its own messages or channel messages it is allowed to
  edit as administrator. If refused, fail closed: no duplicate, no deletion.
- An existing caption stays byte-for-byte identical unless it needs to absorb
  a separately posted synopsis. Telegram photo captions max out at 1024 UTF-16
  code units; never truncate an existing synopsis or erase its entities.
"""
from __future__ import annotations

from html import escape
from urllib.parse import urlparse
import logging

LOG = logging.getLogger("cinex.original_cover")

CAPTION_LIMIT = 1024


def button_url(button) -> str | None:
    underlying = getattr(button, "button", button)
    return getattr(underlying, "url", None)


def safe_buttons(original, additional, private_video_url, *, verified_part_urls=()):
    """Preserve existing URL rows, append missing ones, refuse opaque controls.

    Never silently replace a different private video target; if the source
    cover already points to another film, a human must resolve the ambiguity.
    """
    prefix = private_video_url.rsplit("/", 1)[0] + "/"
    allowed = {private_video_url, *verified_part_urls}
    rows, seen = [], set()
    for row in getattr(original, "buttons", None) or ():
        kept = []
        for button in row:
            url = button_url(button)
            if not url or not isinstance(url, str) or not url.startswith("https://"):
                raise RuntimeError("Fiche d'origine avec boutons non-URL : modification manuelle requise")
            if url.startswith(prefix) and url not in allowed:
                raise RuntimeError("Fiche d'origine déjà associée à une autre vidéo privée")
            if url in seen:
                continue
            seen.add(url)
            kept.append(button)
        if kept:
            rows.append(kept)
    for row in additional:
        kept = []
        for button in row:
            url = button_url(button)
            if not url:
                raise ValueError("Nouveau bouton sans lien")
            if url not in seen:
                kept.append(button)
                seen.add(url)
        if kept:
            rows.append(kept)
    return rows


def original_caption_with_text(poster, extra_text: str):
    """Return (caption, use_caption_edit, use_html).

    Existing caption and formatting survive; intervening text is appended
    exactly once and only if the whole caption fits Telegram's limit.
    """
    original = str(getattr(poster, "raw_text", "") or "")
    extra = str(extra_text or "").strip()
    if not extra or extra in original:
        return original, False, False
    caption = (original + "\n\n" + extra) if original else extra
    if len(caption.encode("utf-16-le")) // 2 > CAPTION_LIMIT:
        raise RuntimeError("Description trop longue pour la fiche existante : texte conservé, vidéo non supprimée")
    formatted = getattr(poster, "text_html", None)
    if isinstance(formatted, str):
        original_html = formatted
        return ((original_html + "\n\n" if original_html else "") + escape(extra),
                True, True)
    if getattr(poster, "entities", None):
        raise RuntimeError("Formatage de la description non accessible : fiche laissée intacte")
    return caption, True, False


def public_keyboard_signature(poster):
    """Read-only signature: a no-op preflight must never alter existing links."""
    rows = []
    for row in getattr(poster, "buttons", None) or ():
        current = []
        for item in row:
            url = button_url(item)
            raw = getattr(item, "button", item)
            label = getattr(raw, "text", None)
            if not isinstance(url, str) or not url.startswith("https://") or not label:
                raise RuntimeError("Ancien bouton non-URL : contrôle manuel requis")
            current.append((str(label), url))
        if current:
            rows.append(tuple(current))
    return tuple(rows)


def read_only_keyboard_signature(poster):
    """Snapshot an original Telegram keyboard without changing it.

    For *read-only verification after a proven private media match*, accept
    native Telegram TL button types including legacy callback/inline buttons.
    Compare their complete serialized bytes (constructor + all fields), not
    merely their labels. If a button cannot be faithfully serialized, fail
    closed. This is NOT used to grant bot editing rights: preflight and
    safe_buttons still require editable, explicit URL controls.
    """
    rows = []
    for row in getattr(poster, "buttons", None) or ():
        entries = []
        for item in row:
            raw = getattr(item, "button", item)
            kind = type(raw)
            # Telethon exposes the exact MTProto TL button beneath the wrapper.
            # Its serialization includes callback payloads and other fields.
            if kind.__module__.startswith("telethon.tl.types"):
                try:
                    serialized = bytes(raw)
                except (TypeError, ValueError, AttributeError) as exc:
                    raise RuntimeError("Bouton Telegram impossible à comparer") from exc
                if not serialized:
                    raise RuntimeError("Bouton Telegram sans représentation")
                entries.append(("telegram", kind.__name__, serialized))
                continue
            # Minimal test doubles or fully exposed URL-only button wrappers.
            # Unknown callbacks/inline buttons without native TL proof are
            # never trusted for destructive actions.
            url = button_url(item)
            label = getattr(raw, "text", None)
            if (isinstance(url, str) and url.startswith("https://")
                    and isinstance(label, str) and label):
                entries.append(("url", label, url))
                continue
            raise RuntimeError("Bouton non-URL sans signature Telegram fiable")
        rows.append(tuple(entries))
    return tuple(rows)


async def preflight_original_editability(client, bot, public, original):
    """Test the EXACT current keyboard before uploading a private archive.

    Telegram's 'message is not modified' response counts as editable.
    If a different bot authored the message, this fails before any copy.
    The second read proves caption, photo and visible URL buttons unchanged.
    """
    live = await client.get_messages(public, ids=original.id)
    if (not live or not getattr(live, "photo", None)
            or live.id != original.id
            or getattr(live.photo, "id", None) != getattr(original.photo, "id", None)
            or str(getattr(live, "raw_text", "") or "") !=
               str(getattr(original, "raw_text", "") or "")):
        raise RuntimeError("Fiche historique changée ou inaccessible avant le contrôle.")
    before = public_keyboard_signature(live)
    await bot.edit_reply_markup(public, live.id, buttons=getattr(live, "buttons", None))
    checked = await client.get_messages(public, ids=original.id)
    if (not checked or checked.id != live.id or not getattr(checked, "photo", None)
            or getattr(checked.photo, "id", None) != getattr(live.photo, "id", None)
            or str(getattr(checked, "raw_text", "") or "") != str(getattr(live, "raw_text", "") or "")
            or public_keyboard_signature(checked) != before):
        raise RuntimeError("La fiche a changé pendant le contrôle ; archivage bloqué.")
    return True


async def edit_original_cover(client, bot, public, original, video,
                              *, buttons, private_video_url, extra_text="", verified_part_urls=()):
    """Edit only the exact original photo and verify its ID and photo survived."""
    live = await client.get_messages(public, ids=original.id)
    if not live or not getattr(live, "photo", None):
        raise RuntimeError("Fiche originale absente ou sans photo ; aucune republication")
    if (getattr(getattr(live, "photo", None), "id", None)
            != getattr(getattr(original, "photo", None), "id", None)):
        raise RuntimeError("La photo originale a changé depuis l'analyse")
    if str(getattr(live, "raw_text", "") or "") != str(
            getattr(original, "raw_text", "") or ""):
        raise RuntimeError("La description originale a changé : nouvelle analyse requise")
    combined = safe_buttons(live, buttons, private_video_url,
                            verified_part_urls=verified_part_urls)
    caption, needs_edit, is_html = original_caption_with_text(live, extra_text)
    if needs_edit:
        await bot.edit_photo_caption(
            public, original.id, caption=caption,
            buttons=combined, parse_mode="html" if is_html else None,
        )
    else:
        await bot.edit_reply_markup(public, original.id, buttons=combined)
    edited = await client.get_messages(public, ids=original.id)
    if not edited or not getattr(edited, "photo", None):
        raise RuntimeError("Photo d'origine introuvable après édition")
    if getattr(live, "pinned", False) and not getattr(edited, "pinned", False):
        raise RuntimeError("Épinglage perdu : archivage bloqué")
    if edited.id != original.id or getattr(edited.photo, "id", None) != getattr(original.photo, "id", None):
        raise RuntimeError("Photo ou identifiant modifié après édition")
    raw_after = str(getattr(edited, "raw_text", "") or "")
    raw_before = str(getattr(original, "raw_text", "") or "")
    if not raw_after.startswith(raw_before):
        raise RuntimeError("Description d'origine modifiée ou perdue")
    if extra_text.strip() and extra_text.strip() not in raw_before:
        if extra_text.strip() not in raw_after:
            raise RuntimeError("Texte intermédiaire absent de la fiche éditée")
    LOG.info("CinéX : fiche d'origine #%s éditée sans nouveau message", original.id)
    return edited
