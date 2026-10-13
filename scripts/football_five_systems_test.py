#!/usr/bin/env python3
"""Revue visuelle des cinq moteurs Actu Foot dans @predict_mrxp uniquement.

Aucune modification de l'historique ni du canal de production.
Les scénarios historiques sont explicitement indiqués. Jamais de score ou buteur inventé.
"""
from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "bsd"))

import requests
import football_channel as ch
import football_match_lifecycle as lifecycle
from free_football_sources import collect_free_day, merge_provider_matches
from telegram_test_guard import validate_test_channel

CATEGORIES = (
    "programme", "avant_match", "resultat", "statistique", "flash", "sondage",
    "composition", "kickoff", "goal", "mi_temps", "score_update",
    "statistique_avancee", "community_vote", "quiz", "debat",
    "reaction", "viral_news", "viral_match", "viral_stat",
)


def main() -> int:
    import os
    chat = os.environ.get("FOOTBALL_NEWS_CHAT_ID", "")
    expected = os.environ.get("TELEGRAM_TEST_CHAT_ID", "")
    token = os.environ.get("FOOTBALL_NEWS_BOT_TOKEN", "")
    guard = validate_test_channel(chat, token)
    if chat.strip() != expected.strip() or guard["username"] != "predict_mrxp":
        raise RuntimeError("Refus: destination test non vérifiée")
    os.environ["FOOTBALL_REQUIRE_COMMENTS"] = "0"
    now = datetime.now(timezone.utc)
    today = now.date()
    sender = ch.Sender(dry_run=False)
    session = sender.session
    sent: dict[str, Any] = {}
    unavailable: dict[str, str] = {}
    errors: dict[str, str] = {}
    cache: dict[str, list[dict]] = {}
    api = None

    def matches(day):
        nonlocal api
        key = day.isoformat()
        if key not in cache:
            free_rows = merge_provider_matches(
                lifecycle.fetch_espn_day(session, day)
                + collect_free_day(session, day)
            )
            if len(free_rows) >= 6:
                cache[key] = free_rows
                print("TEST_SOURCE_FREE", key, len(free_rows), flush=True)
            else:
                if api is None:
                    api = ch.BSDClient(max_requests=45, max_retries=1)
                page = api.list_events(day, day, max_pages=8, ttl=0)
                if not page.complete:
                    if free_rows:
                        cache[key] = free_rows
                        print("TEST_SOURCE_FREE_PARTIAL", key, len(free_rows), flush=True)
                    else:
                        raise RuntimeError("Calendrier multi-source incomplet pour " + key)
                else:
                    cache[key] = page.events
                    print("TEST_SOURCE_BSD_FALLBACK", key, len(page.events), flush=True)
        return cache[key]

    def deliver(name: str, builder, *, historical: str = "") -> None:
        try:
            post = builder()
            if post is None:
                unavailable[name] = "Données fiables insuffisantes pour une publication"
                print("TEST_INDISPONIBLE", name, unavailable[name], flush=True)
                return
            prefix = "🧪 TEST VISUEL / ACTU FOOT / " + name.upper()
            if historical:
                prefix += "\n📚 ARCHIVE / SIMULATION VISUELLE : " + historical
            if post.poll:
                question, options = post.poll
                post.poll = ("🧪 TEST " + question[:280], options)
                if historical:
                    post.poll_description = ("TEST • " + historical + " • " + post.poll_description)[:1024]
            else:
                post.text = "<b>" + ch.esc(prefix) + "</b>\n\n" + post.text
            mid = sender.send(post)
            sent[name] = {"message_id": mid, "category": post.category}
            print("TEST_OK", name, "message_id", mid, flush=True)
        except Exception as exc:
            errors[name] = type(exc).__name__ + ": " + str(exc)[:200]
            print("TEST_ECHEC", name, errors[name], flush=True)

    # Six formats historiques déjà disponibles dans le moteur éditorial.
    # Ce test utilise une fonction existante et ne marque jamais l'historique.
    try:
        result = ch.run_live_test(now)
        sent.update({k: {"message_id": v, "category": k} for k, v in result.get("sent", {}).items()})
        unavailable.update(result.get("skipped", {}))
        errors.update(result.get("errors", {}))
    except Exception as exc:
        print("TEST_SIX_FORMATS_PARTIEL", type(exc).__name__, str(exc)[:200], flush=True)
        # Le moteur existant journalise toujours chaque envoi/échec; la suite continue.

    # Autres variantes du moteur statistiques et communauté.
    deliver("statistique_avancee", lambda: ch.statistique_avancee(session, today))
    news = ch.load_site_news()
    deliver("debat", lambda: ch.community_debate_publication(news, today))
    deliver("quiz", lambda: ch.community_quiz_publication(session, today))

    fixtures: list[dict] = []
    previous: list[dict] = []
    try:
        fixtures = matches(today) + matches(today + timedelta(days=1))
        previous = matches(today - timedelta(days=1)) + matches(today)
    except Exception as exc:
        print("TEST_BSD_PARTIEL", type(exc).__name__, str(exc)[:180], flush=True)

    future = [e for e in ch.candidates(fixtures) if ch.kick(e) > now and ch.final_score(e) is None]
    if future:
        first = future[0]
        virtual_time = ch.kick(first) - timedelta(minutes=90)
        deliver("community_vote", lambda: ch.community_vote_publication([first], virtual_time),
                historical="scénario avant-match basé sur une vraie rencontre à venir")
    else:
        unavailable["community_vote"] = "Aucun match à venir dans le calendrier BSD"

    finished = [e for e in ch.candidates(previous) if ch.final_score(e) is not None]
    if finished:
        selected = sorted(finished, key=lambda e: -ch.importance(e))[0]
        virtual_time = ch.kick(selected) + timedelta(hours=3)
        deliver("reaction", lambda: ch.community_reaction_publication([selected], virtual_time),
                historical="réaction sur un résultat terminé confirmé")
    else:
        unavailable["reaction"] = "Aucun résultat récent disponible"

    # Le moteur de cycle utilise exclusivement des scores réellement récupérés.
    espn: list[dict] = []
    for day in (today, today - timedelta(days=1), today - timedelta(days=2)):
        try:
            espn.extend(lifecycle.fetch_espn_day(session, day))
        except Exception as exc:
            print("TEST_ESPN_INDISPONIBLE", day, type(exc).__name__, flush=True)
    valid = [e for e in espn if e.get("home_team") and e.get("away_team") and e.get("event_date")]
    verified_fixture = next((e for e in valid if e.get("state") == "post"), None) or (valid[0] if valid else None)

    def make_lifecycle(kind, event, **extra):
        if not event:
            return None
        signal = {
            "kind": kind, "key": "test:" + kind + ":" + str(event.get("id") or "fixture"),
            "home": event["home_team"], "away": event["away_team"],
            "league": event.get("league") or "Football",
            "score": extra.get("score", "—"),
            "minute": extra.get("minute", event.get("minute") or 0),
            "source": event.get("source") or "ESPN",
            "goal": extra.get("goal", {}),
            "lineups": extra.get("lineups", {}),
            "home_logo": event.get("home_logo"),
            "away_logo": event.get("away_logo"),
            "kickoff": lifecycle._moment(event.get("event_date")),
            "espn_event_id": str(event.get("id") or "").removeprefix("espn:"),
            "espn_url": lifecycle.espn_match_url(str(event.get("id") or "").removeprefix("espn:")),
        }
        return ch.lifecycle_publication(signal)

    deliver("kickoff", lambda: make_lifecycle("kickoff", verified_fixture, score="0-0"),
            historical="mise en page coup d'envoi sur une rencontre réelle, ancien score de départ")
    halftime_match = next((e for e in valid if lifecycle.is_halftime(e)), None)
    deliver("mi_temps", lambda: make_lifecycle("mi_temps", halftime_match or verified_fixture, score="—"),
            historical="visuel de mi-temps; aucun score de pause n'est affirmé")

    fresh = lifecycle.fetch_supabase_live(session)
    active = [e for e in fresh if lifecycle.is_live(e) and e.get("home_score") is not None
              and e.get("away_score") is not None]
    score_fixture = active[0] if active else next((e for e in valid if e.get("home_score") is not None), None)
    if score_fixture:
        hs, aws = score_fixture["home_score"], score_fixture["away_score"]
        archived = "" if score_fixture in active else "résultat archivé, non affiché comme score du direct"
        deliver("score_update", lambda: make_lifecycle("score_update", score_fixture, score=f"{hs}-{aws}"),
                historical=archived)
    else:
        unavailable["score_update"] = "Pas de score vérifiable dans les sources"

    # Les vrais buteurs et compositions sont tirés du résumé ESPN, jamais inventés.
    detailed: list[tuple[dict, dict]] = []
    for e in sorted(valid, key=lambda x: (x.get("home_score") or 0) + (x.get("away_score") or 0), reverse=True)[:12]:
        try:
            data = lifecycle.fetch_espn_summary(session, str(e.get("id") or ""))
            if data:
                detailed.append((e, data))
        except Exception as exc:
            print("TEST_ESPN_SUMMARY_ERREUR", str(e.get("id")), type(exc).__name__, flush=True)
        if len(detailed) >= 8:
            break
    for e, data in detailed:
        lineups = lifecycle.extract_lineups(data)
        if len(lineups["home"]) == 11 and len(lineups["away"]) == 11:
            deliver("composition", lambda e=e, lineups=lineups: make_lifecycle("composition", e, lineups=lineups),
                    historical="compositions de la rencontre réellement publiées par ESPN")
            break
    if "composition" not in sent and "composition" not in errors:
        unavailable["composition"] = "Aucune composition complète et vérifiée sur la période"

    for e, data in detailed:
        goals = lifecycle.extract_goals(data)
        if goals:
            goal = goals[-1]
            score = f"{e.get('home_score')}-{e.get('away_score')}"
            deliver("goal", lambda e=e, goal=goal, score=score: make_lifecycle("goal", e, score=score, goal=goal),
                    historical="buteur vérifié; score affiché = score observé, pas forcément score à la minute du but")
            break
    if "goal" not in sent and "goal" not in errors:
        unavailable["goal"] = "Aucun buteur certifié dans les résumés ESPN"

    # Moteur viral: trois variantes réelles. Les vidéos sont rendues par le moteur natif.
    deliver("viral_news", lambda: _viral_of_kind([], news, session, now, "news_pulse"))
    spectacular = [e for e in finished if sum(ch.final_score(e) or (0, 0)) >= 4]
    if spectacular:
        e = spectacular[0]
        deliver("viral_match", lambda: _viral_of_kind([e], [], session, ch.kick(e) + timedelta(hours=3), "match_fou"),
                historical="vidéo créée depuis un score final réel")
    else:
        unavailable["viral_match"] = "Aucun score spectaculaire confirmé"
    deliver("viral_stat", lambda: _viral_of_kind([], [], session, now, "stat_pulse"))

    for category in CATEGORIES:
        if category not in sent and category not in unavailable and category not in errors:
            unavailable[category] = "Pas de résultat enregistré dans les logs du test existant"
    report = {"sent": sent, "unavailable": unavailable, "errors": errors}
    print("ACTUFOOT_FIVE_SYSTEMS_TEST", json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if not errors and not unavailable else 1


def _viral_of_kind(events, news, session, now, expected):
    post = ch.viral_publication(events, news, session, now)
    if not post or not post.animation_payload:
        return None
    if post.animation_payload.get("kind") != expected:
        return None
    return post


if __name__ == "__main__":
    sys.exit(main())
