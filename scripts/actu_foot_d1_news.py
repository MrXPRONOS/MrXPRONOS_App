#!/usr/bin/env python3
"""Publish verified football RSS news on Telegram with Cloudflare D1 deduplication.

RSS articles are collected by fetch_foot_news.py.  Only text actually provided
by the feed/its public summary is shown; article sites are not copied.
A post starts with its headline and ends with the category and media name.
No article links or CTA buttons are exposed to subscribers.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

import requests
from PIL import Image, ImageOps

from d1_publication_ledger import D1Ledger
from telegram_rich import post_photo, post_text
from football_rss_editor import prepare, EditorialHold

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILE = ROOT / "telegram_out" / "actu_foot_source_news.json"
# Keep the historical article kind to prevent republishing earlier posts.
KIND = "actu_foot_flash_v2"
SLOT_KIND = "actu_foot_flash_30m_slot_v3"
DAILY_KIND = "actu_foot_flash_daily_quota_v3"
MAX_POSTS_PER_RUN = 2
MAX_POSTS_PER_DAY = 24
MAX_PHOTO_CAPTION_CHARS = 900  # Telegram legacy photo captions: 1024 chars.
MAX_TEXT_CHARS = 3500          # Telegram legacy sendMessage: 4096 chars.


def _time(value):
    try:
        value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _safe_url(value):
    try:
        parts = urlsplit(str(value or "").strip())
        return parts.scheme == "https" and bool(parts.hostname) and not parts.username and not parts.password
    except ValueError:
        return False


def clean_visible_text(value):
    """Remove all visible URLs while keeping readable RSS/Markdown anchor labels."""
    text = html.unescape(str(value or ""))
    text = re.sub(r"(?is)<a\b[^>]*>(.*?)</a>", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(\s*https?://[^)]+\)", r"\1", text)
    text = re.sub(r"(?i)(?:https?://|www\.)[^\s<>\]\)]+", "", text)
    text = re.sub(r"(?is)<[^>]*>", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def story_parts(item):
    title = clean_visible_text(item.get("telegram_title_fr") or item.get("title"))[:220]
    title = re.sub(r"(?i)^(?:⚽\s*)?(?:actu\s*foot|flash\s*foot)\s*[:|–—-]\s*", "", title).strip()
    content = clean_visible_text(
        item.get("telegram_content_fr") or item.get("content") or item.get("telegram_summary") or item.get("summary")
    )
    # Avoid starting the body by repeating the identical headline.
    if content.casefold().startswith(title.casefold()) and title:
        content = content[len(title):].lstrip(" \n.:;–—-")
    category = clean_visible_text(item.get("category") or "Actualité")[:65]
    source = clean_visible_text(item.get("source") or "Source football")[:90]
    return title, content, category, source


def _chunks(text, size=MAX_TEXT_CHARS):
    """Break long, source-provided RSS descriptions without losing their ending."""
    remainder = text.strip()
    while remainder:
        if len(remainder) <= size:
            yield remainder
            break
        cut = remainder.rfind("\n\n", 0, size)
        if cut < size // 3:
            cut = remainder.rfind(" ", 0, size)
        if cut < size // 3:
            cut = size
        part = remainder[:cut].strip()
        if part:
            yield part
        remainder = remainder[cut:].strip()


def select_stories(news, now, *, max_age_hours=48):
    """Only real sourced RSS news with a real photo or a marked general banner."""
    choices = []
    for item in news if isinstance(news, list) else []:
        if not isinstance(item, dict):
            continue
        stamp = _time(item.get("published"))
        if stamp is None or not now - timedelta(hours=max_age_hours) <= stamp <= now + timedelta(minutes=10):
            continue
        title, content, _, _ = story_parts(item)
        link = str(item.get("link") or item.get("source_url") or "").strip()
        slug = str(item.get("slug") or hashlib.sha256(link.encode()).hexdigest()[:24]).strip()
        image = str(item.get("image") or "").strip()
        path = (ROOT / image).resolve()
        origin = str(item.get("image_origin") or "")
        try:
            editorial = int(item.get("editorial_score") or 0)
        except (ValueError, TypeError):
            editorial = 0
        has_valid_image = origin == "source" or (origin == "generated_fallback" and editorial >= 4)
        if (not title or not content or not _safe_url(link)
                or not slug or len(slug) > 100
                or not has_valid_image
                or not image.startswith("assets/images/footnews/")
                or not path.is_relative_to(ROOT.resolve()) or not path.is_file()):
            continue
        choices.append((stamp, item, path, slug, link))
    choices.sort(key=lambda x: (x[0], int(x[1].get("editorial_score") or 0)), reverse=True)
    return choices


def send_article(session, token, chat, item, image_path, link):
    """Send full RSS-provided description (not the website article), without links.

    For the rare description exceeding Telegram's 1024-character photo caption,
    the source photo is followed by text continuation(s). A failure after the
    photo is quarantined by the caller's D1 claim, never silently resent.
    """
    title, content, category, source = story_parts(item)
    footer = "\n\n<i>Catégorie : " + html.escape(category) + "\nSource : " + html.escape(source) + "</i>"
    headline = "<b>" + html.escape(title) + "</b>"
    full = headline + "\n\n" + html.escape(content) + footer

    with TemporaryDirectory(prefix="actu-foot-d1-") as folder:
        dest = Path(folder) / "actu-foot.jpg"
        with Image.open(image_path) as raw:
            ImageOps.exif_transpose(raw).convert("RGB").save(dest, "JPEG", quality=89, optimize=True)
        if len(title) + len(content) + len(category) + len(source) + 25 <= MAX_PHOTO_CAPTION_CHARS:
            return post_photo(session, token, chat, dest, full, None, timeout=80, mime="image/jpeg")

        # In long posts the picture carries only the headline, not an
        # incomplete teaser. Every remaining paragraph is delivered as text.
        photo_id = post_photo(session, token, chat, dest, headline, None, timeout=80, mime="image/jpeg")
        chunks = list(_chunks(content, MAX_TEXT_CHARS - 200))
        for index, part in enumerate(chunks):
            tail = footer if index == len(chunks) - 1 else ""
            post_text(session, token, chat, html.escape(part) + tail,
                      keyboard=None, timeout=60, html=True)
        return photo_id


def dispatch(news, now, *, dry_run, token=None, chat=None, ledger=None, session=None):
    now = now.astimezone(timezone.utc)
    report = {"eligible": 0, "sent": 0, "already_sent": 0, "errors": 0, "no_fresh_news": False}
    stories = select_stories(news, now)
    report["eligible"] = len(stories)
    if not stories:
        report["no_fresh_news"] = True
        return report
    if dry_run:
        report["would_send"] = stories[0][3]
        report["would_send_ids"] = [story[3] for story in stories[:MAX_POSTS_PER_RUN]]
        return report
    if not (token and chat):
        raise RuntimeError("FOOTBALL_NEWS_BOT_TOKEN/FOOTBALL_NEWS_CHAT_ID manquants")

    ledger = ledger or D1Ledger()
    session = session or requests.Session()
    day = now.date().isoformat()
    # Daily reservations, including uncertain deliveries, count against the cap.
    used_daily = {
        str(row.get("ref_id") or "")
        for row in ledger.rows(DAILY_KIND, day)
        if str(row.get("ref_id") or "").startswith(str(chat) + ":")
    }
    sent_this_run = set()
    report["editorial_skipped"] = 0

    for stamp, item, image, slug, link in stories:
        if report["sent"] >= MAX_POSTS_PER_RUN:
            break
        if len(used_daily) >= MAX_POSTS_PER_DAY:
            report["daily_limit_reached"] = True
            break

        article_day = stamp.date().isoformat()
        ref = str(chat) + ":" + slug
        if ref in sent_this_run or ledger.rows(KIND, article_day, ref_id=ref):
            report["already_sent"] += 1
            continue

        # Editorial verification MUST precede D1 claims; no slot is wasted
        # on clipped, untranslatable or unverifiable RSS stories.
        try:
            edited_item = prepare(item, session=session)
        except EditorialHold:
            report["editorial_skipped"] += 1
            continue

        # Each 30-minute run has two independent, durable publication slots.
        slot = f"{chat}:{day}:{now.hour:02d}:{now.minute // 30}:{report['sent']}"
        if not ledger.claim(SLOT_KIND, slot, day):
            report["slot_already_claimed"] = True
            break
        daily_ref = next(
            (f"{chat}:{i:02d}" for i in range(MAX_POSTS_PER_DAY)
             if f"{chat}:{i:02d}" not in used_daily), None
        )
        if daily_ref is None or not ledger.claim(DAILY_KIND, daily_ref, day):
            report["daily_limit_reached"] = True
            break
        used_daily.add(daily_ref)
        if not ledger.claim(KIND, ref, article_day):
            report["already_sent"] += 1
            continue
        try:
            msg = send_article(session, token, chat, edited_item, image, link)
            ledger.mark(KIND, ref, article_day, message_id=msg)
            ledger.mark(SLOT_KIND, slot, day, message_id=msg)
            ledger.mark(DAILY_KIND, daily_ref, day, message_id=msg)
            report["sent"] += 1
            report["telegram_message_id"] = msg
            report["story_slug"] = slug
            sent_this_run.add(ref)
        except Exception as error:
            # A Telegram request may have succeeded even if its receipt failed.
            # Retain all reservations for manual reconciliation, without retry.
            report["errors"] += 1
            report["error_type"] = type(error).__name__
            break
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--news", type=Path, default=DEFAULT_FILE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.news.is_file():
        raise RuntimeError("Actu Foot source feed not produced; publication blocked")
    news = json.loads(args.news.read_text(encoding="utf-8"))
    if not isinstance(news, list):
        raise RuntimeError("Actu Foot feed malformed")
    report = dispatch(
        news, datetime.now(timezone.utc), dry_run=args.dry_run,
        token=os.getenv("FOOTBALL_NEWS_BOT_TOKEN"),
        chat=os.getenv("FOOTBALL_NEWS_CHAT_ID"),
    )
    print("ACTU_FOOT_D1_TELEGRAM", json.dumps(report, ensure_ascii=False))
    if report["errors"]:
        raise SystemExit("Actu Foot Telegram delivery failed; D1 claims retained")


if __name__ == "__main__":
    main()
