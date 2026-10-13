#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collecteur commun News Football -> site Infos Foot + Telegram Actu Foot.

Aucune API payante. Les flux sont des RSS publics français; les métadonnées
og:image/og:description ne sont utilisées qu'en complément lorsqu'un flux est
incomplet. Aucun fait absent des sources n'est inventé.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin

import feedparser
import requests

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
from football_news_engine import (  # noqa: E402
    DEFAULT_FREE_FEEDS,
    build_news_record,
    classify_news,
    cleanup_orphan_images,
    download_real_image,
    extract_entry_image,
    feed_entry_text,
    fetch_open_graph,
    normalize_title,
    source_profile,
)

NEWS_FILE = ROOT / "footnews.json"
PRIMARY_FEED = (os.getenv("FOOTBALL_RSS_FEED") or "").strip()
EXTRA_FEEDS = tuple(
    x.strip()
    for x in (os.getenv("EXTRA_FOOTBALL_RSS_FEEDS") or "").split(",")
    if x.strip()
)
MAX_ARTICLES = max(10, min(120, int(os.getenv("MAX_ARTICLES", "60"))))
MAX_PER_FEED = max(5, min(30, int(os.getenv("MAX_ARTICLES_PER_FEED", "16"))))
MAX_NEWS_AGE_HOURS = max(12, min(336, int(os.getenv("MAX_NEWS_AGE_HOURS", "120"))))
RSS_TIMEOUT = max(4, min(40, int(os.getenv("RSS_TIMEOUT", "18"))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mrxpronos.news")


def feed_urls() -> list[str]:
    ordered = []
    for url in ((PRIMARY_FEED,) if PRIMARY_FEED else ()) + DEFAULT_FREE_FEEDS + EXTRA_FEEDS:
        if url and url not in ordered:
            ordered.append(url)
    return ordered


def entry_date(entry) -> datetime:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass
    raw = entry.get("published") or entry.get("updated") or entry.get("pubDate")
    if raw:
        try:
            dt = parsedate_to_datetime(str(raw))
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
        except (TypeError, ValueError, IndexError):
            try:
                dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
            except (TypeError, ValueError):
                pass
    return datetime.now(timezone.utc)


def safe_link(value: str) -> str:
    link = str(value or "").strip()
    if link.startswith("http://"):
        host = (urlparse(link).hostname or "").lower()
        # Les médias ci-dessous servent aussi leurs pages en HTTPS.
        if host.endswith(("maxifoot.com", "maxifoot.fr", "sofoot.com")):
            link = "https://" + link[7:]
    return link if link.startswith("https://") else ""


def similarity(a: str, b: str) -> float:
    aa, bb = set(a.split()), set(b.split())
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(len(aa | bb), 1)


def old_records() -> dict[str, dict]:
    try:
        data = json.loads(NEWS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {
        str(item.get("link")): item
        for item in data
        if isinstance(item, dict) and item.get("link")
    }


def reuse_image(previous: dict) -> tuple[str, str, str]:
    image = str(previous.get("image") or "")
    if image.startswith("assets/images/footnews/") and (ROOT / image).is_file():
        return image, str(previous.get("image_layout") or "smart-crop"), str(previous.get("source_image") or "")
    return "", "", ""


def fetch_news() -> tuple[list[dict], dict]:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "MrXPRONOS-NewsBot/3.0 RSS Reader (+https://mrxpronos.github.io/MrXPRONOS_App/)"
    })
    previous = old_records()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MAX_NEWS_AGE_HOURS)
    candidates: list[dict] = []
    diagnostics = {
        "feeds": {},
        "accepted_before_dedup": 0,
        "rejected_stale": 0,
        "rejected_invalid": 0,
        "images_real": 0,
        "images_missing": 0,
        "rejected_no_image": 0,
    }

    for feed_url in feed_urls():
        profile = source_profile(feed_url)
        stat = {"status": "ok", "entries": 0, "eligible": 0, "real_images": 0}
        diagnostics["feeds"][profile.name + " | " + feed_url] = stat
        try:
            response = session.get(feed_url, timeout=(7, RSS_TIMEOUT), allow_redirects=True)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
        except (requests.RequestException, ValueError) as exc:
            stat["status"] = "unavailable:" + type(exc).__name__
            continue
        entries = list(feed.entries or [])
        stat["entries"] = len(entries)
        if not entries:
            stat["status"] = "empty"
            continue

        profile = source_profile(feed_url, str(feed.feed.get("title") or ""))
        for entry in entries[:MAX_PER_FEED]:
            title = re.sub(r"\s+", " ", str(entry.get("title") or "")).strip()
            link = safe_link(entry.get("link"))
            if not title or not link:
                diagnostics["rejected_invalid"] += 1
                continue
            published_dt = entry_date(entry)
            if published_dt < cutoff or published_dt > now + timedelta(hours=3):
                diagnostics["rejected_stale"] += 1
                continue

            body = feed_entry_text(entry)
            source_image = extract_entry_image(entry)
            if source_image:
                source_image = urljoin(link, source_image)
            # Une seule lecture légère de la page source si le RSS manque de texte ou d'image.
            metadata = {}
            if len(body) < 120 or not source_image:
                metadata = fetch_open_graph(session, link, RSS_TIMEOUT)
            meta_description = str(metadata.get("description") or "").strip()
            if len(meta_description) > len(body):
                body = meta_description
            if not source_image:
                source_image = str(metadata.get("image") or "").strip()
                if source_image:
                    source_image = urljoin(link, source_image)
            if not body:
                diagnostics["rejected_invalid"] += 1
                continue

            slug = hashlib.sha1(link.encode("utf-8")).hexdigest()[:16]
            image_path, image_mode, previous_source = reuse_image(previous.get(link) or {})
            if image_path and not source_image:
                source_image = previous_source

            category, editorial_score = classify_news(title, body, feed_url)
            record = build_news_record(
                slug=slug,
                title=title,
                body=body,
                link=link,
                published=published_dt.isoformat(),
                source=profile,
                feed_url=feed_url,
                image_path=image_path,
                source_image=source_image,
                image_mode=image_mode,
                category=category,
                editorial_score=editorial_score,
            )
            candidates.append(record)
            stat["eligible"] += 1

    diagnostics["accepted_before_dedup"] = len(candidates)
    candidates.sort(
        key=lambda item: (
            str(item.get("published") or ""),
            int(item.get("editorial_score") or 0),
            int(item.get("source_priority") or 0),
        ),
        reverse=True,
    )

    selected: list[dict] = []
    title_keys: list[str] = []
    links = set()
    for item in candidates:
        link = str(item.get("link") or "")
        norm = normalize_title(str(item.get("title") or ""))
        if not norm or link in links:
            continue
        # Les mêmes annonces publiées par plusieurs médias ne doivent pas saturer Actu Foot.
        if any(similarity(norm, older) >= 0.78 for older in title_keys[-80:]):
            continue

        # Télécharger seulement après déduplication : moins de requêtes et de stockage.
        image_path = str(item.get("image") or "")
        if not (item.get("image_origin") == "source" and image_path.startswith("assets/images/footnews/") and (ROOT / image_path).is_file()):
            image_path, image_mode = download_real_image(
                session,
                str(item.get("source_image") or ""),
                str(item.get("slug") or ""),
                root=ROOT,
            )
            if image_path:
                item["image"] = image_path
                item["image_origin"] = "source"
                item["image_layout"] = image_mode
        if item.get("image_origin") != "source":
            diagnostics["rejected_no_image"] += 1
            diagnostics["images_missing"] += 1
            continue

        diagnostics["images_real"] += 1
        selected.append(item)
        links.add(link)
        title_keys.append(norm)
        if len(selected) >= MAX_ARTICLES:
            break

    diagnostics["selected"] = len(selected)
    diagnostics["orphan_images_removed"] = cleanup_orphan_images(selected, ROOT)
    return selected, diagnostics


def save_news(records: list[dict], diagnostics: dict | None = None) -> None:
    if not records:
        raise RuntimeError("Aucune actualité exploitable : conservation du footnews.json existant")
    NEWS_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("NEWS_ENGINE %s", json.dumps(diagnostics or {}, ensure_ascii=False))
    logger.info("%s actualités sauvegardées dans %s", len(records), NEWS_FILE)


def main() -> None:
    records, diagnostics = fetch_news()
    save_news(records, diagnostics)


if __name__ == "__main__":
    main()
