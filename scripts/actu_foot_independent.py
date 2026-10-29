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
import re
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
    extract_goals, extract_cards, extract_substitutions,
    extract_shootout_kicks, extract_lineups, extract_match_enrichment,
    espn_match_url, _minute_total,
)
from scripts import football_channel as channel

PROGRAMME_KIND = "actufoot_independent_programme_v1"
EVENT_KIND = "actufoot_independent_event_v1"
MAX_TRACKED = 4
MAX_CALLS_PER_CYCLE = 4
PROGRAMME_START = (6, 45)  # Africa/Lome
PROGRAMME_END = (7, 45)
MAX_LIVE_HOURS = 5
DEFINITIVE_REJECTION_CODES = {400, 401, 403, 404, 429}


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


def enrich_espn_fixtures(events: list[dict]) -> list[dict]:
    """Réutiliser uniquement les métadonnées officielles déjà dans le scoreboard.

    Aucun second fournisseur ni API dédiée par compétition.
    Ne jamais inventer le tour ou la compétition en l'absence de métadonnées.
    """
    enriched = []
    for source in events:
        event = dict(source)
        raw = event.get("raw") if isinstance(event.get("raw"), dict) else {}
        competitions = raw.get("competitions") if isinstance(raw.get("competitions"), list) else []
        competition = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
        for key, possible in (
            ("round_name", (competition.get("altGameNote"), competition.get("note"),
                            raw.get("altGameNote"), raw.get("note"))),
            ("stage", (competition.get("stage"), competition.get("round"),
                       raw.get("stage"), raw.get("round"))),
            ("league_name", (event.get("league"), competition.get("league"),
                             raw.get("league"))),
        ):
            if event.get(key):
                continue
            for value in possible:
                if isinstance(value, dict):
                    value = value.get("displayName") or value.get("name") or value.get("shortName")
                if isinstance(value, str) and value.strip():
                    event[key] = value.strip()
                    break
        enriched.append(event)
    return enriched


def selected_fixtures(events: list[dict], now: datetime) -> tuple:
    local_date = now.astimezone(channel.TZ).date()
    upcoming = [
        e for e in enrich_espn_fixtures(events)
        if channel.kick(e) is not None
        and channel.kick(e).astimezone(channel.TZ).date() == local_date
        and channel.kick(e) > now
        and str(e.get("state") or "").lower() not in ("in", "post", "finished")
    ]
    # Programme existant : cartes, logos, mentions, gabarit et filtres conservés.
    # Son ranking est synchronisé avec event_priority par actu_foot_ranking.py.
    # Tri indépendant : grand club puis phase finale puis compétition.
    channel._live_rank_key = event_priority
    post = channel.programme(upcoming, local_date, as_of=now)
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
    """Seul un programme Telegram confirmé autorise le suivi LIVE."""
    rows = ledger.query(
        "SELECT selection_snapshot FROM telegram_sent "
        "WHERE kind=? AND ref_id=? AND ref_date=? "
        "AND delivery_status='sent' LIMIT 1",
        (PROGRAMME_KIND, chat, day),
    ).get("results") or []
    if not rows:
        return [], None
    raw = rows[0].get("selection_snapshot")
    if not raw:
        raise RuntimeError("ACTUFOOT_SENT_PROGRAMME_WITHOUT_PLAN")
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("ACTUFOOT_INVALID_SAVED_PLAN") from exc
    if not isinstance(payload, list):
        raise RuntimeError("ACTUFOOT_INVALID_SAVED_PLAN")
    return [p for p in payload[:MAX_TRACKED] if isinstance(p, dict)], raw


def reserve_programme(ledger: D1Ledger, chat: str, day: str, fixtures: list[dict]) -> bool:
    """Une seule transaction D1 : réserver ET enregistrer le plan avant Telegram."""
    if not fixtures:
        raise RuntimeError("ACTUFOOT_EMPTY_PLAN")
    snapshot = json.dumps(fixtures[:MAX_TRACKED], ensure_ascii=False, separators=(",", ":"))
    result = ledger.query(
        "INSERT OR IGNORE INTO telegram_sent "
        "(id,kind,ref_id,ref_date,sent_at,validation_sent,delivery_status,selection_snapshot) "
        "VALUES (?,?,?,?,?,0,'reserved',?)",
        (str(uuid.uuid4()), PROGRAMME_KIND, chat, day,
         datetime.now(timezone.utc).isoformat(), snapshot),
    )
    changes = (result.get("meta") or {}).get("changes")
    if changes not in (0, 1):
        raise RuntimeError("ACTUFOOT_PROGRAMME_CLAIM_NOT_CONFIRMED")
    return changes == 1


