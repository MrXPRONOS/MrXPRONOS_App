#!/usr/bin/env python3
"""Actu Foot V1.2: verified post-match debriefs and ESPN league tables.

Independent of Neon/Supabase. Reuses V1.1 Cloudflare D1 atomic reservations,
daily quotas, Telegram HTML and role verification. Never invents data.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import actufoot_v11_live as live
from scripts.actufoot_telegram_format import source_footer
from scripts.d1_publication_ledger import D1Ledger
from scripts.football_match_lifecycle import (
    extract_goals, extract_cards, extract_shootout_kicks,
)

LEAGUES = {
    "eng.1": "Premier League",
    "esp.1": "La Liga",
    "fra.1": "Ligue 1",
    "ger.1": "Bundesliga",
    "ita.1": "Serie A",
}
STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/soccer/{code}/standings"
STANDINGS_STATE_KIND = "actufoot_v12_standings_observation"
STANDINGS_TAG = "📊 CLASSEMENTS VÉRIFIÉS"
DEBRIEF_TAG = "📋 DÉBRIEF APRÈS-MATCH"


def safe_text(value: Any, limit: int = 90) -> str:
    return html.escape(re.sub(r"\s+", " ", str(value or "")).strip()[:limit], quote=False)


def verified_score(info: dict) -> str:
    home, away = info.get("home_score"), info.get("away_score")
    if not (type(home) is int and type(away) is int
            and 0 <= home <= 99 and 0 <= away <= 99):
        return ""
    return f"{home}–{away}"


def debrief_message(row: dict, info: dict, summary: dict) -> str | None:
    """Only confirmed final facts; no speculative match narrative or scorer."""
    if live.phase(info) != "final" or not live.valid_summary(row, info):
        return None
    score = verified_score(info)
    if not score:
        return None
    home = safe_text(info["home_team"], 65)
    away = safe_text(info["away_team"], 65)
    league = safe_text(row.get("league_name") or row.get("league"), 85)
    heading = f"<b>🏁 {home} {score} {away}</b>"
    facts = ["<b>Score final confirmé</b>"]
    if league:
        facts.append("<i>🏆 " + league + "</i>")
    shootout_ids = {
        str(k.get("id")) for k in extract_shootout_kicks(summary)
        if isinstance(k, dict) and k.get("id")
    }
    goals = [x for x in extract_goals(summary)
             if isinstance(x, dict) and str(x.get("id") or "") not in shootout_ids]
    for goal in goals[:12]:
        minute = safe_text(goal.get("minute_text") or goal.get("minute_total"), 9)
        player = safe_text(goal.get("player"), 65)
        team = safe_text(goal.get("team"), 55)
        bits = [x for x in (minute + "'" if minute and not minute.endswith("'") else minute,
                           player or "Buteur non indiqué", team) if x]
        kind = "⚽ "
        if goal.get("own_goal"):
            kind = "⚽ CSC · "
        elif goal.get("penalty"):
            kind = "⚽ Penalty · "
        facts.append(kind + " · ".join(bits))
    cards = [x for x in extract_cards(summary) if isinstance(x, dict)]
    for card in cards[:8]:
        if card.get("type") not in {"red", "yellow"}:
            continue
        player = safe_text(card.get("player"), 65)
        minute = safe_text(card.get("minute_text") or card.get("minute"), 9)
        facts.append(("🟥" if card["type"] == "red" else "🟨")
                     + " " + " · ".join(x for x in (player or "Joueur non indiqué", minute) if x))
    if not goals and not cards:
        facts.append("<i>Aucun autre événement détaillé exploitable dans le résumé ESPN.</i>")
    body = "<blockquote>" + "\n".join(facts) + "</blockquote>"
    return "\n\n".join([
        heading, body, "<b>🏷 " + DEBRIEF_TAG + "</b>\n" + source_footer("ESPN"),
    ])


def _int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        if isinstance(value, float) and not value.is_integer():
            return None
        string = str(value).strip()
        if not re.fullmatch(r"-?\d+", string):
            return None
        return int(string)
    except (TypeError, ValueError):
        return None


def _stats(entry: dict) -> dict:
    found = {}
    for stat in entry.get("stats", []) if isinstance(entry.get("stats"), list) else []:
        if not isinstance(stat, dict):
            continue
        name = re.sub(r"[^a-z]", "", str(stat.get("name") or "").casefold())
        if name:
            found[name] = _int(stat.get("value") if stat.get("value") is not None
                               else stat.get("displayValue"))
    return found


def standings_groups(payload: dict, season_year: int) -> list[dict]:
    """Do not merge ESPN groups or infer missing ranks/points/statistics."""
    if not isinstance(payload, dict):
        return []
    season = payload.get("season")
    if not isinstance(season, dict) or _int(season.get("year")) != season_year:
        return []
    groups = []
    stack = [payload]
    while stack:
        node = stack.pop(0)
        if not isinstance(node, dict):
            continue
        table = node.get("standings")
        entries = table.get("entries") if isinstance(table, dict) else None
        if isinstance(entries, list):
            parsed = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                team = entry.get("team")
                if not isinstance(team, dict):
                    continue
                team_id = str(team.get("id") or "").strip()
                name = str(team.get("displayName") or team.get("name") or "").strip()
                stats = _stats(entry)
                rank = stats.get("rank") or stats.get("position") or _int(entry.get("rank"))
                pts = stats.get("points")
                played = stats.get("gamesplayed")
                if played is None:
                    played = stats.get("played")
                gd = stats.get("pointdifferential")
                if gd is None:
                    gd = stats.get("goaldifference")
                if not (team_id and name and rank is not None and pts is not None
                        and played is not None and 1 <= rank <= 100
                        and 0 <= pts <= 250 and 0 <= played <= 70):
                    continue
                parsed.append({"id": team_id, "team": name, "rank": rank,
                               "pts": pts, "played": played, "gd": gd})
            parsed.sort(key=lambda x: x["rank"])
            if (len(parsed) >= 4 and parsed[0]["rank"] == 1
                    and len({x["id"] for x in parsed}) == len(parsed)
                    and len({x["rank"] for x in parsed}) == len(parsed)):
                groups.append({
                    "name": str(node.get("name") or "").strip()[:70],
                    "entries": parsed,
                })
        children = node.get("children")
        if isinstance(children, list):
            stack.extend(x for x in children if isinstance(x, dict))
    return groups[:4]


def _previous_ranks(ledger: D1Ledger, day: str) -> dict:
    rows = ledger.query(
        "SELECT selection_snapshot FROM telegram_sent "
        "WHERE kind=? AND ref_date<? AND delivery_status='observed' "
        "ORDER BY ref_date DESC LIMIT 1",
        (STANDINGS_STATE_KIND, day),
    ).get("results") or []
    if rows:
        try:
            result = json.loads(rows[0].get("selection_snapshot") or "{}")
            return result if isinstance(result, dict) else {}
        except (ValueError, TypeError):
            pass
    return {}


def _store_ranks(ledger: D1Ledger, day: str, snapshot: dict) -> None:
    payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
    ledger.query(
        "INSERT OR IGNORE INTO telegram_sent "
        "(id,kind,ref_id,ref_date,sent_at,validation_sent,delivery_status,selection_snapshot) "
        "VALUES (?,?,?,?,?,0,'observed',?)",
        (str(uuid.uuid4()), STANDINGS_STATE_KIND, "ranking:daily", day,
         datetime.now(timezone.utc).isoformat(), payload),
    )


def standings_message(groups_by_league: dict, prior: dict,
                      now: datetime) -> tuple[str | None, dict]:
    sections, snapshot = [], {}
    for league_code, league_name in LEAGUES.items():
        groups = groups_by_league.get(league_code) or []
        if not groups:
            continue
        snapshot[league_code] = {}
        for group in groups[:2]:
            entries = group["entries"]
            snapshot[league_code].update(
                {row["id"]: row["rank"] for row in entries}
            )
            title = "🏆 " + safe_text(league_name)
            if group.get("name") and group["name"].casefold() != league_name.casefold():
                title += " · " + safe_text(group["name"], 45)
            rows = [title]
            prev = prior.get(league_code) if isinstance(prior.get(league_code), dict) else {}
            for entry in entries[:5]:
                old_rank = _int(prev.get(entry["id"]))
                delta = old_rank - entry["rank"] if old_rank is not None else None
                trend = (" ↑" + str(delta) if delta is not None and delta > 0 else
                         " ↓" + str(-delta) if delta is not None and delta < 0 else
                         " =" if delta == 0 else "")
                gd = f" · diff. {entry['gd']:+d}" if entry["gd"] is not None else ""
                rows.append(
                    f"{entry['rank']}. {safe_text(entry['team'], 40)} · "
                    f"{entry['pts']} pts · {entry['played']} MJ{gd}{trend}"
                )
            sections.append("\n".join(rows))
    if not sections:
        return None, {}
    body = "<blockquote>" + "\n\n".join(sections) + "</blockquote>"
    timestamp = now.astimezone(live.TZ).strftime("%d/%m/%Y %H:%M")
    text = "\n\n".join([
        "<b>📊 Classements des championnats</b>",
        body,
        "<i>Consultés le " + timestamp + " (heure de Lomé) · "
        "Évolution comparée au dernier relevé disponible uniquement.</i>",
        "<b>🏷 " + STANDINGS_TAG + "</b>\n" + source_footer("ESPN"),
    ])
    return (text, snapshot) if len(text) <= 3900 else (None, {})


def fetch_standings(session: requests.Session, code: str, year: int) -> list[dict]:
    if code not in LEAGUES:
        raise ValueError("Unapproved ESPN league")
    response = session.get(STANDINGS_URL.format(code=code),
                           params={"season": year}, timeout=(7, 15))
    response.raise_for_status()
    return standings_groups(response.json(), year)


def _counters(ledger: D1Ledger, now: datetime, day: str) -> Counter:
    counter = Counter()
    counter["now"] = now
    counter["daily"] = {str(r.get("ref_id") or "")
                        for r in ledger.rows(live.QUOTA_KIND, day)}
    counter["slots"] = {str(r.get("ref_id") or "")
                        for r in ledger.rows(live.SLOT_KIND, day)}
    counter["seen"] = {str(r.get("ref_id") or "")
                       for r in ledger.rows(live.POST_KIND, day)}
    return counter


def _ever_reserved(ledger: D1Ledger, ref: str) -> bool:
    return bool(ledger.query(
        "SELECT ref_id FROM telegram_sent WHERE kind=? AND ref_id=? LIMIT 1",
        (live.POST_KIND, ref),
    ).get("results") or [])


def cycle(now: datetime, *, mode: str = "all", dry_run: bool = False,
          session: requests.Session | None = None, ledger: D1Ledger | None = None,
          channels: dict | None = None, token: str | None = None) -> dict:
    """Single operational entrypoint; dry-run never touches Telegram or D1."""
    now = now.astimezone(timezone.utc)
    if mode not in {"all", "debrief", "standings"}:
        raise ValueError("Invalid V1.2 mode")
    channels = channels if channels is not None else live.config_channels()
    session = session or requests.Session()
    token = token if token is not None else os.getenv("FOOTBALL_NEWS_BOT_TOKEN", "")
    local = now.astimezone(live.TZ)
    day = local.date().isoformat()
    report = {"mode": "dry-run" if dry_run else "production",
              "debrief_candidates": 0, "debrief_sent": 0,
              "standings_leagues": 0, "standings_sent": 0,
              "errors": 0, "skipped_unverified": 0, "skipped_existing": 0}
    do_standings = mode == "standings" or (mode == "all" and local.hour == 22)
    do_debrief = mode in {"all", "debrief"}
    if not dry_run and not token:
        raise RuntimeError("ACTUFOOT_V12_BOT_TOKEN_MISSING")
    if not dry_run:
        ledger = ledger or D1Ledger()
        roles = ({"debrief"} if do_debrief else set()) | ({"scores"} if do_standings else set())
        allowed = live.verified_roles(session, token, channels, roles)
        if roles - allowed:
            raise RuntimeError("ACTUFOOT_V12_CHANNEL_RIGHTS_NOT_VERIFIED")
        counters = _counters(ledger, now, day)
    else:
        allowed, counters = set(), Counter()
    if do_debrief:
        days = [local.date()]
        if local.hour < 5:
            days.append(days[0] - timedelta(days=1))
        fixtures = []
        for match_day in days:
            fixtures.extend(live.fetch_espn_day(session, match_day))
        selected = live.select_matches(fixtures, now)
        for row in selected:
            if str(row.get("state") or "").lower() not in {"post", "finished"}:
                continue
            match_id = str(row["id"])
            handle = channels["debrief"]
            ref = f"{handle}:v12:debrief:{match_id}"
            report["debrief_candidates"] += 1
            if not dry_run and _ever_reserved(ledger, ref):
                report["skipped_existing"] += 1
                continue
            if not dry_run:
                kickoff = live.football.kick(row)
                fixture_day = kickoff.astimezone(live.TZ).date().isoformat()
                observation, _ = live.state_row(ledger, fixture_day, match_id)
                # Never backfill old completed fixtures that V1.1 didn't follow.
                if not observation or not observation.get("board_id"):
                    report["skipped_unverified"] += 1
                    continue
            try:
                summary = live.normalize_espn_summary(
                    live.fetch_espn_summary(session, match_id, force=True)
                )
                info = live.parse_espn_summary_match(summary)
                output = debrief_message(row, info or {}, summary)
            except (ValueError, TypeError, requests.RequestException):
                report["errors"] += 1
                continue
            if not output:
                report["skipped_unverified"] += 1
                continue
            if dry_run:
                report["debrief_preview"] = output
                continue
            receipt = live.publish(ledger, session, token, handle, day, ref,
                                   output, counters, allowed, "debrief")
            if receipt:
                report["debrief_sent"] += 1
    if do_standings and not dry_run and _ever_reserved(
            ledger, f"{channels['scores']}:v12:standings:{day}"):
        report["skipped_existing"] += 1
        do_standings = False
    if do_standings:
        year = local.year if local.month >= 7 else local.year - 1
        groups = {}
        for code in LEAGUES:
            try:
                parsed = fetch_standings(session, code, year)
                if parsed:
                    groups[code] = parsed
            except (requests.RequestException, ValueError, TypeError, KeyError):
                report["errors"] += 1
        report["standings_leagues"] = len(groups)
        prior = _previous_ranks(ledger, day) if not dry_run else {}
        message, ranks = standings_message(groups, prior, now)
        if message:
            if dry_run:
                report["standings_preview"] = message
            else:
                handle = channels["scores"]
                ref = f"{handle}:v12:standings:{day}"
                receipt = live.publish(ledger, session, token, handle, day, ref,
                                       message, counters, allowed, "scores")
                if receipt:
                    report["standings_sent"] += 1
                    _store_ranks(ledger, day, ranks)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["all", "debrief", "standings"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = cycle(datetime.now(timezone.utc), mode=args.mode, dry_run=args.dry_run)
    # Never put source article text or private D1 values in CI logs.
    report.pop("debrief_preview", None)
    report.pop("standings_preview", None)
    print("ACTUFOOT_V12", json.dumps(report, ensure_ascii=False, sort_keys=True))
    if report["errors"] and not args.dry_run:
        raise SystemExit("ACTUFOOT_V12_SOURCE_ERRORS")


if __name__ == "__main__":
    main()
