#!/usr/bin/env python3
"""Test réel des cinq systèmes Actu Foot vers le canal Telegram de test uniquement.

Aucun historique/quotas de production n'est modifié.
Les publications sont préfixées [TEST SYSTÈME X].
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "bsd"))

from bsd_api import BSDClient, BSDAPIError  # noqa: E402
from football_match_lifecycle import lifecycle_signals  # noqa: E402
from football_channel import (  # noqa: E402
    History,
    Publication,
    Sender,
    candidates,
    community_quiz_publication,
    community_vote_publication,
    final_score,
    flash,
    importance,
    kick,
    lifecycle_publication,
    load_site_news,
    plain,
    statistique,
    statistique_avancee,
    team,
    league,
    viral_publication,
)

SYSTEM_NAMES = {
    1: "NEWS FOOTBALL",
    2: "CYCLE DU MATCH",
    3: "DATA & STATISTIQUES",
    4: "COMMUNAUTÉ",
    5: "MÉDIAS / VIRAL",
}


def tag_publication(item: Publication, system_no: int, *, simulation: bool = False) -> Publication:
    label = f"🧪 <b>TEST SYSTÈME {system_no} — {SYSTEM_NAMES[system_no]}</b>"
    if simulation:
        label += "\n⚠️ <b>SIMULATION VISUELLE</b> — ce message ne décrit pas un événement live en cours."
    if item.poll:
        question, options = item.poll
        prefix = f"[TEST SYSTÈME {system_no}] "
        if simulation:
            prefix += "[SIMULATION] "
        item.poll = ((prefix + question)[:300], options)
        item.poll_description = (
            f"TEST SYSTÈME {system_no} • {SYSTEM_NAMES[system_no]} • "
            + plain(item.poll_description, 700)
        )[:1024]
    else:
        item.text = label + "\n\n" + item.text
    item.key = f"test-system-{system_no}:" + item.key
    return item


def fetch_day(api: BSDClient, day: date) -> list[dict]:
    page = api.list_events(day, day, max_pages=8, ttl=0)
    if not page.complete:
        raise BSDAPIError("Liste BSD incomplète " + day.isoformat())
    print("TEST_DAY", day.isoformat(), "events", len(page.events))
    return page.events


def choose_real_fixture(events: list[dict], now: datetime) -> dict | None:
    pool = [
        e for e in candidates(events)
        if kick(e) and final_score(e) is None and kick(e) >= now - timedelta(hours=2)
    ]
    if not pool:
        pool = candidates(events)
    return pool[0] if pool else None


def system1(sender: Sender, history: History, now: datetime) -> Publication | None:
    news = load_site_news()
    post = flash(news, history, now)
    if post:
        return tag_publication(post, 1)

    # Repli : utiliser la news réelle la plus récente même si elle se trouve
    # hors de la fenêtre éditoriale du Flash automatique.
    for article in news:
        image_path = str(article.get("image") or "")
        if article.get("image_origin") != "source":
            continue
        if not image_path.startswith("assets/images/footnews/"):
            continue
        if not (ROOT / image_path).is_file():
            continue
        title = plain(article.get("title"), 240)
        summary = plain(article.get("telegram_summary") or article.get("summary"), 430)
        source = plain(article.get("source") or "Source football", 80)
        site_url = plain(article.get("site_url"), 500)
        if not title or not summary:
            continue
        text = (
            "<b>📰 FLASH FOOT</b>\n\n"
            "<b>" + title + "</b>\n\n"
            "<blockquote>" + summary + "</blockquote>\n\n"
            "<i>🗞️ Source : " + source + "</i>"
        )
        keyboard = None
        if site_url.startswith("https://"):
            keyboard = {"inline_keyboard": [[{
                "text": "Lire l’info complète ↗",
                "url": site_url,
                "style": "primary",
            }]]}
        return tag_publication(
            Publication("flash", "fallback:" + plain(article.get("slug"), 90),
                        text, image_path=image_path, keyboard=keyboard),
            1,
        )
    return None


def system2(
    sender: Sender,
    api: BSDClient,
    events: list[dict],
    now: datetime,
) -> Publication | None:
    # Priorité à une vraie transition live si une source gratuite en remonte une.
    try:
        signals = lifecycle_signals(events, set(), now, sender.session, importance)
    except Exception as exc:
        print("TEST_SYSTEM2_LIVE_LOOKUP_ERROR", type(exc).__name__, str(exc)[:180])
        signals = []
    for signal in signals:
        post = lifecycle_publication(signal)
        if post:
            return tag_publication(post, 2)

    # S'il n'y a aucun match live au moment précis du test, on valide quand même
    # le rendu avec une vraie affiche BSD, mais le message est explicitement
    # marqué SIMULATION VISUELLE pour ne pas créer de faux fait sportif.
    fixture = choose_real_fixture(events, now)
    if fixture is None:
        return None
    signal = {
        "kind": "kickoff",
        "key": "visual:" + str(fixture.get("id") or ""),
        "home": team(fixture, "home"),
        "away": team(fixture, "away"),
        "league": league(fixture) or "Football",
        "minute": 1,
        "score": "0-0",
        "source": "BSD V2 • simulation de rendu",
    }
    post = lifecycle_publication(signal)
    return tag_publication(post, 2, simulation=True) if post else None


def system3(
    sender: Sender,
    events_by_day: dict[date, list[dict]],
    now: datetime,
) -> Publication | None:
    for offset in (0, -1, -2):
        day = now.date() + timedelta(days=offset)
        try:
            post = statistique_avancee(sender.session, day)
        except Exception as exc:
            print("TEST_SYSTEM3_ADVANCED_ERROR", day, type(exc).__name__, str(exc)[:180])
            post = None
        if post:
            return tag_publication(post, 3)

    for day in sorted(events_by_day.keys(), reverse=True):
        try:
            post = statistique(events_by_day[day], day)
        except Exception as exc:
            print("TEST_SYSTEM3_BSD_ERROR", day, type(exc).__name__, str(exc)[:180])
            post = None
        if post:
            return tag_publication(post, 3)
    return None


def system4(
    sender: Sender,
    events: list[dict],
    now: datetime,
) -> Publication | None:
    # Le quiz valide le format Telegram quiz + réponse correcte.
    for offset in (0, -1, 1):
        try:
            post = community_quiz_publication(sender.session, now.date() + timedelta(days=offset))
        except Exception as exc:
            print("TEST_SYSTEM4_QUIZ_ERROR", type(exc).__name__, str(exc)[:180])
            post = None
        if post:
            return tag_publication(post, 4)

    post = community_vote_publication(events, now)
    return tag_publication(post, 4) if post else None


def system5(sender: Sender, events: list[dict], now: datetime) -> Publication | None:
    post = viral_publication(events, load_site_news(), sender.session, now)
    return tag_publication(post, 5) if post else None


def main() -> int:
    # Sécurité : le workflow doit fournir explicitement le canal de test.
    chat = (os.getenv("FOOTBALL_NEWS_CHAT_ID") or "").strip()
    prod = (os.getenv("PROD_FOOTBALL_NEWS_CHAT_ID") or "").strip()
    if not chat:
        raise RuntimeError("FOOTBALL_NEWS_CHAT_ID de test manquant")
    if prod and chat == prod:
        raise RuntimeError("Sécurité: le canal de test pointe vers le canal de production")

    now = datetime.now(timezone.utc)
    sender = Sender(dry_run=False)
    api = BSDClient(
        max_requests=int(os.getenv("FOOTBALL_BSD_REQUEST_BUDGET", "24")),
        max_retries=1,
    )

    report: dict[str, Any] = {"sent": {}, "errors": {}, "skipped": {}}

    with tempfile.TemporaryDirectory(prefix="xpronos-systems-1-5-") as tmp:
        history = History(Path(tmp) / "test-history.json")

        days = [
            now.date() - timedelta(days=2),
            now.date() - timedelta(days=1),
            now.date(),
            now.date() + timedelta(days=1),
        ]
        events_by_day: dict[date, list[dict]] = {}
        for day in days:
            try:
                events_by_day[day] = fetch_day(api, day)
            except Exception as exc:
                print("TEST_DAY_ERROR", day, type(exc).__name__, str(exc)[:180])
                events_by_day[day] = []

        today_and_tomorrow = events_by_day[now.date()] + events_by_day[now.date() + timedelta(days=1)]
        recent_and_future = sum((events_by_day[d] for d in days), [])

        makers = {
            1: lambda: system1(sender, history, now),
            2: lambda: system2(sender, api, today_and_tomorrow, now),
            3: lambda: system3(sender, events_by_day, now),
            4: lambda: system4(sender, today_and_tomorrow, now),
            5: lambda: system5(sender, recent_and_future, now),
        }

        for number in range(1, 6):
            print("\n" + "=" * 72)
            print("START_TEST_SYSTEM", number, SYSTEM_NAMES[number])
            try:
                post = makers[number]()
                if post is None:
                    report["skipped"][str(number)] = "Aucun contenu exploitable"
                    print("SKIP_TEST_SYSTEM", number)
                    continue
                message_id = sender.send(post)
                report["sent"][str(number)] = {
                    "name": SYSTEM_NAMES[number],
                    "message_id": message_id,
                    "category": post.category,
                }
                print("OK_TEST_SYSTEM", number, message_id)
            except Exception as exc:
                report["errors"][str(number)] = type(exc).__name__ + ": " + str(exc)[:240]
                print("ERROR_TEST_SYSTEM", number, report["errors"][str(number)])

    print("XPRONOS_SYSTEMS_1_5_TEST", json.dumps(report, ensure_ascii=False))
    if report["errors"] or report["skipped"] or len(report["sent"]) != 5:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
