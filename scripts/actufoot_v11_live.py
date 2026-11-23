#!/usr/bin/env python3
"""Actu Foot V1.1 : scores LIVE et événements ESPN vers les canaux thématiques.

Ce programme est indépendant du RSS V1 et du canal Telegram principal.
Il observe uniquement les affiches éditorialement importantes, confronte le
score au résumé ESPN, met à jour une carte de score unique par match dans le
canal Scores et publie les transitions importantes. Aucune donnée inventée.
Cloudflare D1 garantit la réservation atomique de chaque message avant POST.
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
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import football_channel as football
from scripts.actu_foot_independent import enrich_espn_fixtures, normalize_espn_summary
from scripts.d1_publication_ledger import D1Ledger
from scripts.actufoot_telegram_format import source_footer
from scripts.football_match_lifecycle import (
    fetch_espn_day, fetch_espn_summary, parse_espn_summary_match,
    extract_goals, extract_cards, extract_substitutions, extract_shootout_kicks,
)

TZ = ZoneInfo("Africa/Lome")
CONFIG = ROOT / "config" / "actufoot_v1_channels.json"
STATE_KIND = "actufoot_v11_match_observation"
POST_KIND = "actufoot_v11_live_event"
QUOTA_KIND = "actufoot_v11_daily_quota"
SLOT_KIND = "actufoot_v11_five_minute_slot"
MAX_MATCHES = 5
MAX_PER_RUN = {"scores": 4}
MAX_DAILY = {"scores": 48}
PER_RUN_DEFAULT = 2
DAILY_DEFAULT = 20
MAX_MATCH_HOURS = 5
ALERT_KINDS = {"kickoff", "goal", "score_update", "red", "yellow", "substitution",
               "shootout_made", "shootout_missed", "halftime", "fulltime"}
EXPECTED_ROLES = {
    "flash", "mercato", "champions", "premier", "liga", "ligue1",
    "africa", "national", "scores", "debrief",
}
AFRICAN_NATIONS = re.compile(
    r"\b(togo|benin|senegal|nigeria|ghana|cameroon|cameroun|morocco|maroc|"
    r"algeria|algerie|tunisia|tunisie|mali|burkina|egypt|egypte|"
    r"cote d ivoire|ivory coast)\b"
)


def clean(value: object) -> str:
    """Normalize names without matching arbitrary club abbreviations."""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def config_channels(path: Path = CONFIG) -> dict[str, str]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    channels = obj.get("channels")
    if obj.get("enabled") is not True or obj.get("version") != 1 or not isinstance(channels, dict):
        raise RuntimeError("ACTUFOOT_V11_CONFIG_DISABLED")
    if set(channels) != EXPECTED_ROLES or len(set(channels.values())) != 10:
        raise RuntimeError("ACTUFOOT_V11_CONFIG_INCOMPLETE")
    if any(not re.fullmatch(r"@[A-Za-z][A-Za-z0-9_]{4,31}", v)
           for v in channels.values()):
        raise RuntimeError("ACTUFOOT_V11_CONFIG_PRIVATE_OR_INVALID")
    return channels


def topical_roles(event: dict) -> set[str]:
    """Route by ESPN's *competition* rather than by a team nickname."""
    league = clean(event.get("league_name") or event.get("league") or "")
    home = clean(event.get("home_team"))
    away = clean(event.get("away_team"))
    roles = {"scores"}
    if re.search(r"\b(uefa champions league|ligue des champions de l uefa)\b", league):
        roles.add("champions")
    if re.search(r"\b(english premier league|england premier league)\b", league) or league == "premier league":
        roles.add("premier")
    if re.search(r"\b(spanish la liga|la liga|laliga|primera division)\b", league):
        roles.add("liga")
    if re.search(r"\b(french ligue 1|ligue 1 france|france ligue 1)\b", league) or league == "ligue 1":
        roles.add("ligue1")
    is_africa = bool(re.search(
        r"\b(caf|afcon|african cup of nations|africa cup of nations|"
        r"coupe d afrique|caf champions league)\b", league
    ))
    international = bool(re.search(
        r"\b(world cup|coupe du monde|afcon|africa cup|african cup|"
        r"nations league|international friendly|international friendlies|"
        r"uefa euro|european championship|copa america|world cup qualification|"
        r"world cup qualifying)\b", league
    ))
    if is_africa or (international and
                     (AFRICAN_NATIONS.search(home) or AFRICAN_NATIONS.search(away))):
        roles.add("africa")
    if international:
        roles.add("national")
    return roles


