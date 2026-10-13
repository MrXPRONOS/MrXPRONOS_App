#!/usr/bin/env python3
"""Test visuel S5 Médias/Viral, exclusivement dans @predict_mrxp."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import football_channel as channel
from football_viral_engine import render_animation

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "viral-preview.gif"


def main() -> int:
    test_chat = (os.getenv("TELEGRAM_TEST_CHAT_ID") or "").strip()
    active_chat = (os.getenv("FOOTBALL_NEWS_CHAT_ID") or "").strip()
    if not test_chat or active_chat != test_chat:
        raise RuntimeError("S5 visual test: destination Telegram de test non verrouillée")
    if os.getenv("FOOTBALL_REQUIRE_COMMENTS", "1").strip() != "0":
        raise RuntimeError("S5 visual test: commentaires doivent être désactivés")

    sender = channel.Sender(dry_run=False)
    sender.verify_discussion()
    news = channel.load_site_news()
    if not news:
        raise RuntimeError("S5 visual test: aucune News Football disponible")

    now = datetime.now(timezone.utc)
    post = channel.viral_publication([], news, sender.session, now)
    if post is None or not post.animation_payload:
        raise RuntimeError("S5 visual test: aucun payload viral généré")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    render_animation(post.animation_payload, OUTPUT, sender.session)

    caption = (
        "<b>🧪 S5 • MÉDIAS / VIRAL • TEST VISUEL MR XPRONOS</b>\n\n"
        + post.text
    )[:1000]
    message_id = channel.post_animation(
        sender.session,
        sender.token,
        sender.chat,
        OUTPUT,
        caption,
        post.keyboard or {},
        timeout=120,
        mime="image/gif",
    )
    if not isinstance(message_id, int):
        raise RuntimeError("S5 visual test: Telegram n'a pas confirmé le message_id")

    payload = {
        "message_id": message_id,
        "kind": post.animation_payload.get("kind"),
        "title": post.animation_payload.get("title")
            or post.animation_payload.get("headline")
            or "",
        "output": str(OUTPUT.relative_to(ROOT)),
        "size": OUTPUT.stat().st_size,
    }
    print("VIRAL_VISUAL_TEST_OK", json.dumps(payload, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
