"""Safe, offline Bot API inbox for authorized source-channel announcements.

This module does NOT fetch history or publish media. Admin access and
redistribution rights must be verified before enabling a live Bot API poller.
Messages are keyed by source chat/message IDs, independent of Telegram update
delivery retries. Never guess an anime from a generic filename.
"""
from __future__ import annotations

from copy import deepcopy

from .anime_cadence import cadence_hint


def _source_ids(allowlist):
    parsed = set()
    for value in allowlist:
        text = str(value).strip()
        if not (text.startswith("-100") and text[1:].isdigit()):
            raise ValueError("Source bot autorisée : ID -100... requis.")
        parsed.add(text)
    if not parsed:
        raise ValueError("Aucune source Bot API autorisée.")
    return parsed


def _kind(message):
    if message.get("video"):
        return "video"
    doc = message.get("document") or {}
    mime = str(doc.get("mime_type") or "")
    if mime.startswith("video/"):
        return "video"
    if message.get("animation") or mime == "image/gif":
        return "animation"
    if message.get("photo"):
        return "poster"
    if message.get("text"):
        return "text"
    return None


def _media_file(message, kind):
    if kind == "video":
        return message.get("video") or message.get("document") or {}
    if kind == "animation":
        return message.get("animation") or message.get("document") or {}
    if kind == "poster":
        return (message.get("photo") or [{}])[-1]
    return {}


def ingest_channel_updates(updates: list, previous: dict,
                           authorized_source_ids, *, max_messages=50000):
    """Produce a durable inbox snapshot without posting, fetching or guessing.

    Bot API getUpdates offset must be advanced only AFTER the returned inbox
    has been committed. Edits keep one identity and update its metadata.
    Invalid or unauthorized messages are skipped without persisting contents.
    """
    allowed = _source_ids(authorized_source_ids)
    state = deepcopy(previous or {})
    state.setdefault("schema_version", 1)
    messages = state.setdefault("messages", {})
    cursor = int(state.get("last_update_id", -1))
    summary = {"accepted": 0, "repeated": 0, "unauthorized": 0,
               "skipped": 0, "edited": 0}
    for update in sorted(updates, key=lambda item: int(item.get("update_id", -1))):
        update_id = int(update.get("update_id", -1))
        if update_id <= cursor:
            summary["repeated"] += 1
            continue
        event = update.get("channel_post") or update.get("edited_channel_post")
        if not isinstance(event, dict):
            summary["skipped"] += 1
            cursor = update_id
            continue
        chat = event.get("chat") or {}
        source_id = str(chat.get("id") or "")
        if source_id not in allowed:
            summary["unauthorized"] += 1
            cursor = update_id
            continue
        if event.get("has_protected_content"):
            summary["skipped"] += 1
            cursor = update_id
            continue
        message_id = int(event.get("message_id") or 0)
        kind = _kind(event)
        if message_id <= 0 or not kind:
            summary["skipped"] += 1
            cursor = update_id
            continue
        key = f"{source_id}:{message_id}"
        is_edit = "edited_channel_post" in update
        payload = _media_file(event, kind)
        caption = str(event.get("caption") or event.get("text") or "")[:2000]
        filename = str(payload.get("file_name") or "")[:240]
        record = {
            "source_id": source_id, "message_id": message_id,
            "kind": kind, "text": caption, "filename": filename,
            "file_id": str(payload.get("file_id") or ""),
            "file_unique_id": str(payload.get("file_unique_id") or ""),
            "date": int(event.get("date") or 0),
            "cadence_hint": cadence_hint(caption + " " + filename),
            "status": "pending",
        }
        if key in messages:
            old = messages[key]
            record["status"] = old.get("status", "pending")
            if is_edit:
                messages[key] = record
                summary["edited"] += 1
            else:
                summary["repeated"] += 1
        else:
            if len(messages) >= max_messages:
                # No silent data loss, and caller must NOT advance getUpdates
                # offset until it can save every update in the current batch.
                raise RuntimeError("File des sources bot pleine : aucun curseur avancé.")
            messages[key] = record
            summary["accepted"] += 1
        cursor = update_id
    state["last_update_id"] = cursor
    return state, summary