def is_relevant(event: dict) -> bool:
    """A known leading competition or a Top-100 club/national side only."""
    return (
        football.editorial_competition_priority(event) > 0
        or football.live_grand_club_priority(event)[0] > 0
        or bool(topical_roles(event) - {"scores"})
    )


def select_matches(events: list[dict], now: datetime) -> list[dict]:
    eligible = []
    for event in enrich_espn_fixtures(events):
        event_id = str(event.get("id") or "")
        kickoff = football.kick(event)
        state = str(event.get("state") or "").casefold()
        if not event_id.isdigit() or not kickoff or not event.get("home_team") or not event.get("away_team"):
            continue
        age = now - kickoff
        if not timedelta(minutes=-5) <= age <= timedelta(hours=MAX_MATCH_HOURS):
            continue
        if state not in ("in", "post", "finished"):
            continue
        if event.get("home_score") is None or event.get("away_score") is None:
            continue
        if not is_relevant(event):
            continue
        eligible.append(event)
    eligible.sort(key=lambda e: (
        football.live_grand_club_priority(e),
        football.high_stakes_bonus(e),
        football.editorial_competition_priority(e),
        football.importance(e),
    ), reverse=True)
    selected, per_league = [], Counter()
    for event in eligible:
        league = clean(event.get("league_name") or event.get("league"))
        if per_league[league] >= 3:
            continue
        selected.append(event)
        per_league[league] += 1
        if len(selected) >= MAX_MATCHES:
            break
    return selected


def phase(info: dict) -> str:
    state = str(info.get("state") or "").lower()
    detail = clean(info.get("status_detail"))
    if any(t in detail for t in ("postpon", "cancel", "abandon", "suspend")):
        return "interrupted"
    if state in ("post", "finished"):
        return "final"
    if "half time" in detail or "halftime" in detail or detail == "ht":
        return "halftime"
    if state == "in":
        return "live"
    return "unknown"


def valid_summary(row: dict, info: dict | None) -> bool:
    if not isinstance(info, dict) or str(info.get("id")) != str(row.get("id")):
        return False
    if info.get("home_score") is None or info.get("away_score") is None:
        return False
    if info.get("home_team_id") and row.get("home_team_id") and (
        str(info["home_team_id"]) != str(row["home_team_id"])):
        return False
    if info.get("away_team_id") and row.get("away_team_id") and (
        str(info["away_team_id"]) != str(row["away_team_id"])):
        return False
    if clean(info.get("home_team")) != clean(row.get("home_team")):
        return False
    if clean(info.get("away_team")) != clean(row.get("away_team")):
        return False
    return phase(info) != "unknown"


def snapshot(info: dict, previous: dict | None = None) -> dict:
    old = previous or {}
    return {
        "score": f"{info['home_score']}-{info['away_score']}",
        "phase": phase(info),
        "minute": max(0, min(140, int(info.get("minute") or 0))),
        "board_id": old.get("board_id"),
        "board_text": old.get("board_text", ""),
    }


