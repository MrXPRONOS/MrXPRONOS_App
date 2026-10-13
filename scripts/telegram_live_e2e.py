#!/usr/bin/env python3
"""Test réel des cinq systèmes métier Mr XPRONOS, sans doublons.

Une seule publication Telegram par système:
S1 News Football
S2 Cycle du match
S3 Data & Statistiques
S4 Communauté
S5 Médias / Viral

Le script est réservé au canal Telegram de test. Il ne touche ni à l'historique
ni aux quotas de production.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import football_channel as channel
import football_match_lifecycle as lifecycle
import football_stats_engine as stats


STAGES = (
    "S1_NEWS",
    "S2_CYCLE",
    "S3_DATA",
    "S4_COMMUNAUTE",
    "S5_VIRAL",
)


def _assert_test_route() -> None:
    test_chat = (os.getenv("TELEGRAM_TEST_CHAT_ID") or "").strip()
    active_chat = (os.getenv("FOOTBALL_NEWS_CHAT_ID") or "").strip()
    if not test_chat or active_chat != test_chat:
        raise RuntimeError(
            "Route Telegram interdite: le test doit utiliser TELEGRAM_TEST_CHAT_ID uniquement"
        )
    if os.getenv("FOOTBALL_REQUIRE_COMMENTS", "1").strip() != "0":
        raise RuntimeError("Le canal de test ne doit pas exiger de groupe de discussion")


def _tag(post: channel.Publication, label: str) -> channel.Publication:
    post.key = "e2e:" + label.casefold() + ":" + post.key
    if post.poll:
        question, options = post.poll
        post.poll = (("🧪 " + label + " • TEST\n\n" + question)[:300], options)
        post.poll_description = (
            "TEST MR XPRONOS • " + (post.poll_description or "")
        )[:1024]
        # Le test Communauté doit produire exactement un message Telegram.
        post.card = None
    else:
        post.text = "<b>🧪 " + label + " • TEST MR XPRONOS</b>\n\n" + post.text
    return post


def _news_post(news: list[dict], now: datetime) -> tuple[channel.Publication, str]:
    with tempfile.TemporaryDirectory(prefix="xpronos-e2e-news-") as tmp:
        history = channel.History(Path(tmp) / "history.json")
        post = channel.flash(news, history, now)
    if post is None:
        raise RuntimeError("S1 News: aucune actualité récente publiable")
    return _tag(post, "S1 • NEWS FOOTBALL"), "news_reelles"


def _cycle_post(sender: channel.Sender, now: datetime) -> tuple[channel.Publication, str]:
    """Exerce réellement la détection de transition avec un état contrôlé.

    Une simulation est volontairement utilisée ici: un test peut être lancé à
    n'importe quelle heure, même sans match live. Aucun faux événement n'est
    présenté comme une actualité réelle car le message est explicitement marqué TEST.
    """
    kickoff = now - timedelta(minutes=3)
    base = {
        "id": "e2e-cycle-base",
        "event_date": kickoff.isoformat(),
        "home_team": {"name": "Arsenal"},
        "away_team": {"name": "Chelsea"},
        "league_name": "Premier League",
        "status": "inprogress",
    }
    external = {
        "source": "espn",
        "id": "e2e-cycle-espn",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "home_score": 0,
        "away_score": 0,
        "minute": 3,
        "state": "in",
        "status_detail": "3'",
        "event_date": kickoff.isoformat(),
        "league": "Premier League",
    }

    original_collect = lifecycle.collect_external
    lifecycle.collect_external = lambda session, day, base_events: [external]
    try:
        signals = lifecycle.lifecycle_signals(
            [base], set(), now, sender.session, lambda _: 100
        )
    finally:
        lifecycle.collect_external = original_collect

    signal = next((item for item in signals if item.get("kind") == "kickoff"), None)
    if signal is None:
        raise RuntimeError("S2 Cycle: le moteur n'a pas généré le signal kickoff attendu")
    signal = dict(signal)
    signal["source"] = "simulation contrôlée du moteur"
    signal["key"] = "e2e-cycle:kickoff"
    post = channel.lifecycle_publication(signal)
    if post is None:
        raise RuntimeError("S2 Cycle: publication introuvable")
    return _tag(post, "S2 • CYCLE DU MATCH"), "simulation_controlee"


def _data_post(sender: channel.Sender, now: datetime) -> tuple[channel.Publication, str]:
    today = now.date()
    post = channel.statistique_avancee(sender.session, today)
    if post is not None:
        return _tag(post, "S3 • DATA & STATISTIQUES"), "insight_reel"

    health = stats.source_health(sender.session, today)
    espn_rows = int(health.get("espn_rows") or 0)
    openliga_rows = int(health.get("openliga_rows") or 0)
    if espn_rows <= 0 and openliga_rows <= 0:
        raise RuntimeError("S3 Data: aucune source statistique gratuite ne répond")

    text = (
        "<h3>📊 DATA & STATISTIQUES • CONTRÔLE SOURCES</h3>"
        "<blockquote><b>ESPN :</b> " + str(espn_rows) + " lignes vérifiées<br/>"
        "<b>OpenLigaDB :</b> " + str(openliga_rows) + " lignes vérifiées</blockquote>"
        "<p><i>Fallback de test utilisé car aucun insight éditorial n'était disponible.</i></p>"
    )
    post = channel.Publication(
        "statistique",
        "e2e:data-health:" + today.isoformat(),
        text,
    )
    return _tag(post, "S3 • DATA & STATISTIQUES"), "source_health_reel"


def _community_post(
    sender: channel.Sender, news: list[dict], now: datetime
) -> tuple[channel.Publication, str]:
    today = now.date()
    post = channel.community_quiz_publication(sender.session, today)
    mode = "quiz_reel"
    if post is None:
        post = channel.community_debate_publication(news, today)
        mode = "debat_news_reelles"
    if post is None:
        raise RuntimeError("S4 Communauté: aucun quiz ou débat réel publiable")
    return _tag(post, "S4 • COMMUNAUTÉ"), mode


def _viral_post(
    sender: channel.Sender, news: list[dict], now: datetime
) -> tuple[channel.Publication, str]:
    post = channel.viral_publication([], news, sender.session, now)
    if post is None:
        raise RuntimeError("S5 Viral: aucun payload média publiable")
    return _tag(post, "S5 • MÉDIAS / VIRAL"), "animation_originale"


def main() -> int:
    _assert_test_route()
    now = datetime.now(timezone.utc)
    sender = channel.Sender(dry_run=False)
    news = channel.load_site_news()
    if not news:
        raise RuntimeError("footnews.json est vide: S1/S4/S5 ne peuvent pas être validés")

    builders = (
        ("S1_NEWS", lambda: _news_post(news, now)),
        ("S2_CYCLE", lambda: _cycle_post(sender, now)),
        ("S3_DATA", lambda: _data_post(sender, now)),
        ("S4_COMMUNAUTE", lambda: _community_post(sender, news, now)),
        ("S5_VIRAL", lambda: _viral_post(sender, news, now)),
    )

    report = {"mode": "five-business-systems", "sent": {}, "errors": {}}
    for stage, build in builders:
        try:
            post, mode = build()
            message_id = sender.send(post)
            if not isinstance(message_id, int):
                raise RuntimeError("Telegram n'a pas confirmé de message_id")
            report["sent"][stage] = {
                "message_id": message_id,
                "category": post.category,
                "mode": mode,
            }
            print(
                "FIVE_SYSTEM_SENT",
                json.dumps(
                    {"stage": stage, "message_id": message_id,
                     "category": post.category, "mode": mode},
                    ensure_ascii=False,
                ),
                flush=True,
            )
        except Exception as exc:
            report["errors"][stage] = type(exc).__name__ + ": " + str(exc)[:220]
            print(
                "FIVE_SYSTEM_ERROR",
                json.dumps({"stage": stage, "error": report["errors"][stage]},
                           ensure_ascii=False),
                flush=True,
            )

    print("FIVE_SYSTEMS_E2E", json.dumps(report, ensure_ascii=False), flush=True)
    if report["errors"] or set(report["sent"]) != set(STAGES):
        return 1

    message_ids = [item["message_id"] for item in report["sent"].values()]
    if len(message_ids) != 5 or len(set(message_ids)) != 5:
        print("FIVE_SYSTEM_ERROR doublon_message_id", message_ids, flush=True)
        return 1
    print("FIVE_SYSTEMS_E2E_OK messages=5 doublons=0", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
