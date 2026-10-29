#!/usr/bin/env python3
"""ActuFoot Telegram: programme quotidien et fil rouge autonome.

Aucune connexion Supabase/Neon, ni collecte du moteur de pronostics LIVE.
Cloudflare D1 conserve seulement le programme annoncé et les clés de messages.
Un appel ESPN par rencontre retenue / cycle de deux minutes, uniquement pendant
sa fenêtre de jeu; aucun relevé de score inchangé n'est enregistré.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from scripts.d1_publication_ledger import D1Ledger
from scripts.football_match_lifecycle import (
    fetch_espn_day, fetch_espn_summary, parse_espn_summary_match,
    extract_goals, extract_match_enrichment, espn_match_url,
)
from scripts import football_channel as channel

PLAN_KIND = "actufoot_independent_plan_v1"
PROGRAMME_KIND = "actufoot_independent_programme_v1"
EVENT_KIND = "actufoot_independent_event_v1"
MAX_TRACKED = 4
MAX_CALLS_PER_CYCLE = 4
PROGRAMME_START = (6, 45)  # Africa/Lome
PROGRAMME_END = (7, 45)


def day_key(now: datetime) -> str:
    return now.astimezone(channel.TZ).date().isoformat()


def within_programme_window(now: datetime) -> bool:
    local = now.astimezone(channel.TZ)
    minutes = local.hour * 60 + local.minute
    return 6 * 60 + 45 <= minutes <= 7 * 60 + 45


def event_priority(event: dict) -> tuple:
    """Top 100 > finales/demi-finales > grandes compétitions > importance."""
    count, weight = channel.live_grand_club_priority(event)
    return (
        int(count > 0), weight, count,
        channel.high_stakes_bonus(event),
        channel.editorial_competition_priority(event),
        channel.importance(event),
        channel.kick(event) or datetime.min.replace(tzinfo=timezone.utc),
    )


def selected_fixtures(events: list[dict], now: datetime) -> tuple:
    local_date = now.astimezone(channel.TZ).date()
    upcoming = [
        e for e in events
        if channel.kick(e) is not None
        and channel.kick(e).astimezone(channel.TZ).date() == local_date
        and channel.kick(e) > now
        and str(e.get("state") or "").lower() not in ("in", "post", "finished")
    ]
    # Programme existant : cartes, logos, mentions, gabarit et filtres conservés.
    # Son ranking est synchronisé avec event_priority par actu_foot_ranking.py.
    # Tri indépendant : grand club puis phase finale puis compétition.\n    channel._live_rank_key = event_priority\n    post = channel.programme(upcoming, local_date, as_of=now)
    if post is None:
        return None, []
    expected = (post.verification or {}).get("fixtures") or []
    found = []
    for index, fixture in enumerate(expected[:MAX_TRACKED]):
        matching = next((e for e in upcoming if
            channel.team(e, "home") == fixture.get("home")
            and channel.team(e, "away") == fixture.get("away")
            and channel.kick(e).astimezone(timezone.utc).isoformat() == fixture.get("event_date")
        ), None)
        if not matching or not str(matching.get("id") or "").isdigit():
            continue  # Jamais suivre un match sans identifiant ESPN confirmé.
        found.append({
            "id": str(matching["id"]),
            "home": channel.team(matching, "home"),
            "away": channel.team(matching, "away"),
            "league": channel.league(matching),
            "event_date": fixture["event_date"],
            "home_logo": str(matching.get("home_logo") or ""),
            "away_logo": str(matching.get("away_logo") or ""),
            "rank": index + 1,
            "done": False,
        })
    return post, found


def get_plan(ledger: D1Ledger, chat: str, day: str) -> tuple[list[dict], str | None]:
    rows = ledger.query(
        "SELECT selection_snapshot FROM telegram_sent WHERE kind=? AND ref_id=? "
        "AND ref_date=? AND delivery_status='sent' LIMIT 1",
        (PLAN_KIND, chat, day),
    ).get("results") or []
    if not rows:
        return [], None
    raw = rows[0].get("selection_snapshot")
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise RuntimeError("ActuFoot programme D1 invalide")
    return [p for p in payload[:MAX_TRACKED] if isinstance(p, dict)], raw


def save_plan(ledger: D1Ledger, chat: str, day: str, fixtures: list[dict]):
    raw = json.dumps(fixtures[:MAX_TRACKED], ensure_ascii=False, separators=(",", ":"))
    ledger.query(
        "INSERT OR IGNORE INTO telegram_sent "
        "(id,kind,ref_id,ref_date,sent_at,validation_sent,delivery_status,selection_snapshot) "
        "VALUES (?,?,?,?,?,0,'sent',?)",
        (str(uuid.uuid4()), PLAN_KIND, chat, day,
         datetime.now(timezone.utc).isoformat(), raw),
    )


def mark_finished(ledger: D1Ledger, chat: str, day: str, old_raw: str, fixtures: list[dict], event_id: str):
    updated = [dict(row, done=True) if str(row.get("id")) == event_id else row for row in fixtures]
    if updated == fixtures:
        return old_raw, fixtures
    raw = json.dumps(updated, ensure_ascii=False, separators=(",", ":"))
    result = ledger.query(
        "UPDATE telegram_sent SET selection_snapshot=? "
        "WHERE kind=? AND ref_id=? AND ref_date=? AND selection_snapshot=?",
        (raw, PLAN_KIND, chat, day, old_raw),
    )
    if (result.get("meta") or {}).get("changes") != 1:
        raise RuntimeError("Etat ActuFoot modifié concurremment; aucun écrasement")
    return raw, updated


def confirmed_message(ledger: D1Ledger, sender: channel.Sender,
                      day: str, ref: str, post, *, dry_run: bool) -> bool:
    if post is None:
        return False
    if dry_run:
        sender.send(post)
        return False
    key = sender.chat + ":" + ref
    if not ledger.claim(EVENT_KIND, key, day):
        return False
    # La réservation D1 est conservée si la réponse Telegram est incertaine :
    # aucun doublon automatique, aucune publication sans déduplication.
    message_id = sender.send(post)
    ledger.mark(EVENT_KIND, key, day, message_id=message_id)
    print("ACTUFOOT_SENT", post.category, ref, "message_id", message_id)
    return True


def programme_cycle(now: datetime, sender: channel.Sender, ledger: D1Ledger | None, dry_run: bool):
    if not within_programme_window(now):
        print("ACTUFOOT_PROGRAMME_OUTSIDE_WINDOW")
        return
    today = day_key(now)
    if not dry_run:
        plan, _ = get_plan(ledger, sender.chat, today)
        if plan or ledger.rows(PROGRAMME_KIND, today, ref_id=sender.chat):
            print("ACTUFOOT_PROGRAMME_ALREADY_HANDLED", today)
            return
    events = fetch_espn_day(sender.session, now.astimezone(channel.TZ).date(), force=True)
    post, selected = selected_fixtures(events, now)
    if not post or not selected:
        print("ACTUFOOT_NO_VERIFIED_PRIORITY_MATCHES", len(events))
        return
    if dry_run:
        print("ACTUFOOT_PROGRAMME_DRY_RUN", [(e["home"], e["away"]) for e in selected])
        sender.send(post)
        return
    if not ledger.claim(PROGRAMME_KIND, sender.chat, today):
        print("ACTUFOOT_PROGRAMME_RESERVED", today)
        return
    message_id = sender.send(post)
    ledger.mark(PROGRAMME_KIND, sender.chat, today, message_id=message_id)
    save_plan(ledger, sender.chat, today, selected)
    print("ACTUFOOT_PROGRAMME_SENT", today, len(selected), "message_id", message_id)


def live_signals(row: dict, info: dict, summary: dict, now: datetime) -> list[dict]:
    """Uniquement les événements vérifiables depuis le résumé de ce match."""
    source_id = row["id"]
    minute = int(info.get("minute") or 0)
    hs, aws = info.get("home_score"), info.get("away_score")
    score = f"{hs}-{aws}" if hs is not None and aws is not None else ""
    kind = str(info.get("state") or "").lower()
    detail = str(info.get("status_detail") or "").lower()
    common = {
        "home": row["home"], "away": row["away"], "league": row["league"],
        "source": "ESPN", "minute": minute, "score": score,
        "home_logo": row.get("home_logo") or info.get("home_logo") or "",
        "away_logo": row.get("away_logo") or info.get("away_logo") or "",
        "espn_event_id": source_id, "espn_url": espn_match_url(source_id),
        "follow_ref": source_id, "fixture_key": source_id,
        "plan_rank": row.get("rank") or 99,
        "plan_role": "match_du_jour" if row.get("rank") == 1 else "fil_rouge",
    }
    signals = []
    if kind == "in" and 0 <= minute <= 12:
        signals.append(dict(common, kind="kickoff", key="kickoff:" + source_id))
    if "halftime" in detail or "half time" in detail or "mi-temps" in detail:
        signals.append(dict(common, kind="mi_temps", key="mi_temps:" + source_id))
    # ESPN détaille chaque but; un changement du simple score ne suffit pas.
    if kind == "in" and score:
        for goal in extract_goals(summary):
            goal_min = goal.get("minute_total")
            if goal_min is None:
                goal_min = goal.get("minute")
            if goal_min is None or minute <= 0 or not -2 <= minute - int(goal_min) <= 14:
                continue
            identity = str(goal.get("id") or "").strip()
            if not identity:
                identity = ":".join((str(goal.get("minute_total")),str(goal.get("player")),
                                     str(goal.get("team_id")),str(goal.get("home_score")),
                                     str(goal.get("away_score"))))
            signals.append(dict(common, kind="goal", goal=goal,
                                minute=goal_min,
                                score=(f"{goal['home_score']}-{goal['away_score']}"
                                       if goal.get("home_score") is not None and goal.get("away_score") is not None
                                       else score),
                                key="goal:" + source_id + ":" + identity))
    if kind in ("post", "finished") and score:
        signals.append(dict(common, kind="resultat_final", key="resultat:" + source_id,
                            match_data=extract_match_enrichment(summary),
                            day=now.astimezone(channel.TZ).strftime("%d/%m/%Y")))
    if any(x in detail for x in ("postpon", "cancel", "abandon", "suspend")):
        signals.append(dict(common, kind="suivi_interrompu",
                            key="suivi_interrompu:" + source_id, status=detail))
    return signals


def lifecycle_cycle(now: datetime, sender: channel.Sender, ledger: D1Ledger | None, dry_run: bool):
    if dry_run:
        print("ACTUFOOT_LIVE_DRY_RUN_NO_DB_OR_TELEGRAM")
        return
    checked = 0
    for date_value in (now.astimezone(channel.TZ).date(),
                       now.astimezone(channel.TZ).date() - timedelta(days=1)):
        day = date_value.isoformat()
        plan, raw = get_plan(ledger, sender.chat, day)
        if not plan:
            continue
        for row in plan:
            if checked >= MAX_CALLS_PER_CYCLE:
                return
            if row.get("done"):
                continue
            started = channel.moment(row.get("event_date"))
            if not started or not timedelta(minutes=-8) <= now - started <= timedelta(hours=4):
                continue
            checked += 1
            summary = fetch_espn_summary(sender.session, str(row["id"]), force=True)
            info = parse_espn_summary_match(summary)
            if not info or str(info.get("id") or "") != str(row["id"]):
                print("ACTUFOOT_SUMMARY_NOT_CONFIRMED", row["id"])
                continue
            if channel.team(info, "home").casefold() != row["home"].casefold() or channel.team(info, "away").casefold() != row["away"].casefold():
                print("ACTUFOOT_SUMMARY_TEAMS_MISMATCH", row["id"])
                continue
            signals = live_signals(row, info, summary, now)
            finished = False
            for signal in signals:
                signal_id = signal["key"]
                if signal["kind"] == "resultat_final":
                    post = channel.followed_final_publication(signal)
                    finished = True
                elif signal["kind"] == "suivi_interrompu":
                    post = channel.followed_interruption_publication(signal)
                    finished = True
                else:
                    post = channel.lifecycle_publication(signal)
                confirmed_message(ledger, sender, day, signal_id, post, dry_run=False)
            if finished and raw is not None:
                # Une fois le résultat confirmé, plus aucun appel ESPN pour ce match.
                raw, plan = mark_finished(ledger, sender.chat, day, raw, plan, row["id"])
    print("ACTUFOOT_LIVE_MONITORED", checked)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("full", "lifecycle"), required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    # Le moteur de suivi ne consulte aucune variable SUPABASE_* ou NEON_*.
    os.environ["FOOTBALL_REMOTE_LEDGER"] = "0"
    os.environ["FOOTBALL_CANONICAL_EVENTS"] = "0"
    os.environ["FOOTBALL_RUN_METRICS"] = "0"
    now = datetime.now(timezone.utc)
    sender = channel.Sender(dry_run=args.dry_run)
    ledger = None if args.dry_run else D1Ledger()
    if args.mode == "full":
        programme_cycle(now, sender, ledger, args.dry_run)
    else:
        lifecycle_cycle(now, sender, ledger, args.dry_run)


if __name__ == "__main__":
    main()