def event_lines(row: dict, state: dict, kind: str, detail: dict | None = None) -> str:
    """Confirmed goals lead with the alert; all other events stay match-first."""
    detail = detail or {}
    score = str(state["score"]).replace("-", "–")
    minute = state.get("minute")
    minute_label = f" · {int(minute)}'" if isinstance(minute, int) and minute > 0 else ""
    home = html.escape(str(row["home_team"]), quote=False)
    away = html.escape(str(row["away_team"]), quote=False)
    match_heading = f"<b>⚽ {home} {html.escape(score)} {away}{minute_label}</b>"
    category = {
        "board": "📡 LE FIL DU MATCH",
        "kickoff": "▶️ C’EST PARTI !",
        "goal": "⚽ BUT CONFIRMÉ",
        "score_update": "🔥 NOUVEAU SCORE CONFIRMÉ",
        "red": "🟥 CARTON ROUGE !",
        "yellow": "🟨 CARTON JAUNE",
        "substitution": "🔁 DU CHANGEMENT !",
        "shootout_made": "⚽ TIR AU BUT MARQUÉ !",
        "shootout_missed": "❌ TIR AU BUT MANQUÉ !",
        "halftime": "⏸️ PAUSE À LA MI-TEMPS",
        "fulltime": "🏁 C’EST TERMINÉ !",
        "recap": "📋 LES SCORES À RETENIR",
    }.get(kind, "📊 ACTU MATCH")
    facts = {
        "board": "📡 Retrouvez ici le score vérifié du match.",
        "kickoff": "▶️ Coup d’envoi confirmé.",
        "score_update": f"📈 <b>Le score vient d’être confirmé : {html.escape(score)}.</b>",
        "red": "🟥 Un carton rouge vient d’être signalé.",
        "yellow": "🟨 Un carton jaune vient d’être signalé.",
        "substitution": "🔁 Changement de joueur confirmé.",
        "shootout_made": "✅ Tir au but marqué.",
        "shootout_missed": "❌ Tir au but manqué.",
        "halftime": "⏸️ La première période est terminée.",
        "fulltime": "🏁 Coup de sifflet final confirmé.",
    }.get(kind, "📊 Informations du match actualisées.")

    # Goals must be recognisable from the Telegram channel preview.
    if kind == "goal":
        description = [match_heading]
        competition = row.get("league_name") or row.get("league")
        if competition:
            description.append("<i>🏆 " + html.escape(str(competition), quote=False) + "</i>")
        if detail.get("player"):
            description.append("👤 <b>" + html.escape(str(detail["player"])[:80], quote=False) + "</b>")
        if detail.get("team"):
            description.append("👕 " + html.escape(str(detail["team"])[:80], quote=False))
        return "\n\n".join([
            f"<b>⚽ BUUUT ! Le score est désormais de {html.escape(score)}.</b>",
            "<blockquote>" + "\n".join(description) + "</blockquote>",
            "<b>🏷 ⚽ BUT CONFIRMÉ</b>\n" + source_footer("ESPN"),
        ])

    lines = [facts]
    if row.get("league_name") or row.get("league"):
        lines.append("<i>🏆 " + html.escape(str(row.get("league_name") or row.get("league"))) + "</i>")
    if detail.get("player"):
        lines.append("👤 <b>" + html.escape(str(detail["player"])[:80]) + "</b>")
    if detail.get("entrant"):
        lines.append("⬆️ " + html.escape(str(detail["entrant"])[:80]))
    if detail.get("sortant"):
        lines.append("⬇️ " + html.escape(str(detail["sortant"])[:80]))
    if detail.get("players") and not detail.get("entrant"):
        lines.append("👥 " + html.escape(", ".join(map(str, detail["players"][:2]))[:120]))
    if detail.get("team"):
        lines.append("👕 " + html.escape(str(detail["team"])[:80]))
    if kind == "board" and state.get("phase") == "halftime":
        lines.append("<i>⏸️ Pause à la mi-temps</i>")
    elif kind == "board" and state.get("phase") == "final":
        lines.append("<i>🏁 Rencontre terminée</i>")
    label = category
    if kind == "score_update":
        label += " · " + html.escape(score)
    return "\n\n".join([
        match_heading,
        "<blockquote>" + "\n".join(lines) + "</blockquote>",
        "<b>🏷 " + label + "</b>\n" + source_footer("ESPN"),
    ])