def mark_finished(ledger: D1Ledger, chat: str, day: str, old_raw: str,
                  fixtures: list[dict], event_id: str):
    updated = [dict(row, done=True) if str(row.get("id")) == event_id else row for row in fixtures]
    if updated == fixtures:
        return old_raw, fixtures
    raw = json.dumps(updated, ensure_ascii=False, separators=(",", ":"))
    result = ledger.query(
        "UPDATE telegram_sent SET selection_snapshot=? "
        "WHERE kind=? AND ref_id=? AND ref_date=? AND delivery_status='sent' "
        "AND selection_snapshot=?",
        (raw, PROGRAMME_KIND, chat, day, old_raw),
    )
    if (result.get("meta") or {}).get("changes") != 1:
        raise RuntimeError("ACTUFOOT_PLAN_CONCURRENT_UPDATE")
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
        rows = ledger.rows(EVENT_KIND, day, ref_id=key)
        if rows and rows[0].get("delivery_status") == "sent":
            return True
        # Ne jamais considérer une réservation incertaine comme un envoi réussi.
        raise RuntimeError("ACTUFOOT_EVENT_UNCERTAIN_DELIVERY " + ref)
    try:
        message_id = sender.send(post)
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else None
        if code in DEFINITIVE_REJECTION_CODES:
            ledger.release(EVENT_KIND, key, day)
        raise
    # L'état 'reserved' reste intact en cas de timeout ou de réponse ambiguë.
    ledger.mark(EVENT_KIND, key, day, message_id=message_id)
    print("ACTUFOOT_SENT", post.category, ref, "message_id", message_id)
    return True


def programme_cycle(now: datetime, sender: channel.Sender, ledger: D1Ledger | None,
                    dry_run: bool):
    if not within_programme_window(now):
        print("ACTUFOOT_PROGRAMME_OUTSIDE_WINDOW")
        return
    today = day_key(now)
    if not dry_run:
        rows = ledger.rows(PROGRAMME_KIND, today, ref_id=sender.chat)
        if rows:
            if rows[0].get("delivery_status") == "sent":
                plan, _ = get_plan(ledger, sender.chat, today)
                if not plan:
                    raise RuntimeError("ACTUFOOT_PROGRAMME_SENT_EMPTY_PLAN")
                print("ACTUFOOT_PROGRAMME_ALREADY_HANDLED", today, len(plan))
                return
            raise RuntimeError("ACTUFOOT_PROGRAMME_UNCERTAIN_DELIVERY " + today)
    events = fetch_espn_day(sender.session, now.astimezone(channel.TZ).date(), force=True)
    if not events:
        raise RuntimeError("ACTUFOOT_ESPN_DAY_EMPTY_OR_UNAVAILABLE " + today)
    post, selected = selected_fixtures(events, now)
    if not post or not selected:
        print("ACTUFOOT_NO_VERIFIED_PRIORITY_MATCHES", len(events))
        return
    if dry_run:
        print("ACTUFOOT_PROGRAMME_DRY_RUN", [(e["home"], e["away"]) for e in selected])
        sender.send(post)
        return
    # Tester les autorisations du bot AVANT de réserver le programme.
    sender.verify_discussion()
    if not reserve_programme(ledger, sender.chat, today, selected):
        raise RuntimeError("ACTUFOOT_PROGRAMME_CONCURRENT_RESERVATION")
    try:
        message_id = sender.send(post)
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else None
        if code in DEFINITIVE_REJECTION_CODES:
            ledger.release(PROGRAMME_KIND, sender.chat, today)
        raise
    ledger.mark(PROGRAMME_KIND, sender.chat, today, message_id=message_id)
    print("ACTUFOOT_PROGRAMME_SENT", today, len(selected), "message_id", message_id)



