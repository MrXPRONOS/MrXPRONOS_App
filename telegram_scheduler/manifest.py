"""Strict, offline validation for scheduled publishing manifests."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

KINDS = {"text", "image", "video", "document"}
MAX_POSTS = 500


def load_manifest(filename, *, now=None, root=None):
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    base = (root or Path.cwd()).resolve()
    path = Path(filename).resolve()
    if not path.is_file():
        raise ValueError("Manifest does not exist")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("horizon_hours") not in (24, 168):
        raise ValueError("Invalid manifest horizon")
    rows = data.get("posts")
    if not isinstance(rows, list) or not (0 < len(rows) <= MAX_POSTS):
        raise ValueError("Invalid manifest size")
    horizon = int(data["horizon_hours"])
    result, unique = [], set()
    for raw in rows:
        if not isinstance(raw, dict) or set(raw) - {"peer", "at", "key", "text", "file", "kind", "parse_mode"}:
            raise ValueError("Invalid manifest post")
        if isinstance(raw.get("peer"), bool):
            raise ValueError("Invalid peer")
        peer = int(raw["peer"])
        if peer >= 0:
            raise ValueError("Expected Telegram marked channel/chat ID")
        key = str(raw["key"]).strip()
        if not key or len(key) > 256:
            raise ValueError("Invalid stable key")
        value = str(raw["at"])
        slot = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if slot.tzinfo is None or slot.utcoffset() is None:
            raise ValueError("UTC-aware slot required")
        slot = slot.astimezone(timezone.utc)
        if slot.microsecond or slot < now + timedelta(minutes=3) or slot >= now + timedelta(hours=horizon):
            raise ValueError("Slot is too close or outside rolling horizon")
        kind = str(raw.get("kind") or "text")
        if kind not in KINDS:
            raise ValueError("Unsupported media type")
        text = str(raw.get("text") or "")
        parse_mode = raw.get("parse_mode")
        if parse_mode not in (None, "html"):
            raise ValueError("Unsupported markup")
        file = raw.get("file")
        if kind == "text":
            if file is not None or not text:
                raise ValueError("Invalid text post")
            if len(text) > 4096:
                raise ValueError("Telegram text limit")
        else:
            if not isinstance(file, str) or not file:
                raise ValueError("Media path required")
            file_path = (base / file).resolve()
            if not file_path.is_relative_to(base) or not file_path.is_file():
                raise ValueError("Media missing or outside approved repository")
            if file_path.stat().st_size < 1:
                raise ValueError("Empty media")
            if len(text) > 1024:
                raise ValueError("Telegram media caption limit")
            file = str(file_path)
        identity = (peer, slot, key)
        if identity in unique:
            raise ValueError("Duplicate manifest key for a slot")
        unique.add(identity)
        result.append({"peer": peer, "at": slot, "key": key, "text": text,
                       "kind": kind, "file": file, "parse_mode": parse_mode})
    return horizon, sorted(result, key=lambda x: (x["at"], x["peer"], x["key"]))


def queue_counts(rows):
    return Counter(row["peer"] for row in rows)