def derive_events(row: dict, info: dict, summary: dict,
                  previous: dict | None) -> list[tuple[str, str, dict]]:
    """No old goals, no guessed scorer, no unconfirmed score transitions."""
    current = snapshot(info, previous)
    current_phase = current["phase"]
    match_id = str(row["id"])
    output = []
    if previous is None:
        if current_phase == "live" and current["minute"] <= 7:
            output.append(("kickoff", f"kickoff:{match_id}", {}))
        elif current_phase == "halftime":
            output.append(("halftime", f"halftime:{match_id}", {}))
        return output
    if previous.get("score") != current["score"] and current_phase in ("live", "halftime", "final"):
        old = previous.get("score") or ""
        before = re.fullmatch(r"(\d+)-(\d+)", old)
        new = re.fullmatch(r"(\d+)-(\d+)", current["score"])
        inc = (int(new[1]) + int(new[2]) - int(before[1]) - int(before[2])
               if before and new else 0)
        kind, detail = "score_update", {}
        if inc == 1 and int(new[1]) >= int(before[1]) and int(new[2]) >= int(before[2]):
            goals = [
                g for g in extract_goals(summary)
                if isinstance(g, dict)
                and g.get("home_score") == int(new[1])
                and g.get("away_score") == int(new[2])
                and (g.get("minute_total") or g.get("minute") or 0)
                >= max(0, int(previous.get("minute") or 0) - 3)
            ]
            if goals:
                kind = "goal"
                detail = {"player": str(goals[-1].get("player") or "")}
        output.append((kind, f"score:{match_id}:{current['score']}", detail))
    if current_phase == "halftime" and previous.get("phase") != "halftime":
        output.append(("halftime", f"halftime:{match_id}", {}))
    if current_phase == "final" and previous.get("phase") != "final":
        output.append(("fulltime", f"fulltime:{match_id}", {}))
    # Recent source-confirmed timeline events only; do not replay the first observation.
    if current_phase in ("live", "halftime", "final") and current["minute"] >= previous.get("minute", 0):
        for card in extract_cards(summary):
            if not isinstance(card, dict) or str(card.get("type") or "") not in ("red", "yellow"):
                continue
            minute = card.get("minute_total") or card.get("minute")
            if not isinstance(minute, int):
                continue
            if not (minute >= int(previous.get("minute") or 0)
                    and 0 <= current["minute"] - minute <= 18):
                continue
            raw_key = str(card.get("id") or "")
            if not raw_key:
                raw_key = f"{minute}:{clean(card.get('player'))}"
            kind = "red" if card.get("type") == "red" else "yellow"
            output.append((kind, f"{kind}:{match_id}:{raw_key}",
                           {"player": str(card.get("player") or "")}))
        for change in extract_substitutions(summary):
            if not isinstance(change, dict):
                continue
            minute = change.get("minute")
            if not isinstance(minute, int) or not (
                minute >= int(previous.get("minute") or 0)
                and 0 <= current["minute"] - minute <= 18
            ):
                continue
            raw_key = str(change.get("id") or "")
            if not raw_key:
                raw_key = f"{minute}:{clean(change.get('entrant'))}:{clean(change.get('sortant'))}"
            output.append(("substitution", f"sub:{match_id}:{raw_key}", {
                "entrant": str(change.get("entrant") or ""),
                "sortant": str(change.get("sortant") or ""),
                "players": change.get("players") or [],
            }))
        for kick in extract_shootout_kicks(summary):
            if not isinstance(kick, dict) or kick.get("outcome") not in ("made", "missed"):
                continue
            minute = kick.get("minute")
            if not isinstance(minute, int) or not (
                minute >= int(previous.get("minute") or 0)
                and 0 <= current["minute"] - minute <= 18
            ):
                continue
            raw_key = str(kick.get("id") or "")
            if not raw_key:
                raw_key = f"{minute}:{clean(kick.get('player'))}:{clean(kick.get('team'))}:{kick['outcome']}"
            kind = "shootout_" + str(kick["outcome"])
            output.append((kind, f"{kind}:{match_id}:{raw_key}", {
                "player": str(kick.get("player") or ""),
                "team": str(kick.get("team") or ""),
            }))
    return output


def bot_api(session: requests.Session, token: str, method: str, data: dict):
    try:
        response = session.post(
            f"https://api.telegram.org/bot{token}/{method}",
            data=data, timeout=(7, 20))
        parsed = response.json()
        if response.status_code != 200 or parsed.get("ok") is not True:
            raise RuntimeError("TELEGRAM_API_REJECTED_" + str(response.status_code))
        return parsed["result"]
    except (requests.RequestException, ValueError, KeyError) as exc:
        # Never log a request URL containing the bot token.
        raise RuntimeError("TELEGRAM_API_UNCERTAIN_" + type(exc).__name__) from None


def verified_roles(session: requests.Session, token: str,
                   channels: dict[str, str], roles: set[str]) -> set[str]:
    me = bot_api(session, token, "getMe", {})
    if not me.get("is_bot") or not isinstance(me.get("id"), int):
        raise RuntimeError("ACTUFOOT_V11_UNVERIFIED_BOT")
    allowed = set()
    for role in sorted(roles):
        handle = channels[role]
        try:
            chat = bot_api(session, token, "getChat", {"chat_id": handle})
            member = bot_api(session, token, "getChatMember", {
                "chat_id": handle, "user_id": me["id"]})
            if (chat.get("type") == "channel"
                and "@" + str(chat.get("username") or "").casefold() == handle.casefold()
                and member.get("status") in ("administrator", "creator")
                and (member.get("status") == "creator"
                     or member.get("can_post_messages") is True)):
                allowed.add(role)
        except RuntimeError:
            pass
    return allowed