def signal_identity(row: dict, category: str, item: dict) -> str:
    """ID ESPN ou empreinte déterministe des données factuelles."""
    raw_id = str(item.get("id") or "").strip()
    if raw_id:
        return f"{category}:{row['id']}:{raw_id}"
    components = (
        item.get("minute_text") or item.get("minute_total") or item.get("minute"),
        item.get("player"), item.get("team_id"), item.get("team"),
        item.get("type"), item.get("entrant"), item.get("sortant"),
        item.get("home_score"), item.get("away_score"),
        item.get("outcome"), item.get("label"),
    )
    import hashlib
    fingerprint = hashlib.sha256(
        json.dumps(components, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()[:20]
    return f"{category}:{row['id']}:{fingerprint}"


def live_signals(row: dict, info: dict, summary: dict, now: datetime) -> list[dict]:
    """Événements vérifiés depuis UN résumé ESPN par match retenu.

    L'historique envoyé, jamais le score courant, empêche les doublons :
    les buts survenus durant une interruption restent récupérables jusqu'à
    la fin du match. Les événements sans source explicite sont ignorés.
    """
    source_id = str(row["id"])
    raw = info.get("raw") if isinstance(info.get("raw"), dict) else {}
    competitions = raw.get("competitions") if isinstance(raw.get("competitions"), list) else []
    comp = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
    status = comp.get("status") if isinstance(comp.get("status"), dict) else raw.get("status")
    status = status if isinstance(status, dict) else {}
    minute_text = str(status.get("displayClock") or status.get("clock") or "")
    minute = _minute_total(minute_text)
    if minute is None:
        minute = int(info.get("minute") or 0)
    period = int(info.get("period") or 0)
    hs, aws = info.get("home_score"), info.get("away_score")
    score = f"{hs}-{aws}" if hs is not None and aws is not None else ""
    state = str(info.get("state") or "").lower()
    detail = str(info.get("status_detail") or "").lower()
    live = state == "in"
    finished = state in ("post", "finished")
    is_half = any(x in detail for x in ("halftime", "half time", "half-time", "mi-temps", "ht -", " ht"))
    shootout_h = info.get("home_shootout_score")
    shootout_a = info.get("away_shootout_score")
    shootout_scores = ([shootout_h, shootout_a]
                       if shootout_h is not None and shootout_a is not None else [])
    shootout = ("shootout" in detail or "penalty shoot" in detail
                or "tirs au but" in detail or period >= 5 or bool(shootout_scores))
    common = {
        "home": row["home"], "away": row["away"], "league": row["league"],
        "source": "ESPN", "minute": minute, "minute_text": minute_text,
        "score": score,
        "home_logo": row.get("home_logo") or info.get("home_logo") or "",
        "away_logo": row.get("away_logo") or info.get("away_logo") or "",
        "espn_event_id": source_id, "espn_url": espn_match_url(source_id),
        "follow_ref": source_id, "fixture_key": source_id,
        "plan_rank": row.get("rank") or 99,
        "plan_role": "match_du_jour" if row.get("rank") == 1 else "fil_rouge",
    }
    signals = []
    def add(kind: str, key: str, **kwargs):
        signals.append(dict(common, kind=kind, key=key, **kwargs))

    if live and 0 <= minute <= 12:
        add("kickoff", "kickoff:" + source_id)
    if is_half and period in (0, 1, 2):
        add("mi_temps", "mi_temps:" + source_id)
    if is_half and period >= 3:
        add("mi_temps_prolongation", "mi_temps_prolongation:" + source_id)
    if live and period == 2 and 45 <= minute <= 59:
        add("debut_2e_mi_temps", "debut_2e_mi_temps:" + source_id)
    if live and minute >= 90 and period <= 2 and not shootout:
        add("temps_additionnel", "temps_additionnel:" + source_id)
    if live and period in (3, 4):
        add("prolongation", "prolongation:" + source_id)

    # Sources chronologiques officielles, sans score synthétique inventé.
    if live or finished or is_half:
        # Les tirs convertis pendant une séance de TAB ne sont pas des buts
        # du score réglementaire : ils sont traités séparément ci-dessous.
        shootout_event_ids = {
            str(item.get("id"))
            for item in extract_shootout_kicks(summary)
            if item.get("id")
        }
        for goal in extract_goals(summary):
            if not isinstance(goal, dict):
                continue
            if str(goal.get("id") or "") in shootout_event_ids:
                continue
            goal_min = goal.get("minute_total")
            if goal_min is None:
                goal_min = goal.get("minute")
            if goal_min is None:
                continue
            gh, ga = goal.get("home_score"), goal.get("away_score")
            add("goal", signal_identity(row, "goal", goal),
                goal=goal, minute=goal_min, minute_text=goal.get("minute_text") or "",
                score=f"{gh}-{ga}" if gh is not None and ga is not None else score)
        for card in extract_cards(summary):
            if not isinstance(card, dict):
                continue
            category = "carton_rouge" if card.get("type") == "red" else "carton_jaune"
            add(category, signal_identity(row, category, card),
                player=card.get("player") or "",
                minute=card.get("minute"), minute_text=card.get("minute_text") or "")
        for change in extract_substitutions(summary):
            if not isinstance(change, dict):
                continue
            add("remplacement", signal_identity(row, "remplacement", change),
                entrant=change.get("entrant") or "", sortant=change.get("sortant") or "",
                players=change.get("players") or [], minute=change.get("minute"),
                minute_text=change.get("minute_text") or "")

        lineups = extract_lineups(summary)
        if len(lineups.get("home") or []) == 11 and len(lineups.get("away") or []) == 11:
            old_home = row.get("lineup_home") or []
            old_away = row.get("lineup_away") or []
            if not old_home or not old_away:
                add("composition", "composition:" + source_id,
                    lineups=lineups, lineup_home_hash="",
                    lineup_away_hash="")
            else:
                for side in ("home", "away"):
                    old = old_home if side == "home" else old_away
                    new = lineups[side]
                    if old == new:
                        continue
                    new_only = [player for player in new if player not in old]
                    left = [player for player in old if player not in new]
                    add("changement_composition",
                        signal_identity(row, "changement_composition",
                                        {"team": side, "entrant": new_only,
                                         "sortant": left, "label": "|".join(new)}),
                        side=side, club=row[side], entrant=new_only[0] if new_only else "",
                        sortant=left[0] if left else "",
                        players=new, lineups=lineups)

    if (live and shootout) or (finished and shootout_scores):
        add("tirs_au_but", "tirs_au_but:" + source_id,
            shootout_scores=shootout_scores)
    if live or finished:
        for kick in extract_shootout_kicks(summary):
            if not isinstance(kick, dict) or kick.get("outcome") not in ("made", "missed"):
                continue
            category = ("tir_au_but_marque" if kick["outcome"] == "made"
                        else "tir_au_but_manque")
            kh, ka = kick.get("home_shootout_score"), kick.get("away_shootout_score")
            add(category, signal_identity(row, category, kick),
                player=kick.get("player") or "", team=kick.get("team") or "",
                shootout_scores=[kh, ka] if kh is not None and ka is not None
                else shootout_scores, minute=kick.get("minute"))
    if finished and shootout_scores:
        add("fin_tirs_au_but", "fin_tirs_au_but:" + source_id,
            shootout_scores=shootout_scores)
    if any(x in detail for x in ("postpon", "cancel", "abandon", "suspend")):
        add("suivi_interrompu", "suivi_interrompu:" + source_id, status=detail)
    elif finished and score:
        add("resultat_final", "resultat:" + source_id,
            shootout_scores=shootout_scores,
            match_data=extract_match_enrichment(summary),
            day=now.astimezone(channel.TZ).strftime("%d/%m/%Y"))
    return signals


def save_lineups(ledger: D1Ledger, chat: str, day: str, old_raw: str,
                 fixtures: list[dict], event_id: str, lineups: dict):
    updated = [
        dict(row, lineup_home=list(lineups.get("home") or []),
             lineup_away=list(lineups.get("away") or []))
        if str(row.get("id")) == event_id else row
        for row in fixtures
    ]
    if updated == fixtures:
        return old_raw, fixtures
    raw = json.dumps(updated, ensure_ascii=False, separators=(",", ":"))
    result = ledger.query(
        "UPDATE telegram_sent SET selection_snapshot=? "
        "WHERE kind=? AND ref_id=? AND ref_date=? "
        "AND delivery_status='sent' AND selection_snapshot=?",
        (raw, PROGRAMME_KIND, chat, day, old_raw),
    )
    if (result.get("meta") or {}).get("changes") != 1:
        raise RuntimeError("ACTUFOOT_LINEUPS_CONCURRENT_UPDATE")
    return raw, updated


def lifecycle_cycle(now: datetime, sender: channel.Sender,
                    ledger: D1Ledger | None, dry_run: bool):
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
        # Vérifier le canal avant toute réservation D1 d'événement.
        sender.verify_discussion()
        # Lecture groupée des événements : ne pas réinsérer des événements inchangés.
        previous = ledger.query(
            "SELECT ref_id,delivery_status FROM telegram_sent "
            "WHERE kind=? AND ref_date=? AND ref_id LIKE ? LIMIT 400",
            (EVENT_KIND, day, sender.chat + ":%"),
        ).get("results") or []
        known = {str(item["ref_id"]): item["delivery_status"] for item in previous}
        for row in list(plan):
            if checked >= MAX_CALLS_PER_CYCLE:
                break
            if row.get("done"):
                continue
            started = channel.moment(row.get("event_date"))
            if not started:
                raise RuntimeError("ACTUFOOT_SAVED_KICKOFF_INVALID " + str(row.get("id")))
            if not timedelta(minutes=-75) <= now - started <= timedelta(hours=MAX_LIVE_HOURS):
                if now - started > timedelta(hours=MAX_LIVE_HOURS):
                    print("ACTUFOOT_UNCONFIRMED_FINAL_EXPIRED", row["id"])
                continue
            checked += 1
            summary = fetch_espn_summary(sender.session, str(row["id"]), force=True)
            if not isinstance(summary, dict) or not summary:
                raise RuntimeError("ACTUFOOT_ESPN_SUMMARY_UNAVAILABLE " + str(row["id"]))
            info = parse_espn_summary_match(summary)
            if not info or str(info.get("id") or "") != str(row["id"]):
                raise RuntimeError("ACTUFOOT_ESPN_SUMMARY_ID_MISMATCH " + str(row["id"]))
            if (channel.team(info, "home").casefold() != row["home"].casefold()
                    or channel.team(info, "away").casefold() != row["away"].casefold()):
                raise RuntimeError("ACTUFOOT_ESPN_TEAMS_MISMATCH " + str(row["id"]))
            signals = live_signals(row, info, summary, now)
            final_ok = False
            interruption_ok = False
            lineups_ok = False
            for signal in signals:
                ref = signal["key"]
                key = sender.chat + ":" + ref
                if key in known:
                    if known[key] != "sent":
                        raise RuntimeError("ACTUFOOT_UNCERTAIN_DELIVERY " + ref)
                    was_sent = True
                else:
                    if signal["kind"] == "resultat_final":
                        post = channel.followed_final_publication(signal)
                    elif signal["kind"] == "suivi_interrompu":
                        post = channel.followed_interruption_publication(signal)
                    else:
                        post = channel.lifecycle_publication(signal)
                    if post is None:
                        continue
                    was_sent = confirmed_message(
                        ledger, sender, day, ref, post, dry_run=False
                    )
                    if was_sent:
                        known[key] = "sent"
                if was_sent and signal["kind"] == "resultat_final":
                    final_ok = True
                if was_sent and signal["kind"] == "suivi_interrompu":
                    interruption_ok = True
                if was_sent and signal["kind"] in ("composition", "changement_composition"):
                    lineups_ok = True
            # Le plan reste récupérable après une panne d'envoi ou de D1.
            if lineups_ok:
                current_lineups = extract_lineups(summary)
                if len(current_lineups.get("home") or []) == 11 and len(current_lineups.get("away") or []) == 11:
                    raw, plan = save_lineups(
                        ledger, sender.chat, day, raw, plan, str(row["id"]),
                        current_lineups,
                    )
            if (final_ok or interruption_ok) and raw is not None:
                raw, plan = mark_finished(
                    ledger, sender.chat, day, raw, plan, str(row["id"])
                )
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