def state_row(ledger: D1Ledger, day: str, fixture_id: str):
    rows = ledger.query(
        "SELECT selection_snapshot FROM telegram_sent "
        "WHERE kind=? AND ref_id=? AND ref_date=? LIMIT 1",
        (STATE_KIND, fixture_id, day),
    ).get("results") or []
    if not rows:
        return None, None
    raw = rows[0].get("selection_snapshot")
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        raise RuntimeError("ACTUFOOT_V11_STATE_INVALID")
    if not isinstance(data, dict):
        raise RuntimeError("ACTUFOOT_V11_STATE_INVALID")
    return data, raw


def commit_state(ledger: D1Ledger, day: str, fixture_id: str,
                 state: dict, previous_raw: str | None) -> bool:
    raw = json.dumps(state, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    if previous_raw is None:
        result = ledger.query(
            "INSERT OR IGNORE INTO telegram_sent "
            "(id,kind,ref_id,ref_date,sent_at,validation_sent,delivery_status,selection_snapshot) "
            "VALUES (?,?,?,?,?,0,'observed',?)",
            (str(uuid.uuid4()), STATE_KIND, fixture_id, day,
             datetime.now(timezone.utc).isoformat(), raw),
        )
    else:
        result = ledger.query(
            "UPDATE telegram_sent SET selection_snapshot=? WHERE "
            "kind=? AND ref_id=? AND ref_date=? AND selection_snapshot=?",
            (raw, STATE_KIND, fixture_id, day, previous_raw),
        )
    if (result.get("meta") or {}).get("changes") != 1:
        raise RuntimeError("ACTUFOOT_V11_STATE_RACE")
    return True


def event_receipt(ledger: D1Ledger, day: str, ref: str) -> int | None:
    rows = ledger.query(
        "SELECT telegram_message_id FROM telegram_sent "
        "WHERE kind=? AND ref_id=? AND ref_date=? AND delivery_status='sent' LIMIT 1",
        (POST_KIND, ref, day),
    ).get("results") or []
    if not rows:
        return None
    try:
        mid = int(rows[0].get("telegram_message_id"))
        return mid if mid > 0 else None
    except (ValueError, TypeError):
        return None


def publish(ledger: D1Ledger, session: requests.Session, token: str,
            handle: str, day: str, ref: str, text: str,
            counters: dict, allowed: set[str], role: str) -> int | None:
    """Slots and per-day quotas are reserved BEFORE the potentially ambiguous POST."""
    if role not in allowed:
        counters["skipped_rights"] += 1
        return None
    if counters["run:" + handle] >= MAX_PER_RUN.get(role, PER_RUN_DEFAULT):
        counters["skipped_quota"] += 1
        return None
    if ref in counters["seen"]:
        counters["duplicates"] += 1
        return event_receipt(ledger, day, ref)
    existing = event_receipt(ledger, day, ref)
    if existing is not None:
        counters["seen"].add(ref)
        counters["duplicates"] += 1
        return existing
    limit = MAX_DAILY.get(role, DAILY_DEFAULT)
    limit_refs = counters["daily"]
    quota_ref = next(
        (f"{handle}:{i:02d}" for i in range(limit)
         if f"{handle}:{i:02d}" not in limit_refs),
        None)
    if quota_ref is None:
        counters["skipped_quota"] += 1
        return None
    now = counters["now"]
    epoch = int(now.timestamp()) // 300
    slot_ref = next(
        (f"{handle}:{epoch}:{i}" for i in range(MAX_PER_RUN.get(role, PER_RUN_DEFAULT))
         if f"{handle}:{epoch}:{i}" not in counters["slots"]),
        None)
    if slot_ref is None:
        counters["skipped_quota"] += 1
        return None
    if not ledger.claim(SLOT_KIND, slot_ref, day):
        counters["slots"].add(slot_ref)
        counters["skipped_quota"] += 1
        return None
    counters["slots"].add(slot_ref)
    if not ledger.claim(QUOTA_KIND, quota_ref, day):
        counters["daily"].add(quota_ref)
        counters["skipped_quota"] += 1
        return None
    counters["daily"].add(quota_ref)
    if not ledger.claim(POST_KIND, ref, day):
        counters["seen"].add(ref)
        counters["duplicates"] += 1
        return None
    counters["seen"].add(ref)
    counters["run:" + handle] += 1
    try:
        response = bot_api(session, token, "sendMessage", {
            "chat_id": handle, "parse_mode": "HTML",
            "disable_web_page_preview": "true", "text": text,
        })
        mid = int(response.get("message_id"))
        if mid <= 0:
            raise RuntimeError("TELEGRAM_NO_POSITIVE_MESSAGE_ID")
        ledger.mark(POST_KIND, ref, day, message_id=mid)
        counters["sent"] += 1
        counters["channel:" + role] += 1
        return mid
    except (RuntimeError, TypeError, ValueError, KeyError) as exc:
        # A missing/invalid message_id is an ambiguous delivery, NOT success.
        # The D1 reservation stays quarantined and can never be blindly retried.
        status = ("rejected" if isinstance(exc, RuntimeError)
                  and str(exc).startswith("TELEGRAM_API_REJECTED_")
                  else "uncertain")
        ledger.set_status(POST_KIND, ref, day, status)
        counters["errors"] += 1
        return None


def update_board(session: requests.Session, token: str, handle: str,
                 message_id: int, text: str) -> bool:
    try:
        bot_api(session, token, "editMessageText", {
            "chat_id": handle, "message_id": message_id,
            "parse_mode": "HTML", "disable_web_page_preview": "true", "text": text,
        })
        return True
    except RuntimeError:
        return False


def recap_message(selected: list[dict], now: datetime) -> str | None:
    """The first verified match leads; the editorial recap label stays below."""
    rows = []
    for item in selected:
        score_h, score_a = item.get("home_score"), item.get("away_score")
        if not isinstance(score_h, int) or not isinstance(score_a, int):
            continue
        status = "Terminé" if item.get("state") in ("post", "finished") else "En direct"
        home = html.escape(str(item["home_team"]), quote=False)
        away = html.escape(str(item["away_team"]), quote=False)
        rows.append((f"{home} {score_h}–{score_a} {away}", status))
    if not rows:
        return None
    first, first_status = rows[0]
    rest = [
        "• " + score + " · <i>" + status + "</i>"
        for score, status in rows[1:MAX_MATCHES]
    ]
    body = ["<i>📡 " + first_status + " · Score confirmé</i>"] + rest
    return "\n\n".join([
        "<b>⚽ " + first + "</b>",
        "<blockquote>" + "\n".join(body) + "</blockquote>",
        "<b>🏷 📋 TOUR D’HORIZON DES SCORES · "
        + now.astimezone(TZ).strftime("%H:%M") + "</b>\n" + source_footer("ESPN"),
    ])

def cycle(now: datetime, *, dry_run: bool = False,
          session: requests.Session | None = None, ledger: D1Ledger | None = None,
          channels: dict[str, str] | None = None, token: str | None = None):
    now = now.astimezone(timezone.utc)
    channels = channels if channels is not None else config_channels()
    session = session or requests.Session()
    token = token if token is not None else os.getenv("FOOTBALL_NEWS_BOT_TOKEN", "")
    report = {"mode": "dry-run" if dry_run else "production", "eligible": 0,
              "selected": 0, "sent": 0, "edited": 0, "errors": 0,
              "duplicates": 0, "skipped_rights": 0, "skipped_quota": 0,
              "unavailable": 0, "mismatched": 0, "per_channel": {}}
    days = [now.astimezone(TZ).date()]
    if now.astimezone(TZ).hour < 5:
        days.append(days[0] - timedelta(days=1))
    fixtures = []
    for match_day in days:
        fixtures.extend(fetch_espn_day(session, match_day))
    selected = select_matches(fixtures, now)
    report["eligible"] = len(fixtures)
    report["selected"] = len(selected)
    if dry_run:
        report["preview"] = [
            {"id": e["id"], "home": e["home_team"], "away": e["away_team"],
             "roles": sorted(topical_roles(e))}
            for e in selected
        ]
        return report
    if not token:
        raise RuntimeError("ACTUFOOT_V11_BOT_TOKEN_MISSING")
    if not selected:
        return report
    ledger = ledger or D1Ledger()
    all_roles = set().union(*(topical_roles(e) for e in selected))
    allowed = verified_roles(session, token, channels, all_roles)
    if "scores" not in allowed:
        raise RuntimeError("ACTUFOOT_V11_SCORES_DESTINATION_NOT_VERIFIED")
    day = now.astimezone(TZ).date().isoformat()
    counters = Counter()
    counters["now"] = now  # Counter stores an object here as a mapping.
    counters["daily"] = {
        str(row.get("ref_id") or "") for row in ledger.rows(QUOTA_KIND, day)
    }
    counters["slots"] = {
        str(row.get("ref_id") or "") for row in ledger.rows(SLOT_KIND, day)
    }
    counters["seen"] = {
        str(row.get("ref_id") or "") for row in ledger.rows(POST_KIND, day)
    }
    for row in selected:
        kickoff = football.kick(row)
        fixture_day = kickoff.astimezone(TZ).date().isoformat()
        previous, raw = state_row(ledger, fixture_day, str(row["id"]))
        summary = fetch_espn_summary(session, str(row["id"]), force=True)
        if not summary:
            counters["unavailable"] += 1
            continue
        summary = normalize_espn_summary(summary)
        info = parse_espn_summary_match(summary)
        if not valid_summary(row, info):
            counters["mismatched"] += 1
            continue
        current = snapshot(info, previous)
        current_phase = current["phase"]
        # First sight of a completed match must not replay an old score.
        if previous is None and current_phase in ("final", "interrupted"):
            commit_state(ledger, fixture_day, str(row["id"]), current, None)
            continue
        signals = derive_events(row, info, summary, previous)
        board = event_lines(row, current, "board")
        score_handle = channels["scores"]
        board_ref = f"{score_handle}:board:{row['id']}"
        if current_phase not in ("interrupted",) and not current.get("board_id"):
            existing_mid = event_receipt(ledger, day, board_ref)
            if existing_mid:
                current["board_id"] = existing_mid
            else:
                mid = publish(ledger, session, token, score_handle, day,
                              board_ref, board, counters, allowed, "scores")
                if mid:
                    current["board_id"] = mid
                    current["board_text"] = board
        if current.get("board_id") and current.get("board_text") != board:
            if update_board(session, token, score_handle, int(current["board_id"]), board):
                current["board_text"] = board
                counters["edited"] += 1
            else:
                counters["errors"] += 1
        for kind, identity, detail in signals:
            if kind not in ALERT_KINDS:
                continue
            for role in sorted(topical_roles(row)):
                # Scores hosts the persistent board; kickoff is enough on
                # league channels. No redundant kickoff in Scores.
                if role == "scores" and kind == "kickoff":
                    continue
                handle = channels[role]
                text = event_lines(row, current, kind, detail)
                publish(ledger, session, token, handle, day,
                        f"{handle}:{identity}", text, counters, allowed, role)
        if previous is None:
            commit_state(ledger, fixture_day, str(row["id"]), current, None)
        elif current != previous:
            commit_state(ledger, fixture_day, str(row["id"]), current, raw)
    local = now.astimezone(TZ)
    bucket = None
    minute_of_day = local.hour * 60 + local.minute
    if 12 * 60 + 30 <= minute_of_day < 12 * 60 + 40:
        bucket = "midi"
    elif 22 * 60 + 30 <= minute_of_day < 22 * 60 + 40:
        bucket = "soir"
    if bucket:
        recap = recap_message(selected, now)
        if recap:
            publish(ledger, session, token, channels["scores"], day,
                    f"{channels['scores']}:recap:{day}:{bucket}", recap,
                    counters, allowed, "scores")
    for key in ("sent", "edited", "errors", "duplicates", "skipped_rights",
                "skipped_quota", "unavailable", "mismatched"):
        report[key] = counters[key]
    report["per_channel"] = {
        role: counters["channel:" + role] for role in sorted(EXPECTED_ROLES)
    }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = cycle(datetime.now(timezone.utc), dry_run=args.dry_run)
    print("ACTUFOOT_V11_LIVE", json.dumps(report, ensure_ascii=False, sort_keys=True))
    if report["errors"]:
        raise SystemExit("ACTUFOOT_V11_LIVE_DELIVERY_INCOMPLETE")


if __name__ == "__main__":
    main()
