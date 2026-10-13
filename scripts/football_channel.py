#!/usr/bin/env python3
"""Mr XPRONOS : six rubriques de football vers un canal Telegram distinct.

Le RSS Foot Mercato vient du projet Actu Poster. Les rencontres proviennent
exclusivement du client BSD V2 du dépôt principal. Aucune opération sur data.json.
Lancer depuis la racine : python scripts/football_channel.py --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, date, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bsd"))
sys.path.insert(0, str(ROOT / "scripts"))
from bsd_api import BSDClient, BSDAPIError  # noqa: E402
from bsd_h2h import hybrid_h2h  # noqa: E402
from free_football_providers import FreeFootballProviders, SPORTSCORE_ATTRIBUTION  # noqa: E402
from telegram_rich import post_photo, post_text, post_animation  # noqa: E402
from football_match_lifecycle import (lifecycle_signals, verify_espn_before_publish, verify_espn_fixtures_before_publish)  # noqa: E402
import football_followup as followup  # noqa: E402
from football_stats_engine import daily_insight  # noqa: E402
from football_viral_engine import (  # noqa: E402
    build_viral_payload, render_animation, media_credit_text, media_credit_url,
)
from football_community_engine import (  # noqa: E402
    build_match_vote,
    build_stats_quiz,
    build_tsdb_club_quiz,
    build_news_debate,
    build_postmatch_reaction,
)

TZ = ZoneInfo("Africa/Lome")
STATE_PATH = Path(os.getenv("FOOTBALL_NEWS_STATE", ".state/mrxpronos-football.json"))
RSS_URL = os.getenv("FOOTBALL_RSS_FEED", "https://www.footmercato.net/flux-rss")
NEWS_CHAT_ENV = "FOOTBALL_NEWS_CHAT_ID"
MAX_MESSAGES_PER_RUN = 2
LIMITS = {"flash": 2, "programme": 1, "avant_match": 2, "resultat": 2,
          "statistique": 1, "sondage": 1, "quiz": 1, "debat": 1,
          "reaction": 1, "viral": 1, "composition": 6, "kickoff": 8,
          "goal": 14, "mi_temps": 8, "score_update": 32, "suivi_interrompu": 8}
LEAGUE_TERMS = (
    "champions league", "premier league", "ligue 1", "la liga", "laliga",
    "serie a", "bundesliga", "europa league", "coupe du monde", "world cup",
    "coupe d'afrique", "afcon", "caf", "uefa", "ligue des champions",
    "can 202", "eredivisie", "liga portugal", "ligue 1 togolaise",
)
TEAM_TERMS = (
    "real madrid", "barcelona", "barcelone", "manchester city", "manchester united",
    "liverpool", "arsenal", "chelsea", "tottenham", "newcastle", "psg",
    "paris saint-germain", "bayern", "inter milan", "juventus", "ac milan",
    "napoli", "marseille", "atletico", "borussia dortmund", "leverkusen",
    "benfica", "porto", "sporting", "ajax", "inter miami", "al ahly",
    "wydad", "esperance", "senegal", "sénégal", "togo", "côte d'ivoire",
    "nigeria", "maroc",
)
ELITE_TEAM_TERMS = (
    "real madrid", "barcelona", "manchester city", "manchester united",
    "liverpool", "arsenal", "chelsea", "psg", "paris saint-germain",
    "bayern", "inter milan", "juventus", "ac milan", "atletico",
    "borussia dortmund",
)
ELITE_LEAGUE_TERMS = (
    "champions league", "ligue des champions", "premier league", "la liga",
    "laliga", "serie a", "bundesliga", "ligue 1", "europa league",
)
CATEGORY_LABELS = {
    "flash": "📰 FLASH FOOT",
    "programme": "📅 MATCHS DU JOUR",
    "avant_match": "🔎 AVANT-MATCH",
    "resultat": "🏁 RÉSULTAT FINAL",
    "statistique": "📊 LA STAT DU JOUR",
    "sondage": "🗳️ VOTE DU JOUR",
    "quiz": "🧠 QUIZ FOOT",
    "debat": "💬 DÉBAT DU JOUR",
    "reaction": "⭐ RÉACTION DU SOIR",
    "viral": "🎬 MOMENT VIRAL",
    "composition": "📋 COMPOSITIONS OFFICIELLES",
    "kickoff": "▶️ COUP D’ENVOI",
    "goal": "⚽ BUT",
    "score_update": "📊 SCORE LIVE",
    "suivi_interrompu": "⚠️ RENCONTRE INTERROMPUE",
    "mi_temps": "⏸️ MI-TEMPS",
}


# Fenêtres éditoriales de production, heure du Togo (GMT).
# GitHub Actions peut démarrer quelques minutes en retard; les fenêtres sont
# volontairement tolérantes et l'historique empêche tout doublon.
EDITORIAL_WINDOWS = {
    "programme": ((6, 45), (7, 45)),      # cible 07h00
    "flash_morning": ((8, 45), (10, 0)),  # cible 09h00
    "statistique": ((12, 15), (13, 15)),  # cible 12h30
    "sondage": ((14, 45), (15, 45)),      # cible 15h00
    "community_evening": ((17, 45), (18, 45)), # cible 18h00
    "viral": ((19, 15), (20, 15)),             # cible 19h30/20h00
    "community_reaction": ((21, 0), (22, 45)), # après les grosses affiches
}
PRODUCTION_START_HOUR = 7
PRODUCTION_END_HOUR = 23


def _minutes_since_midnight(dt: datetime) -> int:
    local = dt.astimezone(TZ)
    return local.hour * 60 + local.minute


def in_editorial_window(name: str, now: datetime) -> bool:
    start, end = EDITORIAL_WINDOWS[name]
    minute = _minutes_since_midnight(now)
    start_minute = start[0] * 60 + start[1]
    end_minute = end[0] * 60 + end[1]
    return start_minute <= minute <= end_minute


def production_active(now: datetime) -> bool:
    hour = now.astimezone(TZ).hour
    return PRODUCTION_START_HOUR <= hour <= PRODUCTION_END_HOUR


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=False)


def plain(value: Any, max_len: int = 500) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", html.unescape(str(value or "")))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_len].rstrip()


def structured_plain(value: Any, max_len: int = 500) -> str:
    """Plain text that keeps meaningful list/newline structure for Telegram."""
    cleaned = re.sub(r"<[^>]+>", " ", html.unescape(str(value or "")))
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    # Recover compact numbered lists such as "1: Texte 2: Texte" without
    # treating scores (1:0), times (12:30) or decimal values as list markers.
    cleaned = re.sub(
        r"(?<!^)(?<!\n)(?<=\S)[ \t]+(?=(?:\d{1,2})[\.:\)]\s+(?=[A-ZÀÂÇÉÈÊËÎÏÔÙÛÜŸŒ]))",
        "\n",
        cleaned,
    )
    lines = [
        re.sub(r"[ \t]+", " ", line).strip()
        for line in cleaned.splitlines()
    ]
    result = "\n".join(line for line in lines if line).strip()
    if len(result) <= max_len:
        return result
    short = result[:max_len]
    if " " in short:
        short = short.rsplit(" ", 1)[0]
    return short.rstrip(" ,;:-") + "…"


def moment(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def kick(event: dict) -> datetime | None:
    return moment(event.get("event_date") or event.get("start_time"))


def score(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        n = int(value)
        return n if n >= 0 and str(value).strip() not in ("", "None") else None
    except (ValueError, TypeError):
        return None


def final_score(event: dict) -> tuple[int, int] | None:
    if str(event.get("status", "")).lower().strip() not in ("finished", "ft", "full_time"):
        return None
    home, away = score(event.get("home_score")), score(event.get("away_score"))
    return (home, away) if home is not None and away is not None else None


def team(event: dict, side: str) -> str:
    value = event.get(side + "_team")
    name = value.get("name") if isinstance(value, dict) else value
    return plain(name, 55)


def league(event: dict) -> str:
    for key in ("league_name", "competition_name", "tournament_name", "league"):
        item = event.get(key)
        value = item.get("name") if isinstance(item, dict) else item
        if isinstance(value, str) and value.strip().casefold() not in ("", "football", "soccer"):
            return plain(value, 70)
    return ""


def sportscore_credit(events: list[dict] | dict) -> str:
    rows = events if isinstance(events, list) else [events]
    for event in rows:
        if not isinstance(event, dict):
            continue
        sources = [str(event.get("source") or "")] + [str(x) for x in (event.get("provider_sources") or [])]
        if any(x.casefold() == "sportscore" for x in sources):
            return '<p><small>Sports data: <a href="https://sportscore.com/">SportScore</a></small></p>'
    return ""


def importance(event: dict) -> int:
    combined = " ".join((league(event), team(event, "home"), team(event, "away"))).lower()
    points = sum(10 for term in LEAGUE_TERMS if term in combined)
    points += sum(5 for term in TEAM_TERMS if term in combined)
    points += sum(18 for term in ELITE_LEAGUE_TERMS if term in combined)
    points += sum(14 for term in ELITE_TEAM_TERMS if term in combined)
    # Une affiche entre deux équipes fortes doit naturellement remonter.
    elite_count = sum(1 for term in ELITE_TEAM_TERMS if term in combined)
    if elite_count >= 2:
        points += 24
    return points

_TSDB_LOGOS: dict[str, str] | None = None
_REMOTE_TEAM_LOGOS: dict[str, str] = {}
_REMOTE_LOGO_REQUESTS = 0
_REMOTE_LOGO_BUDGET = 28

def _norm_team(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", plain(value, 90).casefold()).strip()

def _load_logo_cache() -> dict[str, str]:
    global _TSDB_LOGOS
    if _TSDB_LOGOS is not None:
        return _TSDB_LOGOS
    out: dict[str, str] = {}
    path = ROOT / "cache" / "tsdb_cache.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {}
    if isinstance(payload, dict):
        for item in payload.values():
            if not isinstance(item, dict):
                continue
            for side in ("Home", "Away"):
                name = item.get("str" + side + "Team")
                badge = item.get("str" + side + "TeamBadge")
                if name and isinstance(badge, str) and badge.startswith(("https://", "http://")):
                    out[_norm_team(name)] = badge
    _TSDB_LOGOS = out
    return out

def _remote_team_logo(name: str) -> str:
    """Resolve a missing badge sparingly via TheSportsDB v1."""
    global _REMOTE_LOGO_REQUESTS
    key = _norm_team(name)
    if not key:
        return ""
    if key in _REMOTE_TEAM_LOGOS:
        return _REMOTE_TEAM_LOGOS[key]
    if _REMOTE_LOGO_REQUESTS >= _REMOTE_LOGO_BUDGET:
        return ""
    _REMOTE_LOGO_REQUESTS += 1
    try:
        response = requests.get(
            "https://www.thesportsdb.com/api/v1/json/123/searchteams.php",
            params={"t": name},
            headers={"User-Agent": "MrXPRONOS-logo-resolver/1.0"},
            timeout=(5, 12),
        )
        response.raise_for_status()
        payload = response.json()
        teams = payload.get("teams") if isinstance(payload, dict) else None
        if isinstance(teams, list):
            for item in teams:
                if not isinstance(item, dict):
                    continue
                candidate_name = item.get("strTeam") or ""
                if _norm_team(candidate_name) != key:
                    continue
                badge = item.get("strBadge") or item.get("strTeamBadge") or ""
                if isinstance(badge, str) and badge.startswith(("https://", "http://")):
                    _REMOTE_TEAM_LOGOS[key] = badge
                    return badge
    except (requests.RequestException, ValueError, TypeError):
        pass
    _REMOTE_TEAM_LOGOS[key] = ""
    return ""


def team_visual_url(event: dict, side: str, *, allow_remote: bool = False) -> str:
    """BSD first, then project cache, then optional sparse external lookup."""
    candidates_keys = (
        side + "_team_logo", side + "_logo", side + "_team_badge",
        side + "_badge", side + "_team_image", side + "_image",
    )
    for key in candidates_keys:
        value = event.get(key)
        if isinstance(value, str) and value.startswith(("https://", "http://")):
            return value
    obj = event.get(side + "_team")
    if isinstance(obj, dict):
        for key in ("logo", "logo_url", "badge", "badge_url", "crest", "image", "image_url"):
            value = obj.get(key)
            if isinstance(value, str) and value.startswith(("https://", "http://")):
                return value
    name = team(event, side)
    local = _load_logo_cache().get(_norm_team(name), "")
    if local:
        return local
    return _remote_team_logo(name) if allow_remote else ""


def has_two_team_logos(event: dict, *, allow_remote: bool = False) -> bool:
    """A result/stat card is eligible only when both team logos are known."""
    return bool(
        team_visual_url(event, "home", allow_remote=allow_remote)
        and team_visual_url(event, "away", allow_remote=allow_remote)
    )



def candidates(events: list[dict]) -> list[dict]:
    valid = [e for e in events if e.get("id") is not None
             and team(e, "home") and team(e, "away") and kick(e)]
    return sorted(valid, key=lambda e: (-importance(e), kick(e), str(e["id"])))


def time_label(dt: datetime) -> str:
    return dt.astimezone(TZ).strftime("%Hh%M")


def post_label(text: str) -> str:
    return (text
            + "\n\n<b>💬 Donne ton avis dans les commentaires.</b>"
            + "\n<i>⚽ Mr XPRONOS • L'actualité du football</i>")


class History:
    """Persistant via actions/cache; modification uniquement après succès Telegram."""

    def __init__(self, path: Path = STATE_PATH):
        self.path = path
        self.items: dict[str, dict[str, str]] = {}
        self.followed: dict[str, dict] = {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            entries = payload.get("sent", {}) if isinstance(payload, dict) else {}
            tracked = payload.get("followed", {}) if isinstance(payload, dict) else {}
            if isinstance(tracked, dict):
                self.followed = {str(k): v for k, v in tracked.items() if isinstance(v, dict)}
            if isinstance(entries, dict):
                self.items = {str(k): v for k, v in entries.items() if isinstance(v, dict)}
        except (OSError, ValueError):
            pass

    def seen(self, key: str) -> bool:
        return key in self.items

    def count(self, category: str, today: date) -> int:
        return sum(1 for v in self.items.values()
                   if v.get("category") == category and v.get("day") == today.isoformat())

    def newest(self, category: str) -> datetime | None:
        times = [moment(v.get("at")) for v in self.items.values()
                 if v.get("category") == category]
        times = [t for t in times if t is not None]
        return max(times) if times else None

    def mark(self, key: str, category: str, now: datetime) -> None:
        self.items[key] = {"category": category, "day": now.astimezone(TZ).date().isoformat(),
                           "at": now.isoformat()}

    def save(self, now: datetime) -> None:
        since = now - timedelta(days=32)
        compact = {k: v for k, v in self.items.items()
                   if (moment(v.get("at")) or now) >= since}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="football-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"version": 2, "sent": compact,
                       "followed": followup.active(self.followed, now)},
                      handle, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


@dataclass
class Publication:
    category: str
    key: str
    text: str
    poll: tuple[str, list[str]] | None = None
    card: dict[str, Any] | None = None
    image_path: str | None = None
    keyboard: dict[str, Any] | None = None
    poll_type: str = "regular"
    correct_option_ids: list[int] | None = None
    poll_explanation: str = ""
    poll_description: str = ""
    poll_shuffle: bool = False
    poll_allows_revoting: bool = True
    animation_payload: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None


def _verify_espn_news_reference(session: requests.Session, verification: dict[str, Any]) -> dict[str, Any]:
    """Contrôle non bloquant d'une corroboration ESPN déjà trouvée par le collecteur."""
    url = str(verification.get("url") or "").strip()
    if not url.startswith("https://"):
        return {"ok": False, "quality": 0, "reason": "missing_espn_news_url"}
    host = (urlparse(url).hostname or "").lower()
    if not host.endswith("espn.com"):
        return {"ok": False, "quality": 0, "reason": "invalid_espn_host"}
    expected_terms = {
        plain(x, 50).casefold()
        for x in (verification.get("matched_terms") or [])
        if plain(x, 50)
    }
    try:
        response = session.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; MrXPRONOS-NewsVerifier/1.0)",
                "Accept": "text/html,application/xhtml+xml",
            },
            timeout=(7, 15),
            allow_redirects=True,
        )
        final_host = (urlparse(response.url).hostname or "").lower()
        if not response.ok or not final_host.endswith("espn.com"):
            return {"ok": False, "quality": 75, "reason": "espn_news_page_unavailable", "url": url}
        body = plain(response.text[:600000], 600000).casefold()
        matched = sum(1 for term in expected_terms if term in body)
        content_ok = not expected_terms or matched >= min(2, len(expected_terms))
        return {
            "ok": content_ok,
            "quality": 96 if content_ok else 82,
            "reason": "espn_news_page_confirmed" if content_ok else "espn_news_terms_not_found",
            "url": response.url,
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "quality": 75,
            "reason": "espn_news_page_error",
            "url": url,
            "error": type(exc).__name__,
        }


def _espn_stats_html(enrichment: dict[str, Any], title: str = "📊 Données ESPN") -> str:
    stats = enrichment.get("stats") if isinstance(enrichment, dict) else None
    stats = stats if isinstance(stats, dict) else {}
    home = stats.get("home") if isinstance(stats.get("home"), dict) else {}
    away = stats.get("away") if isinstance(stats.get("away"), dict) else {}
    rows = []
    for label, key in (
        ("Tirs cadrés", "shots_on_target"),
        ("Tirs", "shots"),
        ("Corners", "corners"),
        ("Possession", "possession"),
        ("Fautes", "fouls"),
        ("Hors-jeu", "offsides"),
        ("Arrêts", "saves"),
    ):
        hv, av = home.get(key), away.get(key)
        if hv not in (None, "") and av not in (None, ""):
            rows.append(esc(label) + " : <b>" + esc(hv) + " – " + esc(av) + "</b>")
    if not rows:
        return ""
    return "<p><b>" + esc(title) + "</b><br/>" + "<br/>".join(rows[:5]) + "</p>"


def _apply_espn_preflight_enrichment(item: Publication, result: dict[str, Any]) -> None:
    """Corrige/enrichit l'objet Publication avant que Sender ne génère l'image."""
    if not isinstance(result, dict) or not result.get("ok"):
        return

    verified = result.get("verified") if isinstance(result.get("verified"), list) else []
    if item.category == "programme" and item.card and verified:
        matches = item.card.get("matches") if isinstance(item.card.get("matches"), list) else []
        for card_match in matches:
            if not isinstance(card_match, dict):
                continue
            best = next(
                (
                    row for row in verified
                    if _norm_team(row.get("home")) == _norm_team(card_match.get("home"))
                    and _norm_team(row.get("away")) == _norm_team(card_match.get("away"))
                ),
                None,
            )
            when = moment(best.get("event_date")) if isinstance(best, dict) else None
            if when:
                card_match["time"] = time_label(when)

    if item.category == "avant_match" and verified:
        row = verified[0] if isinstance(verified[0], dict) else {}
        when = moment(row.get("event_date"))
        if item.card and when:
            item.card["time"] = time_label(when)
        venue = plain(row.get("venue"), 100)
        if venue and "🏟" not in item.text:
            item.text += "<p>🏟 <b>" + esc(venue) + "</b></p>"

    enrichment = result.get("enrichment") if isinstance(result.get("enrichment"), dict) else {}
    info = enrichment.get("info") if isinstance(enrichment.get("info"), dict) else {}

    if item.category == "composition":
        context = []
        venue = plain(info.get("venue"), 100)
        if venue:
            context.append("🏟 " + esc(venue))
        referees = [plain(x, 70) for x in (info.get("referees") or []) if plain(x, 70)]
        if referees:
            context.append("👤 Arbitre : " + esc(referees[0]))
        if context and "Arbitre :" not in item.text:
            item.text += "<p>" + "<br/>".join(context) + "</p>"

    if item.category == "mi_temps" and "Données ESPN à la pause" not in item.text:
        block = _espn_stats_html(enrichment, "📊 Données ESPN à la pause")
        if block:
            item.text += block

    if item.category == "resultat" and "📊 Repères du match" not in item.text:
        block = _espn_stats_html(enrichment, "📊 Repères du match")
        if block:
            item.text += block
        goals = enrichment.get("goals") if isinstance(enrichment.get("goals"), list) else []
        if goals and "🎯 Buteurs" not in item.text:
            lines = []
            for goal in goals[:8]:
                if not isinstance(goal, dict):
                    continue
                player = plain(goal.get("player"), 65)
                minute = plain(goal.get("minute_text"), 18)
                if player:
                    suffix = " (pen.)" if goal.get("penalty") else " (c.s.c.)" if goal.get("own_goal") else ""
                    lines.append("⚽ " + esc(player) + suffix + ((" • " + esc(minute)) if minute else ""))
            if lines:
                item.text += "<p><b>🎯 Buteurs ESPN</b><br/>" + "<br/>".join(lines) + "</p>"


def espn_preflight(sender: "Sender", item: Publication, *, dry_run: bool = False) -> bool:
    """Contrôle ESPN juste avant envoi; bloquant pour les faits de match, informatif pour les news."""
    if dry_run or not item.verification:
        return True
    if item.verification.get("type") == "news":
        result = _verify_espn_news_reference(sender.session, item.verification)
        print("ESPN_NEWS_PREFLIGHT", item.category, item.key, json.dumps(result, ensure_ascii=False))
        # La news reste fondée sur sa source journalistique d'origine; ESPN est une corroboration.
        return True

    if item.verification.get("type") == "fixture_list":
        result = verify_espn_fixtures_before_publish(sender.session, item.verification)
        print("ESPN_FIXTURE_PREFLIGHT", item.category, item.key, json.dumps({
            "ok": result.get("ok"),
            "quality": result.get("quality"),
            "reason": result.get("reason"),
            "covered": result.get("covered"),
            "missing": result.get("missing"),
            "total": result.get("total"),
            "contradictions": result.get("contradictions") or [],
        }, ensure_ascii=False))
        if result.get("ok"):
            _apply_espn_preflight_enrichment(item, result)
        return bool(result.get("ok"))

    result = verify_espn_before_publish(sender.session, item.verification)
    print("ESPN_PREFLIGHT", item.category, item.key, json.dumps({
        "ok": result.get("ok"),
        "quality": result.get("quality"),
        "reason": result.get("reason"),
        "event_id": result.get("event_id"),
        "page_verified": (result.get("page") or {}).get("content_verified"),
        "source_url": result.get("source_url"),
    }, ensure_ascii=False))
    accepted = bool(result.get("ok")) and int(result.get("quality") or 0) >= 90
    if accepted:
        _apply_espn_preflight_enrichment(item, result)
    return accepted


class Sender:
    def __init__(self, *, dry_run: bool = False):
        self.dry_run = dry_run
        self.token = (os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or
                      os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        self.chat = os.getenv(NEWS_CHAT_ENV, "").strip()
        self.require_comments = os.getenv("FOOTBALL_REQUIRE_COMMENTS", "1").strip() != "0"
        self.linked_chat_id: int | str | None = None
        self._discussion_checked = False
        if not dry_run and (not self.chat or not self.token):
            raise RuntimeError("Secrets manquants: FOOTBALL_NEWS_CHAT_ID et FOOTBALL_NEWS_BOT_TOKEN (ou TELEGRAM_BOT_TOKEN). Aucune publication vers le canal des pronostics.")
        self.session = requests.Session()

    def verify_discussion(self) -> int | str | None:
        """Vérifie le groupe de discussion Telegram lié au canal.

        Telegram crée nativement le fil de commentaires des posts d'un canal
        lorsqu'un supergroupe est lié. Le Bot API expose ce lien via
        getChat.result.linked_chat_id.
        """
        if self.dry_run:
            return None
        if self._discussion_checked:
            return self.linked_chat_id
        response = self.session.post(
            "https://api.telegram.org/bot" + self.token + "/getChat",
            data={"chat_id": self.chat}, timeout=(12, 30),
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("ok") is not True or not isinstance(payload.get("result"), dict):
            raise RuntimeError("Telegram getChat n'a pas confirmé le canal")
        self.linked_chat_id = payload["result"].get("linked_chat_id")
        self._discussion_checked = True
        if self.require_comments and self.linked_chat_id is None:
            raise RuntimeError(
                "Commentaires requis mais aucun linked_chat_id détecté. "
                "Lier un groupe de discussion au canal Telegram."
            )
        if self.linked_chat_id is not None:
            print("COMMENTAIRES_ACTIFS linked_chat_id", self.linked_chat_id)
        else:
            print("COMMENTAIRES_NON_LIES publication autorisee car FOOTBALL_REQUIRE_COMMENTS=0")
        return self.linked_chat_id

    def send(self, item: Publication) -> int | None:
        if self.dry_run:
            print("DRY_RUN", item.category, item.key, plain(item.text, 900))
            if item.poll:
                print("DRY_RUN_POLL", item.poll)
            if item.keyboard:
                print("DRY_RUN_BUTTONS", json.dumps(item.keyboard, ensure_ascii=False))
            return None
        self.verify_discussion()

        if item.poll:
            question, options = item.poll
            if item.card:
                from football_cards import render_card
                with tempfile.TemporaryDirectory(prefix="xpronos-poll-") as tmp:
                    style = item.category if item.category in {"quiz", "reaction"} else (
                        "community_vote" if item.key.startswith("community-vote:") else "sondage"
                    )
                    graphic = render_card(style, item.card, Path(tmp) / "sondage.png")
                    post_photo(
                        self.session, self.token, self.chat, graphic,
                        "<h3>🗳️ LE DÉBAT DU JOUR • MR XPRONOS</h3><p><i>Votez dans le sondage ci-dessous.</i></p>",
                        {}, timeout=70, mime="image/png",
                    )
            poll_options = [{"text": plain(option, 100)} for option in options if plain(option, 100)]
            if len(poll_options) < 2:
                raise RuntimeError("Sondage Telegram invalide: moins de deux options")
            poll_data = {
                "chat_id": self.chat,
                "question": question[:300],
                "options": json.dumps(poll_options, ensure_ascii=False),
                "is_anonymous": "true",
                "type": item.poll_type if item.poll_type in {"regular", "quiz"} else "regular",
                "allows_multiple_answers": "false",
                "allows_revoting": "true" if item.poll_allows_revoting else "false",
                "shuffle_options": "true" if item.poll_shuffle else "false",
            }
            if item.poll_description:
                poll_data["description"] = plain(item.poll_description, 1024)
            if item.poll_type == "quiz":
                ids = sorted(set(int(x) for x in (item.correct_option_ids or []) if int(x) >= 0))
                if not ids:
                    raise RuntimeError("Quiz Telegram sans réponse correcte")
                poll_data["correct_option_ids"] = json.dumps(ids)
                poll_data["explanation"] = plain(item.poll_explanation, 200)
                poll_data["allows_revoting"] = "false"
            response = self.session.post(
                "https://api.telegram.org/bot" + self.token + "/sendPoll",
                data=poll_data,
                timeout=(12, 55),
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("ok") is not True:
                raise RuntimeError("Telegram n'a pas confirmé le sondage")
            identifier = payload.get("result", {}).get("message_id")
            print("ENVOYE", item.category, item.key, "message_id", identifier)
            return identifier

        if item.animation_payload:
            from football_viral_engine import render_animation
            with tempfile.TemporaryDirectory(prefix="xpronos-viral-") as tmp:
                animation = render_animation(
                    item.animation_payload,
                    Path(tmp) / "viral.mp4",
                    self.session,
                )
                identifier = post_animation(
                    self.session, self.token, self.chat, animation,
                    item.text[:1000], item.keyboard or {},
                    timeout=120, mime="video/mp4",
                )
        elif item.image_path and not item.card:
            media = (ROOT / item.image_path).resolve()
            if not media.is_relative_to(ROOT.resolve()) or not media.is_file():
                raise RuntimeError("Image News Football absente ou hors dépôt: " + str(item.image_path))
            # Le site garde le WebP optimisé; Telegram reçoit la même vraie photo
            # réencodée en JPEG pour une compatibilité sendPhoto maximale.
            from PIL import Image, ImageOps
            with tempfile.TemporaryDirectory(prefix="xpronos-real-news-") as tmp:
                telegram_photo = Path(tmp) / "news.jpg"
                with Image.open(media) as source:
                    ImageOps.exif_transpose(source).convert("RGB").save(
                        telegram_photo, "JPEG", quality=91, optimize=True
                    )
                identifier = post_photo(
                    self.session, self.token, self.chat, telegram_photo,
                    item.text[:3500], item.keyboard or {},
                    timeout=70, mime="image/jpeg",
                )
        elif item.card:
            from football_cards import render_card
            with tempfile.TemporaryDirectory(prefix="xpronos-news-") as tmp:
                graphic_style = (
                    "resultat_suivi" if item.category == "resultat" and
                    item.card.get("_arty_format") == "resultat_suivi"
                    else "statistique_avancee" if item.category == "statistique"
                    and item.key.startswith("statistique-avancee:")
                    else item.category
                )
                graphic = render_card(
                    graphic_style, item.card, Path(tmp) / "publication.png"
                )
                identifier = post_photo(
                    self.session, self.token, self.chat, graphic,
                    item.text[:3500], item.keyboard or {},
                    timeout=70, mime="image/png",
                )
        else:
            identifier = post_text(
                self.session, self.token, self.chat,
                item.text[:3900], item.keyboard,
                timeout=60, html=True,
            )
        print("ENVOYE", item.category, item.key, "message_id", identifier)
        return identifier


def parse_rss(xml_data: bytes) -> list[dict]:
    root = ET.fromstring(xml_data)
    out = []
    for node in root.findall(".//item"):
        title = plain(node.findtext("title"), 190)
        link = (node.findtext("link") or "").strip()
        if not title or not link.startswith(("http://", "https://")):
            continue
        description = clean_news_summary(plain(node.findtext("description"), 420))
        image_url = ""
        for child in node.iter():
            tag = str(child.tag).lower()
            candidate = child.attrib.get("url") or child.attrib.get("href")
            kind = str(child.attrib.get("type") or "").lower()
            if candidate and candidate.startswith(("http://", "https://")) and (
                tag.endswith("thumbnail") or tag.endswith("content") or
                ("enclosure" in tag and kind.startswith("image/"))
            ):
                image_url = candidate
                break
        stamp = node.findtext("pubDate")
        dt = None
        if stamp:
            try:
                dt = parsedate_to_datetime(stamp)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError, IndexError):
                pass
        out.append({"title": title, "url": link, "summary": description,
                    "image": image_url,
                    "date": dt.astimezone(timezone.utc) if dt else None})
    return sorted(out, key=lambda r: r["date"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)


def clean_news_summary(value: str) -> str:
    """Retire URLs, Markdown et résidus de lien des résumés RSS."""
    text = html.unescape(value or "")
    text = re.sub(r'\[([^\]]+)\]\((?:https?://)[^)]+\)', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\[(?:[^\]]+)\]', r'\1', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[\*_~]+', '', text)
    text = re.sub(r'\s+', ' ', text).strip(" -–—|[]()")
    return plain(text, 260)

def fetch_rss(session: requests.Session) -> list[dict]:
    response = session.get(RSS_URL, timeout=(10, 25),
                           headers={"User-Agent": "MrXPRONOS-football-news/1.0"})
    response.raise_for_status()
    return parse_rss(response.content)

def fetch_article_image(session: requests.Session, url: str) -> str:
    """Extract the article's own social image without scraping article text."""
    try:
        response = session.get(
            url, timeout=(10, 25),
            headers={"User-Agent": "Mozilla/5.0 MrXPRONOS-football-news/1.0"},
        )
        response.raise_for_status()
    except requests.RequestException:
        return ""
    page = response.text[:1_500_000]
    patterns = (
        r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image(?::secure_url)?["\']',
        r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image(?::src)?["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, page, flags=re.I)
        if match:
            image = html.unescape(match.group(1)).strip()
            if image.startswith(("https://", "http://")):
                return image
    return ""



def load_site_news(path: Path = ROOT / "footnews.json") -> list[dict]:
    """Lit exactement les actualités enrichies qui alimentent la page Infos Foot."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(payload, list):
        return []
    return sorted(
        (item for item in payload if isinstance(item, dict)),
        key=lambda item: str(item.get("published") or ""),
        reverse=True,
    )


NEWS_LABELS = {
    "Officiel": ("✅", "OFFICIEL"),
    "Blessures": ("🚑", "INFIRMERIE"),
    "Mercato": ("🚨", "MERCATO"),
    "Déclarations": ("🗣️", "DÉCLARATION"),
    "Convocations": ("📋", "SÉLECTION"),
    "Polémique": ("🔥", "POLÉMIQUE"),
    "Afrique": ("🌍", "FOOT AFRIQUE"),
    "Matchs": ("⚽", "MATCH"),
    "Compétitions": ("🏆", "COMPÉTITION"),
    "Actualité": ("🚨", "FLASH FOOT"),
}


def flash(articles: list[dict], history: History, now: datetime) -> Publication | None:
    """Version Telegram courte de la même news complète publiée sur infos.html."""
    last = history.newest("flash")
    if last and now - last < timedelta(hours=3):
        return None
    for article in articles:
        stamp = moment(article.get("published"))
        if stamp is None or not (now - timedelta(hours=30) <= stamp <= now + timedelta(minutes=10)):
            continue
        slug = plain(article.get("slug"), 80)
        source_url = str(article.get("source_url") or article.get("link") or "")
        key = "flash:" + (slug or hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:24])
        if history.seen(key):
            continue
        image_path = str(article.get("image") or "")
        # News Football utilise toujours une vraie photo issue de la source.
        if article.get("image_origin") != "source" or not image_path.startswith("assets/images/footnews/"):
            continue
        if not (ROOT / image_path).is_file():
            continue
        title = plain(article.get("title"), 240)
        summary = structured_plain(article.get("telegram_summary") or article.get("summary"), 430)
        if not title or not summary:
            continue
        category = plain(article.get("category") or "Actualité", 40)
        emoji, label = NEWS_LABELS.get(category, NEWS_LABELS["Actualité"])
        source = plain(article.get("source") or "Source football", 80)
        site_url = str(article.get("site_url") or (
            "https://mrxpronos.github.io/MrXPRONOS_App/infos.html?news=" + slug
        ))
        message = (
            "<b>" + emoji + " " + esc(label) + "</b>\n\n"
            "<b>" + esc(title) + "</b>\n\n"
            "<blockquote>" + esc(summary) + "</blockquote>\n\n"
            "<i>🗞️ Source : " + esc(source) + "</i>\n"
            "<a href=\"" + esc(site_url) + "\">Lire l’info complète sur Mr XPRONOS ↗</a>"
        )
        keyboard_rows = [[
            {"text": "Lire l’info complète ↗", "url": site_url, "style": "primary"}
        ]]
        verification = None
        espn_verification = article.get("espn_verification")
        if isinstance(espn_verification, dict):
            espn_url = str(espn_verification.get("url") or "")
            if espn_url.startswith("https://") and (urlparse(espn_url).hostname or "").lower().endswith("espn.com"):
                keyboard_rows.append([{"text": "Corroboration ESPN ↗", "url": espn_url}])
                verification = {
                    "type": "news",
                    "url": espn_url,
                    "matched_terms": espn_verification.get("matched_terms") or [],
                }
                message += "\n<i>✅ Information aussi repérée chez ESPN.</i>"
        keyboard = {"inline_keyboard": keyboard_rows}
        return Publication(
            "flash", key, message, image_path=image_path,
            keyboard=keyboard, verification=verification,
            card={
                "image_path": image_path,
                "title": title,
                "summary": summary,
                "source": source,
                "day": now.astimezone(TZ).strftime("%d/%m/%Y"),
            },
        )
    return None

def programme(events: list[dict], today: date, *, as_of: datetime | None = None) -> Publication | None:
    future = [e for e in candidates(events) if kick(e).astimezone(TZ).date() == today
              and (as_of is None or kick(e) > as_of)
              and final_score(e) is None
              and str(e.get("status", "")).lower() not in ("cancelled", "postponed", "finished", "live")]
    if not future:
        return None
    chosen = []
    for event in future[:14]:
        if has_two_team_logos(event, allow_remote=True):
            chosen.append(event)
        if len(chosen) >= 5:
            break
    if not chosen:
        return None
    lead = chosen[0]
    lead_league = esc(league(lead) or "Football")
    message = (
        "<h3>📅 MATCHS DU JOUR • MR XPRONOS</h3>"
        "<p><i>Les affiches phares sélectionnées parmi les rencontres BSD du jour. Le suivi intégral est annoncé séparément par AVANT-MATCH.</i></p>"
        "<blockquote><b>🔥 À L'AFFICHE</b><br/>"
        + esc(team(lead, "home")) + " – " + esc(team(lead, "away"))
        + "<br/><b>🕒 " + time_label(kick(lead)) + "</b> • " + lead_league
        + "</blockquote>"
        "<p><b>💬 Quel match attendez-vous le plus ?</b></p>"
        "<p><i>Heure du Togo (GMT) • Le programme complet est sur l'image.</i></p>"
    )
    card = {"day": today.strftime("%d/%m/%Y"), "matches": [
        {"home": team(e, "home"), "away": team(e, "away"), "time": time_label(kick(e)),
         "league": league(e), "importance": importance(e),
         "home_logo": team_visual_url(e, "home", allow_remote=True),
         "away_logo": team_visual_url(e, "away", allow_remote=True)}
        for e in chosen]}
    verification = {
        "type": "fixture_list",
        "kind": "programme",
        "fixtures": [
            {
                "home": team(e, "home"),
                "away": team(e, "away"),
                "event_date": kick(e).astimezone(timezone.utc).isoformat(),
            }
            for e in chosen
        ],
    }
    return Publication(
        "programme", "programme:" + today.isoformat(),
        message, card=card, verification=verification,
    )


def finished_recent(events: list[dict], now: datetime) -> list[dict]:
    return [e for e in candidates(events) if final_score(e) is not None
            and kick(e) < now - timedelta(minutes=85)
            and kick(e) >= now - timedelta(hours=9)]


def resultat(events: list[dict], history: History, now: datetime) -> Publication | None:
    for e in finished_recent(events, now):
        if not has_two_team_logos(e, allow_remote=True):
            continue
        key = "resultat:" + str(e["id"])
        if history.seen(key):
            continue
        a, b = final_score(e)
        outcome = ("🤝 Match nul" if a == b else
                   "🏅 Victoire de " + esc(team(e, "home") if a > b else team(e, "away")))
        text = (
            "<h3>🏁 RÉSULTAT FINAL • MR XPRONOS</h3>"
            "<p><i>" + esc(league(e) or "Football") + "</i></p>"
            "<blockquote><b>⚽ " + esc(team(e, "home")) + "  " + str(a)
            + " – " + str(b) + "  " + esc(team(e, "away")) + "</b><br/>"
            + outcome + "</blockquote>"
            "<p><b>💬 Votre réaction ?</b><br/><i>Les commentaires sont ouverts.</i></p>"
        )
        card = {"day": now.astimezone(TZ).strftime("%d/%m/%Y"),
                "league": league(e), "home": team(e, "home"),
                "away": team(e, "away"), "scores": (a, b),
                "home_logo": team_visual_url(e, "home", allow_remote=True),
                "away_logo": team_visual_url(e, "away", allow_remote=True)}
        verification = {
            "type": "fixture_list",
            "kind": "resultat",
            "fixtures": [{
                "home": team(e, "home"),
                "away": team(e, "away"),
                "event_date": kick(e).astimezone(timezone.utc).isoformat(),
                "score": f"{a}-{b}",
            }],
        }
        return Publication("resultat", key, text, card=card, verification=verification)
    return None


def form(team_id: Any, name: str, events: list[dict], before: datetime) -> str:
    """Forme sur les cinq derniers matchs terminés réellement retrouvés."""
    recent = []
    for e in events:
        when = kick(e)
        result = final_score(e)
        if not when or not result or when >= before:
            continue
        side = None
        for side_name in ("home", "away"):
            current = e.get(side_name + "_team")
            current_id = (current.get("id") if isinstance(current, dict) else
                          e.get(side_name + "_team_id"))
            if team_id is not None and str(current_id) == str(team_id):
                side = side_name
                break
            if team_id is None and team(e, side_name).casefold() == name.casefold():
                side = side_name
                break
        if side:
            scored, conceded = result if side == "home" else result[::-1]
            verdict = "V" if scored > conceded else "N" if scored == conceded else "D"
            recent.append((when, verdict))
    recent.sort(reverse=True)
    vals = [item[1] for item in recent[:5]]
    if not vals:
        return ""
    points = sum(3 if value == "V" else 1 if value == "N" else 0 for value in vals)
    return " • ".join(vals) + "  |  " + str(points) + "/" + str(len(vals) * 3) + " pts"


def fetch_prematch_forms(
    client: BSDClient | None,
    event: dict,
    *,
    session: requests.Session | None = None,
) -> dict[str, str]:
    """Forme récente: SportScore d'abord, BSD seulement en secours."""
    before = kick(event)
    if before is None:
        return {"home": "", "away": ""}
    values: dict[str, str] = {"home": "", "away": ""}
    hub = FreeFootballProviders(session=session or getattr(client, "session", None))
    for side in ("home", "away"):
        obj = event.get(side + "_team")
        team_id = obj.get("id") if isinstance(obj, dict) else event.get(side + "_team_id")
        name = team(event, side)

        free_rows = hub.sportscore_team_schedule(name, limit=10)
        if free_rows:
            values[side] = form(None, name, free_rows, before)
        if values[side] or client is None:
            continue

        try:
            rows = client.list_team_recent_events(
                team_id=int(team_id) if team_id is not None and str(team_id).isdigit() else None,
                team_name=name,
                before=before.astimezone(TZ).date(),
                limit=8,
                ttl=900,
            )
            values[side] = form(team_id, name, rows, before)
        except (BSDAPIError, ValueError, TypeError, requests.RequestException) as exc:
            print("INFO_FORME_EQUIPE", side, name, type(exc).__name__)
    return values


def avant_match(events: list[dict], history: History, now: datetime,
                history_events: list[dict], form_values: dict[str, str] | None = None,
                h2h_values: dict[str, Any] | None = None) -> Publication | None:
    selected = [e for e in candidates(events)
                if timedelta(minutes=65) <= kick(e) - now <= timedelta(minutes=170)
                and final_score(e) is None and not history.seen("avant_match:" + str(e["id"]))]
    selected = [e for e in selected[:10] if has_two_team_logos(e, allow_remote=True)]
    if not selected:
        return None
    e = selected[0]
    def team_id(side: str):
        obj = e.get(side + "_team")
        return obj.get("id") if isinstance(obj, dict) else e.get(side + "_team_id")
    h, a = team(e, "home"), team(e, "away")
    form_values = form_values or {}
    home_form = form_values.get("home") or form(team_id("home"), h, history_events, kick(e))
    away_form = form_values.get("away") or form(team_id("away"), a, history_events, kick(e))
    form_block = ""
    if home_form or away_form:
        rows = []
        if home_form:
            rows.append("<b>" + esc(h) + "</b> : " + esc(home_form))
        if away_form:
            rows.append("<b>" + esc(a) + "</b> : " + esc(away_form))
        form_block = "<p><b>📈 Forme récente</b><br/>" + "<br/>".join(rows) + "</p>"

    h2h_block = ""
    h2h_values = h2h_values or {}
    try:
        total_h2h = int(h2h_values.get("total_matches") or 0)
        home_wins = int(h2h_values.get("home_wins") or 0)
        away_wins = int(h2h_values.get("away_wins") or 0)
        draws = int(h2h_values.get("draws") or 0)
    except (TypeError, ValueError):
        total_h2h = home_wins = away_wins = draws = 0
    if total_h2h >= 2 and home_wins + away_wins + draws == total_h2h:
        avg_goals = h2h_values.get("avg_total_goals")
        avg_text = ""
        try:
            if avg_goals is not None:
                avg_text = "<br/>⚽ Moyenne : " + esc(f"{float(avg_goals):.1f}") + " buts/match"
        except (TypeError, ValueError):
            pass
        h2h_block = (
            "<p><b>🤝 Confrontations directes</b><br/>"
            + esc(str(total_h2h)) + " matchs • "
            + "<b>" + esc(h) + "</b> " + esc(str(home_wins)) + " victoire"
            + ("s" if home_wins != 1 else "")
            + " • " + esc(str(draws)) + " nul" + ("s" if draws != 1 else "")
            + " • <b>" + esc(a) + "</b> " + esc(str(away_wins)) + " victoire"
            + ("s" if away_wins != 1 else "")
            + avg_text
            + "</p>"
        )
    message = (
        "<h3>🔎 AVANT-MATCH • MR XPRONOS</h3>"
        "<p><i>" + esc(league(e) or "Football") + "</i></p>"
        "<blockquote><b>⚽ " + esc(h) + " – " + esc(a) + "</b><br/>"
        "<b>🕒 " + time_label(kick(e)) + "</b> • Heure du Togo</blockquote>"
        + form_block + h2h_block +
        "<p><b>🔖 Nous suivrons cette rencontre jusqu’au résultat final.</b></p>"
        "<p><b>💬 Quel scénario imaginez-vous ?</b></p>"
    )
    card = {
        "day": kick(e).astimezone(TZ).strftime("%d/%m/%Y"),
        "league": league(e) or "Football",
        "home": h, "away": a, "time": time_label(kick(e)),
        "home_form": home_form, "away_form": away_form,
        "h2h_total": total_h2h, "h2h_home_wins": home_wins,
        "h2h_draws": draws, "h2h_away_wins": away_wins,
        "home_logo": team_visual_url(e, "home", allow_remote=True),
        "away_logo": team_visual_url(e, "away", allow_remote=True),
    }
    verification = {
        "type": "fixture_list",
        "kind": "avant_match",
        "fixtures": [{
            "home": h,
            "away": a,
            "event_date": kick(e).astimezone(timezone.utc).isoformat(),
        }],
    }
    return Publication(
        "avant_match", "avant_match:" + str(e["id"]),
        message, card=card, verification=verification,
    )




def viral_publication(
    events: list[dict],
    news: list[dict],
    session: requests.Session,
    now: datetime,
) -> Publication | None:
    payload = build_viral_payload(events, news, session, now, importance)
    if not payload:
        return None
    key = plain(payload.get("key"), 190)
    caption = str(payload.get("caption") or "").strip()
    if not key or not caption:
        return None

    credit = media_credit_text(payload)
    if credit:
        caption += "\n\n<i>🎞️ Fond média : " + esc(credit) + "</i>"
    caption = post_label(caption)

    buttons = []
    target = plain(payload.get("target_url"), 500)
    if target.startswith("https://"):
        buttons.append([{"text": "Voir plus ↗", "url": target, "style": "primary"}])
    credit_url = media_credit_url(payload)
    if credit_url.startswith("https://"):
        buttons.append([{"text": "Crédit média ↗", "url": credit_url}])

    return Publication(
        "viral",
        key,
        caption,
        keyboard={"inline_keyboard": buttons} if buttons else None,
        animation_payload=payload,
    )



def statistique_avancee(session: requests.Session, reference_day: date) -> Publication | None:
    """Statistique quotidienne multi-source, avec fallback ailleurs si indisponible."""
    insight = daily_insight(session, reference_day)
    if not insight:
        return None

    title = plain(insight.get("title"), 120)
    headline = plain(insight.get("headline"), 220)
    lines = [
        plain(line, 180)
        for line in (insight.get("lines") or [])
        if plain(line, 180)
    ][:4]
    source = plain(insight.get("source"), 120)
    confidence = int(insight.get("confidence") or 0)
    if not title or not headline or confidence < 70:
        return None

    details = "".join("<br/>• " + esc(line) for line in lines)
    message = (
        "<h3>" + esc(title) + "</h3>"
        "<blockquote><b>" + esc(headline) + "</b>"
        + details + "</blockquote>"
        "<p><i>Sources : " + esc(source or "source statistique")
        + " • confiance " + str(confidence) + "%</i></p>"
        "<p><b>💬 Quelle statistique veux-tu voir demain ?</b></p>"
    )
    key = (
        "statistique-avancee:"
        + reference_day.isoformat()
        + ":"
        + plain(insight.get("league_key"), 60)
        + ":"
        + plain(insight.get("kind"), 60)
    )
    return Publication(
        "statistique",
        key,
        post_label(message),
        card={
            "headline": headline,
            "title": title,
            "league": insight.get("league"),
            "source": source,
            "lines": lines,
            "value": insight.get("value") or "",
            "kind": insight.get("kind"),
            "confidence": confidence,
        },
    )


def statistique(events: list[dict], reference_day: date) -> Publication | None:
    finished = [e for e in events if final_score(e) is not None and kick(e)]
    if not finished:
        return None
    ranked = sorted(
        finished,
        key=lambda x: (
            -(importance(x) * 3 + min(sum(final_score(x)), 8) * 7),
            -importance(x),
            -sum(final_score(x)),
            str(x.get("id")),
        ),
    )
    e = next(
        (item for item in ranked[:12]
         if has_two_team_logos(item, allow_remote=True)),
        None,
    )
    if e is None:
        return None
    h, a = final_score(e)
    total = h + a
    message = (
        "<h3>📊 LA STAT DU JOUR • MR XPRONOS</h3>"
        "<p><i>Une statistique marquante issue des dernières rencontres BSD avec logos vérifiés.</i></p>"
        "<blockquote><b>🔥 " + str(total) + " BUTS</b><br/>"
        + esc(team(e, "home")) + " <b>" + str(h) + " – " + str(a) + "</b> "
        + esc(team(e, "away")) + "<br/>"
        + "<i>" + esc(league(e) or "Football") + "</i></blockquote>"
        "<p><b>💬 Quelle autre statistique récente vous a marqué ?</b></p>"
    )
    selected_day = kick(e).astimezone(TZ).date()
    card = {"day": selected_day.strftime("%d/%m/%Y"), "league": league(e),
            "home": team(e, "home"), "away": team(e, "away"), "scores": (h, a),
            "home_logo": team_visual_url(e, "home", allow_remote=True),
            "away_logo": team_visual_url(e, "away", allow_remote=True)}
    verification = {
        "type": "fixture_list",
        "kind": "statistique_match",
        "fixtures": [{
            "home": team(e, "home"),
            "away": team(e, "away"),
            "event_date": kick(e).astimezone(timezone.utc).isoformat(),
            "score": f"{h}-{a}",
        }],
    }
    return Publication(
        "statistique", "statistique:" + reference_day.isoformat(),
        message, card=card, verification=verification,
    )



def community_vote_publication(events: list[dict], now: datetime) -> Publication | None:
    payload = build_match_vote(events, now, importance)
    if not payload:
        return None
    question = plain(payload.get("question"), 300)
    options = [plain(x, 100) for x in payload.get("options", []) if plain(x, 100)]
    if not question or len(options) < 2:
        return None
    chosen = next(
        (
            event for event in events
            if team(event, "home") == payload.get("home")
            and team(event, "away") == payload.get("away")
        ),
        None,
    )
    return Publication(
        "sondage",
        plain(payload.get("key"), 180),
        "🗳️ Vote du jour",
        poll=(question, options),
        poll_type="regular",
        poll_description=(
            plain(payload.get("league"), 70)
            + " • Vote avant le coup d'envoi • Mr XPRONOS"
        ),
        poll_allows_revoting=True,
        card={
            "home": payload.get("home"),
            "away": payload.get("away"),
            "league": payload.get("league"),
            "question": question,
            "options": options,
            "home_logo": team_visual_url(chosen, "home") if chosen else "",
            "away_logo": team_visual_url(chosen, "away") if chosen else "",
        },
    )


def community_quiz_publication(session: requests.Session, day: date) -> Publication | None:
    payload = build_stats_quiz(session, day) or build_tsdb_club_quiz(session, day)
    if not payload:
        return None
    question = plain(payload.get("question"), 300)
    options = [plain(x, 100) for x in payload.get("options", []) if plain(x, 100)]
    correct = payload.get("correct_option_ids") or []
    if not question or len(options) < 2 or not correct:
        return None
    return Publication(
        "quiz",
        plain(payload.get("key"), 180),
        "🧠 Quiz Foot",
        poll=(question, options),
        poll_type="quiz",
        correct_option_ids=[int(x) for x in correct],
        poll_explanation=plain(payload.get("explanation"), 200),
        poll_description=(
            "🧠 QUIZ FOOT • "
            + plain(payload.get("league"), 80)
            + " • Données vérifiées par Mr XPRONOS"
        ),
        poll_shuffle=True,
        poll_allows_revoting=False,
        card={
            "question": question,
            "options": options,
            "league": payload.get("league"),
            "source": payload.get("source"),
        },
    )


def community_debate_publication(news: list[dict], day: date) -> Publication | None:
    payload = build_news_debate(news, day)
    if not payload:
        return None
    title = plain(payload.get("title"), 220)
    summary = plain(payload.get("summary"), 340)
    source = plain(payload.get("source"), 80)
    question = plain(payload.get("question"), 240)
    url = plain(payload.get("url"), 420)
    if not title or not summary:
        return None
    message = (
        "<h3>💬 DÉBAT DU JOUR</h3>"
        "<p><b>" + esc(title) + "</b></p>"
        "<blockquote>" + esc(summary) + "</blockquote>"
        + ("<p><i>🗞️ Source : " + esc(source) + "</i></p>" if source else "")
        + "<p><b>" + esc(question) + "</b></p>"
    )
    keyboard = None
    if url.startswith("https://"):
        keyboard = {"inline_keyboard": [[{
            "text": "Lire l'info complète ↗",
            "url": url,
            "style": "primary",
        }]]}
    return Publication(
        "debat",
        plain(payload.get("key"), 180),
        post_label(message),
        keyboard=keyboard,
        card={
            "headline": title,
            "question": title,
            "summary": summary,
            "source": source,
        },
    )


def community_reaction_publication(events: list[dict], now: datetime) -> Publication | None:
    payload = build_postmatch_reaction(events, now, importance)
    if not payload:
        return None
    question = plain(payload.get("question"), 300)
    options = [plain(x, 100) for x in payload.get("options", []) if plain(x, 100)]
    if not question or len(options) < 2:
        return None
    return Publication(
        "reaction",
        plain(payload.get("key"), 180),
        "⭐ Réaction du soir",
        poll=(question, options),
        poll_type="regular",
        poll_description=(
            plain(payload.get("league"), 70)
            + " • Note le match • Mr XPRONOS"
        ),
        poll_allows_revoting=True,
        card={
            "question": question,
            "reaction": question,
            "league": payload.get("league"),
            "score": payload.get("score"),
            "home": payload.get("home"),
            "away": payload.get("away"),
            "home_logo": payload.get("home_logo"),
            "away_logo": payload.get("away_logo"),
        },
    )



def sondage(events: list[dict], history: History, now: datetime) -> Publication:
    today = now.astimezone(TZ).date()
    future = [e for e in candidates(events) if kick(e) > now + timedelta(minutes=20)
              and kick(e) < now + timedelta(hours=34) and final_score(e) is None]
    # Un sondage match n'est créé que si les deux vrais logos sont disponibles.
    # Sinon, on bascule sur un sondage générique plutôt que d'afficher 1 / 3.
    future_with_logos = [
        e for e in future if has_two_team_logos(e, allow_remote=True)
    ]
    if future_with_logos:
        e = future_with_logos[0]
        h, a = team(e, "home"), team(e, "away")
        question = (
            "🗳️ MR XPRONOS • LE DÉBAT DU JOUR\n\n"
            "🔥 " + h + " vs " + a + "\n"
            "Qui prend les 3 points ?"
        )[:300]
        options = ["🏠 " + h, "🤝 Match nul", "✈️ " + a]
        image_question = (h + " vs " + a + " : qui va gagner ?")[:100]
        if max(map(len, options)) <= 100:
            return Publication(
                "sondage", "sondage:" + today.isoformat(),
                "🗳️ Sondage Mr XPRONOS", (question, options),
                card={
                    "day": today.strftime("%d/%m/%Y"),
                    "question": question,
                    "options": options,
                    "image_question": image_question,
                    "image_options": [h, "Match nul", a],
                    "home_logo": team_visual_url(e, "home", allow_remote=True),
                    "away_logo": team_visual_url(e, "away", allow_remote=True),
                },
                verification={
                    "type": "fixture_list",
                    "kind": "sondage",
                    "fixtures": [{
                        "home": h,
                        "away": a,
                        "event_date": kick(e).astimezone(timezone.utc).isoformat(),
                    }],
                },
            )
    topics = [
        ("Quel championnat aimez-vous suivre ?", ["Premier League", "Liga", "Ligue 1", "Autre"]),
        ("Vous préférez quel type de match ?", ["Festival de buts", "Duel tactique", "Derby intense"]),
        ("Qu'aimez-vous lire sur Mr XPRONOS ?", ["Actualités", "Résultats", "Statistiques", "Analyses"]),
        ("Quel contenu souhaitez-vous davantage ?", ["Mercato", "Football africain", "Quiz", "Débats"]),
    ]
    question, options = topics[today.toordinal() % len(topics)]
    question = (question + " 💬 Vote puis commente.")[:300]
    return Publication(
        "sondage", "sondage:" + today.isoformat(), "🗳️ Sondage Mr XPRONOS",
        (question, options),
        card={
            "day": today.strftime("%d/%m/%Y"),
            "question": question,
            "options": options[:3],
            "image_question": re.sub(r"\s*💬.*$", "", question).strip(),
            "image_options": options[:3],
        },
    )



def lifecycle_publication(signal: dict) -> Publication | None:
    """Transforme une transition de match vérifiée en post court Actu Foot."""
    kind = str(signal.get("kind") or "")
    home = plain(signal.get("home"), 55)
    away = plain(signal.get("away"), 55)
    competition = plain(signal.get("league") or "Football", 70)
    source = plain(signal.get("source") or "données live", 50)
    if not home or not away or kind not in {"composition", "kickoff", "goal", "mi_temps", "score_update"}:
        return None

    button_rows = [[{
        "text": "Suivre les matchs LIVE ↗",
        "url": "https://mrxpronos.github.io/MrXPRONOS_App/live.html",
        "style": "primary",
    }]]
    espn_url = plain(signal.get("espn_url"), 500)
    if espn_url.startswith("https://www.espn.com/"):
        button_rows.append([{"text": "Vérifier sur ESPN ↗", "url": espn_url}])
    button = {"inline_keyboard": button_rows}
    card: dict[str, Any] | None = None

    if kind == "composition":
        lineups = signal.get("lineups") if isinstance(signal.get("lineups"), dict) else {}
        home_players = [plain(x, 45) for x in lineups.get("home", []) if plain(x, 45)][:11]
        away_players = [plain(x, 45) for x in lineups.get("away", []) if plain(x, 45)][:11]
        if len(home_players) != 11 or len(away_players) != 11:
            return None
        kickoff_at = signal.get("kickoff")
        kickoff_text = time_label(kickoff_at) if isinstance(kickoff_at, datetime) else ""
        home_block = "<b>" + esc(home) + "</b>\n" + "\n".join(
            str(i + 1) + ". " + esc(name) for i, name in enumerate(home_players)
        )
        away_block = "<b>" + esc(away) + "</b>\n" + "\n".join(
            str(i + 1) + ". " + esc(name) for i, name in enumerate(away_players)
        )
        message = (
            "<h3>📋 COMPOSITIONS OFFICIELLES</h3>"
            "<p><i>" + esc(competition) + (" • " + esc(kickoff_text) if kickoff_text else "") + "</i></p>"
            "<blockquote>" + home_block + "\n\n" + away_block + "</blockquote>"
            "<p><i>Source : " + esc(source) + "</i></p>"
        )

        home_logo = plain(signal.get("home_logo"), 500)
        away_logo = plain(signal.get("away_logo"), 500)
        # Le visuel premium est envoyé seulement lorsque les 11 titulaires et
        # les deux vrais logos sont présents. Sinon l'ancien post texte reste intact.
        if len(home_players) == 11 and len(away_players) == 11 and home_logo and away_logo:
            card = {
                "home": home,
                "away": away,
                "competition": competition,
                "time": kickoff_text,
                "source": source,
                "home_logo": home_logo,
                "away_logo": away_logo,
                "home_players": home_players,
                "away_players": away_players,
            }
    elif kind == "kickoff":
        message = (
            "<h3>▶️ COUP D’ENVOI</h3>"
            "<p><i>" + esc(competition) + "</i></p>"
            "<blockquote><b>⚽ " + esc(home) + " " + esc(signal.get("score") or "0-0")
            + " " + esc(away) + "</b></blockquote>"
            "<p>Le match est lancé"
            + (" • " + esc(str(signal.get("minute"))) + "'" if signal.get("minute") else "")
            + ".</p>"
            "<p><i>Source live : " + esc(source) + "</i></p>"
        )
    elif kind == "score_update":
        message = (
            "<b>📊 SCORE LIVE CONFIRMÉ</b>\n\n"
            "<i>" + esc(competition) + "</i>\n\n"
            "<b>⚽ " + esc(home) + " " + esc(signal.get("score") or "—")
            + " " + esc(away) + "</b>\n"
            + ("⏱ " + esc(str(signal.get("minute"))) + "'\n" if signal.get("minute") else "")
            + "\n<i>Score actuel vérifié • " + esc(source) + "</i>"
        )
    elif kind == "mi_temps":
        message = (
            "<h3>⏸️ MI-TEMPS</h3>"
            "<p><i>" + esc(competition) + "</i></p>"
            "<blockquote><b>" + esc(home) + " " + esc(signal.get("score") or "—")
            + " " + esc(away) + "</b></blockquote>"
            "<p><b>💬 Votre avis sur cette première période ?</b></p>"
            "<p><i>Source live : " + esc(source) + "</i></p>"
        )
    else:
        goal = signal.get("goal") if isinstance(signal.get("goal"), dict) else {}
        scorer = plain(goal.get("player"), 70)
        minute = plain(goal.get("minute_text"), 16) or (
            str(signal.get("minute")) + "'" if signal.get("minute") is not None else ""
        )
        qualifier = ""
        if goal.get("penalty"):
            qualifier = " (pen.)"
        elif goal.get("own_goal"):
            qualifier = " (c.s.c.)"
        scorer_line = (
            "<p><b>🎯 " + esc(scorer) + esc(qualifier) + (" • " + esc(minute) if minute else "") + "</b></p>"
            if scorer else
            ("<p><b>🕒 " + esc(minute) + "</b></p>" if minute else "")
        )
        assists = [plain(x, 60) for x in (goal.get("assists") or []) if plain(x, 60)]
        assist_line = (
            "<p>🅰️ Passe : " + esc(", ".join(assists[:2])) + "</p>"
            if assists else ""
        )
        message = (
            "<h3>⚽ BUUUUT !</h3>"
            "<p><i>" + esc(competition) + "</i></p>"
            "<blockquote><b>" + esc(home) + " " + esc(signal.get("score") or "—")
            + " " + esc(away) + "</b></blockquote>"
            + scorer_line + assist_line +
            "<p><i>Source live : " + esc(source) + "</i></p>"
        )

    if card is None:
        card = {
            "home": home,
            "away": away,
            "competition": competition,
            "league": competition,
            "source": source,
            "score": plain(signal.get("score") or ""),
            "minute": signal.get("minute"),
            "home_logo": plain(signal.get("home_logo") or "", 500),
            "away_logo": plain(signal.get("away_logo") or "", 500),
            "goal": signal.get("goal") or {},
            "time": plain(signal.get("time") or "", 40),
        }

    event_id = plain(signal.get("espn_event_id"), 32)
    verification = None
    if event_id:
        verification = {
            "event_id": event_id,
            "kind": kind,
            "home": home,
            "away": away,
            "score": plain(signal.get("score"), 20),
            "goal": signal.get("goal") if isinstance(signal.get("goal"), dict) else {},
        }
    elif signal.get("event_date"):
        verification = {
            "type": "fixture_list",
            "kind": "resultat" if kind == "resultat_final" else kind,
            "fixtures": [{
                "home": home,
                "away": away,
                "event_date": signal.get("event_date"),
                "score": plain(signal.get("score"), 20),
            }],
        }

    return Publication(
        kind,
        str(signal.get("key") or ""),
        post_label(message + "<p><i>🔖 Match suivi par Mr XPRONOS</i></p>"),
        card=card,
        keyboard=button,
        verification=verification,
    )


def followed_interruption_publication(signal: dict) -> Publication | None:
    home, away = plain(signal.get("home"), 55), plain(signal.get("away"), 55)
    if not home or not away:
        return None
    detail = plain(signal.get("status"), 90)
    text = (
        "<h3>⚠️ CHANGEMENT DE PROGRAMME • MATCH SUIVI</h3>"
        "<p><b>" + esc(home) + " – " + esc(away) + "</b></p>"
        "<p>La rencontre est reportée, suspendue ou annulée selon la source."
        " Nous arrêtons les alertes de ce match tant que sa reprise n'est pas confirmée.</p>"
        "<p><i>Statut : " + esc(detail or "changement signalé") + "</i></p>"
    )
    return Publication(
        "suivi_interrompu",
        str(signal.get("key") or ""),
        post_label(text),
        card={
            "home": home,
            "away": away,
            "league": signal.get("league"),
            "source": signal.get("source"),
            "status": detail,
            "home_logo": signal.get("home_logo"),
            "away_logo": signal.get("away_logo"),
        },
    )


def followed_final_publication(signal: dict) -> Publication | None:
    """Résultat suivi enrichi par les faits ESPN disponibles."""
    home, away = plain(signal.get("home"), 55), plain(signal.get("away"), 55)
    scores = plain(signal.get("score"), 12)
    if not home or not away or not re.fullmatch(r"\d+-\d+", scores):
        return None
    h, a = (int(n) for n in scores.split("-"))
    comp = plain(signal.get("league") or "Football", 80)
    result = ("🤝 Match nul" if h == a else
              "🏅 Victoire de " + esc(home if h > a else away))

    match_data = signal.get("match_data") if isinstance(signal.get("match_data"), dict) else {}
    goals = match_data.get("goals") if isinstance(match_data.get("goals"), list) else []
    goal_lines = []
    for goal in goals[:8]:
        if not isinstance(goal, dict):
            continue
        player = plain(goal.get("player"), 65) or "Buteur non renseigné"
        minute = plain(goal.get("minute_text"), 18)
        suffix = " (pen.)" if goal.get("penalty") else " (c.s.c.)" if goal.get("own_goal") else ""
        goal_lines.append("⚽ " + esc(player) + suffix + ((" • " + esc(minute)) if minute else ""))
    goals_block = (
        "<p><b>🎯 Buteurs</b><br/>" + "<br/>".join(goal_lines) + "</p>"
        if goal_lines else ""
    )

    stats = match_data.get("stats") if isinstance(match_data.get("stats"), dict) else {}
    home_stats = stats.get("home") if isinstance(stats.get("home"), dict) else {}
    away_stats = stats.get("away") if isinstance(stats.get("away"), dict) else {}
    stat_lines = []
    for label, key in (
        ("Tirs cadrés", "shots_on_target"),
        ("Corners", "corners"),
        ("Possession", "possession"),
        ("Fautes", "fouls"),
    ):
        hv, av = home_stats.get(key), away_stats.get(key)
        if hv not in (None, "") and av not in (None, ""):
            stat_lines.append(esc(label) + " : <b>" + esc(hv) + " – " + esc(av) + "</b>")
    stats_block = (
        "<p><b>📊 Repères du match</b><br/>" + "<br/>".join(stat_lines[:4]) + "</p>"
        if stat_lines else ""
    )

    info = match_data.get("info") if isinstance(match_data.get("info"), dict) else {}
    context_lines = []
    venue = plain(info.get("venue"), 100)
    if venue:
        context_lines.append("🏟 " + esc(venue))
    if info.get("attendance") is not None:
        context_lines.append("👥 " + esc(str(info.get("attendance"))) + " spectateurs")
    referees = [plain(x, 70) for x in (info.get("referees") or []) if plain(x, 70)]
    if referees:
        context_lines.append("👤 Arbitre : " + esc(referees[0]))
    context_block = "<p>" + "<br/>".join(context_lines) + "</p>" if context_lines else ""

    message = (
        "<h3>🏁 RÉSULTAT FINAL • MATCH SUIVI</h3>"
        "<p><i>" + esc(comp) + "</i></p>"
        "<blockquote><b>⚽ " + esc(home) + " " + scores.replace("-", " – ")
        + " " + esc(away) + "</b><br/>" + result + "</blockquote>"
        + goals_block + stats_block + context_block +
        "<p>✅ Fin de notre suivi de cette rencontre.</p>"
        "<p><b>💬 Votre avis sur le match ?</b></p>"
        "<p><i>Score confirmé : " + esc(signal.get("source") or "source live") + "</i></p>"
    )
    logo_home = plain(signal.get("home_logo"), 500)
    logo_away = plain(signal.get("away_logo"), 500)
    card = None
    if logo_home.startswith("http") and logo_away.startswith("http"):
        card = {"day": signal.get("day") or "",
                "league": comp, "home": home, "away": away,
                "scores": (h, a), "home_logo": logo_home,
                "away_logo": logo_away}
    if card is None:
        card = {
            "_arty_format": "resultat_suivi",
            "home": home,
            "away": away,
            "score": scores,
            "league": comp,
            "source": signal.get("source") or "score confirmé",
            "home_logo": logo_home,
            "away_logo": logo_away,
        }

    espn_url = plain(signal.get("espn_url"), 500)
    keyboard = None
    if espn_url.startswith("https://www.espn.com/"):
        keyboard = {"inline_keyboard": [[{"text": "Vérifier sur ESPN ↗", "url": espn_url}]]}
    event_id = plain(signal.get("espn_event_id"), 32)
    verification = {
        "event_id": event_id,
        "kind": "resultat_final",
        "home": home,
        "away": away,
        "score": scores,
    } if event_id else None
    if verification is None and signal.get("event_date"):
        verification = {
            "type": "fixture_list",
            "kind": "resultat",
            "fixtures": [{
                "home": home,
                "away": away,
                "event_date": signal.get("event_date"),
                "score": scores,
            }],
        }

    return Publication(
        "resultat",
        str(signal.get("key") or ""),
        post_label(message),
        card=card,
        keyboard=keyboard,
        verification=verification,
    )


def enough(history: History, cat: str, now: datetime) -> bool:
    return history.count(cat, now.astimezone(TZ).date()) < LIMITS[cat]



def run_lifecycle_only(now: datetime, *, dry_run: bool = False, force: bool = False) -> dict[str, int]:
    """Passage léger Actu Foot : aucun RSS, aucune image site, aucun appel BSD.

    Les transitions viennent d'ESPN public et, si disponible, du cache Supabase
    déjà alimenté par notre moteur live BSD+ESPN.
    """
    now = now.astimezone(timezone.utc)
    state = History()
    sender = Sender(dry_run=dry_run)
    counter = {"sent": 0, "skipped": 0, "errors": 0}
    max_send = MAX_MESSAGES_PER_RUN

    def publish(item: Publication | None, *, ref: str = "") -> None:
        if item is None or counter["sent"] >= max_send:
            return
        if not force and (state.seen(item.key) or
                          (item.category != "resultat" and not enough(state, item.category, now))):
            counter["skipped"] += 1
            return
        if not espn_preflight(sender, item, dry_run=dry_run):
            counter["skipped"] += 1
            print("PUBLICATION_BLOQUEE_ESPN", item.category, item.key)
            return
        sender.send(item)
        counter["sent"] += 1
        if not dry_run:
            state.mark(item.key, item.category, now)
            if item.category == "resultat" and ref:
                followup.completed(state.followed, ref, now)
            if item.category == "suivi_interrompu" and ref:
                state.followed[ref]["cancelled"] = True
            state.save(now)

    try:
        tracked = followup.base_events(state.followed, now)
        if not tracked:
            print("FOLLOWUP_NO_SELECTED_MATCH", "fast")
        signals = lifecycle_signals(
            tracked,
            set(state.items.keys()),
            now,
            sender.session,
            importance,
            tracked_only=True,
        )
        used_matches: set[str] = set()
        for signal in signals:
            ref = str(signal.get("follow_ref") or "")
            if not ref or ref not in followup.pending(state.followed, now):
                continue
            kind = signal.get("kind")
            # L'ordre final > but > mi-temps > score est conservé par le moteur.
            match_key = ref
            if match_key in used_matches:
                continue
            post = (followed_final_publication(signal) if kind == "resultat_final"
                    else followed_interruption_publication(signal) if kind == "suivi_interrompu"
                    else lifecycle_publication(signal))
            if post is None:
                continue
            publish(post, ref=ref)
            used_matches.add(match_key)
            if counter["sent"] >= max_send:
                break
    except (requests.RequestException, ValueError, TypeError) as exc:
        counter["errors"] += 1
        print("ERREUR_LIFECYCLE_ONLY", type(exc).__name__, str(exc)[:180])
    finally:
        if not dry_run:
            state.save(now)

    print("XPRONOS_LIFECYCLE", json.dumps(counter), "dry_run", dry_run)
    return counter


def run(now: datetime, *, dry_run: bool = False, force: bool = False) -> dict[str, int]:
    now = now.astimezone(timezone.utc)
    today = now.astimezone(TZ).date()
    hour = now.astimezone(TZ).hour
    state = History()
    sender = Sender(dry_run=dry_run)
    client: BSDClient | None = None
    cache: dict[str, list[dict]] = {}
    counter = {"sent": 0, "skipped": 0, "errors": 0}
    max_send = MAX_MESSAGES_PER_RUN

    free_hub = FreeFootballProviders(session=sender.session)
    free_cache: dict[str, list[dict]] = {}
    FREE_DAY_MIN = max(1, int(os.getenv("FOOTBALL_FREE_DAY_MIN_MATCHES", "12")))

    def _free_day(day: date) -> list[dict]:
        key = day.isoformat()
        if key in free_cache:
            return free_cache[key]
        provider_results = free_hub.day(day)
        merged: list[dict] = []
        for result in provider_results:
            if result.error:
                print("FREE_DAY_INFO", result.provider, result.error[:140])
            for event in result.events:
                duplicate = next(
                    (x for x in merged if free_hub.best_match(event, [x], threshold=.74)),
                    None,
                )
                if duplicate is None:
                    merged.append(event)
                else:
                    replacement = free_hub.merge_facts([duplicate, event])
                    merged[merged.index(duplicate)] = replacement
        free_cache[key] = merged
        if merged:
            print("FREE_DAY", key, "rencontres", len(merged), "appels", dict(free_hub.calls))
        return merged

    def get_day(day: date, *, require_bsd: bool = False) -> list[dict]:
        nonlocal client
        name = day.isoformat()

        free_rows = _free_day(day)
        if not require_bsd and len(free_rows) >= FREE_DAY_MIN:
            return free_rows

        if name not in cache:
            if client is None:
                client = BSDClient(
                    max_requests=int(os.getenv("FOOTBALL_BSD_REQUEST_BUDGET", "18")),
                    max_retries=1,
                )
            page = client.list_events(day, day, max_pages=7, ttl=0)
            if not page.complete:
                raise BSDAPIError(
                    "BSD: journée incomplète " + name + " (" +
                    str(len(page.events)) + "/" + str(page.total_reported) + ")"
                )

            # Conserver les IDs BSD pour les marchés/archives, mais compléter les
            # faits manquants avec les gratuites déjà récupérées.
            enriched = []
            for bsd_event in page.events:
                base = {
                    "home_team": team(bsd_event, "home"),
                    "away_team": team(bsd_event, "away"),
                    "event_date": bsd_event.get("event_date"),
                }
                free_match = free_hub.best_match(base, free_rows, threshold=.68)
                if free_match:
                    bsd_event = dict(bsd_event)
                    bsd_event["free_provider_match"] = free_match
                    bsd_event["provider_sources"] = ["bsd"] + list(free_match.get("provider_sources") or [free_match.get("source")])
                    for key in ("home_logo", "away_logo"):
                        if not bsd_event.get(key) and free_match.get(key):
                            bsd_event[key] = free_match[key]
                enriched.append(bsd_event)
            cache[name] = enriched
            print("BSD_JOUR_FALLBACK", name, "rencontres", len(page.events),
                  "requêtes", client.requests_made, "free", len(free_rows))
        return cache[name]

    def publish(item: Publication | None, *, follow_event: dict | None = None,
                ref: str = "") -> bool:
        if item is None or counter["sent"] >= max_send:
            return False
        if not force and (state.seen(item.key) or
                          (item.category != "resultat" and not enough(state, item.category, now))):
            counter["skipped"] += 1
            return False
        # Une publication AVANT-MATCH ne doit jamais dépasser la capacité de suivi.
        if follow_event is not None:
            if not followup.selection_allowed(state.followed, now):
                return False
            if followup.tracked_fixture(follow_event, state.followed, now):
                return False
        if not espn_preflight(sender, item, dry_run=dry_run):
            counter["skipped"] += 1
            print("PUBLICATION_BLOQUEE_ESPN", item.category, item.key)
            return False
        sender.send(item)
        counter["sent"] += 1
        if not dry_run:
            state.mark(item.key, item.category, now)
            if follow_event is not None:
                ref_added = followup.follow(state.followed, follow_event, now)
                print("FOLLOWUP_SELECTED", ref_added)
            if item.category == "resultat" and ref:
                followup.completed(state.followed, ref, now)
                print("FOLLOWUP_FINISHED", ref)
            if item.category == "suivi_interrompu" and ref:
                state.followed[ref]["cancelled"] = True
                print("FOLLOWUP_INTERRUPTED", ref)
            state.save(now)
        return True

    # Ordre de production :
    # 07h Matchs du jour, 09h Flash, 12h30 Stat, 15h Débat,
    # puis Avant-match / Résultats selon les événements réels.
    try:
        if force or in_editorial_window("programme", now):
            if force or enough(state, "programme", now):
                try:
                    publish(programme(get_day(today), today, as_of=now))
                except (BSDAPIError, requests.RequestException, ValueError) as exc:
                    counter["errors"] += 1
                    print("ERREUR_PROGRAMME", type(exc).__name__, str(exc)[:160])

        if force or in_editorial_window("flash_morning", now):
            if counter["sent"] < max_send and (force or enough(state, "flash", now)):
                try:
                    publish(flash(load_site_news(), state, now))
                except (ET.ParseError, requests.RequestException, ValueError) as exc:
                    counter["errors"] += 1
                    print("ERREUR_RSS_MATIN", type(exc).__name__, str(exc)[:160])

        if force or in_editorial_window("statistique", now):
            if counter["sent"] < max_send and (force or enough(state, "statistique", now)):
                try:
                    reference = today
                    post = statistique_avancee(sender.session, reference)
                    if post is None:
                        fallback_day = today - timedelta(days=1)
                        recent = get_day(fallback_day) + get_day(today)
                        post = statistique(recent, fallback_day)
                        if post is None:
                            older = fallback_day - timedelta(days=1)
                            post = statistique(get_day(older), fallback_day)
                    publish(post)
                except (BSDAPIError, requests.RequestException, ValueError) as exc:
                    counter["errors"] += 1
                    print("ERREUR_STAT", type(exc).__name__, str(exc)[:160])

        if force or in_editorial_window("sondage", now):
            if counter["sent"] < max_send and (force or enough(state, "sondage", now)):
                try:
                    # Le sondage lié à un match doit concerner un match déjà choisi.
                    tracked_vote = followup.base_events(state.followed, now)
                    post = community_vote_publication(tracked_vote, now) if tracked_vote else None
                    publish(post or sondage([], state, now))
                except (BSDAPIError, requests.RequestException, ValueError) as exc:
                    # Le sondage éditorial générique reste le dernier fallback.
                    counter["errors"] += 1
                    print("ERREUR_COMMUNITY_VOTE", type(exc).__name__, str(exc)[:160])
                    publish(sondage([], state, now))

        if force or in_editorial_window("community_evening", now):
            if counter["sent"] < max_send:
                try:
                    # Un jour sur deux on privilégie le quiz, l'autre le débat.
                    # En cas d'indisponibilité, l'autre format prend immédiatement le relais.
                    if today.toordinal() % 2 == 0:
                        post = (
                            community_quiz_publication(sender.session, today)
                            if (force or enough(state, "quiz", now))
                            else None
                        )
                        if post is None and (force or enough(state, "debat", now)):
                            post = community_debate_publication(load_site_news(), today)
                    else:
                        post = (
                            community_debate_publication(load_site_news(), today)
                            if (force or enough(state, "debat", now))
                            else None
                        )
                        if post is None and (force or enough(state, "quiz", now)):
                            post = community_quiz_publication(sender.session, today)
                    publish(post)
                except (requests.RequestException, ValueError, TypeError) as exc:
                    counter["errors"] += 1
                    print("ERREUR_COMMUNITY_EVENING", type(exc).__name__, str(exc)[:160])

        if production_active(now) and counter["sent"] < max_send:
            try:
                matches = get_day(today)
                # En soirée on prépare aussi les matchs du lendemain.
                if hour >= 20:
                    matches = matches + get_day(today + timedelta(days=1))

                # Avant-match : une seule sélection éditoriale, enregistrée
                # exclusivement APRÈS confirmation de Telegram.
                upcoming = [
                    e for e in candidates(matches)
                    if timedelta(minutes=65) <= kick(e) - now <= timedelta(minutes=170)
                    and final_score(e) is None
                    and str(e.get("status") or "").lower() not in
                        ("cancelled", "postponed", "live", "finished")
                    and not state.seen("avant_match:" + str(e["id"]))
                    and not followup.tracked_fixture(e, state.followed, now)
                ]
                if (counter["sent"] < max_send and upcoming
                        and followup.selection_allowed(state.followed, now)
                        and (force or enough(state, "avant_match", now))):
                    selected = next(
                        (e for e in upcoming[:12] if has_two_team_logos(e, allow_remote=True)),
                        None,
                    )
                    if selected:
                        forms = fetch_prematch_forms(client, selected, session=sender.session)
                        h2h_values = {}
                        try:
                            h2h_values = hybrid_h2h(
                                client, selected, [], min_local_meetings=3,
                                allow_api=True, now=now,
                            )
                        except (BSDAPIError, ValueError, TypeError) as exc:
                            print("H2H_AVANT_MATCH_INDISPONIBLE", type(exc).__name__, str(exc)[:140])
                        post = avant_match([selected], state, now, [], forms, h2h_values)
                        publish(post, follow_event=selected)

                # Les événements du moteur LIVE et les résultats sont désormais
                # limités aux rencontres annoncées par AVANT-MATCH.
                tracked = followup.base_events(state.followed, now)
                if counter["sent"] < max_send and tracked:
                    signals = lifecycle_signals(
                        tracked, set(state.items.keys()), now,
                        sender.session, importance, tracked_only=True,
                    )
                    used_matches: set[str] = set()
                    for signal in signals:
                        ref = str(signal.get("follow_ref") or "")
                        if not ref or ref in used_matches or ref not in followup.pending(state.followed, now):
                            continue
                        post = (followed_final_publication(signal)
                                if signal.get("kind") == "resultat_final"
                                else followed_interruption_publication(signal)
                                if signal.get("kind") == "suivi_interrompu"
                                else lifecycle_publication(signal))
                        if post and publish(post, ref=ref):
                            used_matches.add(ref)
                        if counter["sent"] >= max_send:
                            break

                # Fallback BSD: la source ESPN/cache peut manquer un match déjà
                # fini; utiliser alors le statut FT et le score officiels BSD.
                if counter["sent"] < max_send:
                    for event in matches:
                        ref = followup.tracked_fixture(event, state.followed, now)
                        final = final_score(event)
                        if not ref or final is None or state.seen("resultat:" + ref):
                            continue
                        h, a = final
                        obj_home, obj_away = event.get("home_team"), event.get("away_team")
                        sig = {
                            "key": "resultat:" + ref,
                            "home": team(event, "home"), "away": team(event, "away"),
                            "league": league(event), "score": f"{h}-{a}",
                            "home_logo": obj_home.get("logo") if isinstance(obj_home, dict) else "",
                            "away_logo": obj_away.get("logo") if isinstance(obj_away, dict) else "",
                            "source": "BSD V2", "day": now.strftime("%d/%m/%Y"),
                            "event_date": kick(event).astimezone(timezone.utc).isoformat(),
                        }
                        if publish(followed_final_publication(sig), ref=ref):
                            break
            except (BSDAPIError, requests.RequestException, ValueError) as exc:
                counter["errors"] += 1
                print("ERREUR_BSD_MATCH", type(exc).__name__, str(exc)[:160])

        if (force or in_editorial_window("viral", now)) and counter["sent"] < max_send:
            if force or enough(state, "viral", now):
                try:
                    tracked_viral = [event for event in get_day(today)
                                     if any(followup.same_fixture(event, item)
                                            for item in followup.active(state.followed, now).values())]
                    publish(viral_publication(tracked_viral, load_site_news(), sender.session, now))
                except (BSDAPIError, requests.RequestException, ValueError, TypeError, OSError) as exc:
                    counter["errors"] += 1
                    print("ERREUR_VIRAL", type(exc).__name__, str(exc)[:180])

        if (force or in_editorial_window("community_reaction", now)) and counter["sent"] < max_send:
            if force or enough(state, "reaction", now):
                try:
                    tracked_reaction = [event for event in get_day(today)
                                        if any(followup.same_fixture(event, item)
                                               for item in followup.active(state.followed, now).values())]
                    publish(community_reaction_publication(tracked_reaction, now))
                except (BSDAPIError, requests.RequestException, ValueError, TypeError) as exc:
                    counter["errors"] += 1
                    print("ERREUR_COMMUNITY_REACTION", type(exc).__name__, str(exc)[:160])

        # Deuxième Flash possible plus tard dans la journée si une nouvelle actu
        # est disponible et que l'espacement minimum de 3h est respecté.
        local_hour = now.astimezone(TZ).hour
        if (17 <= local_hour <= 23 and counter["sent"] < max_send
                and (force or enough(state, "flash", now))):
            try:
                publish(flash(load_site_news(), state, now))
            except (ET.ParseError, requests.RequestException, ValueError) as exc:
                counter["errors"] += 1
                print("ERREUR_RSS_SOIR", type(exc).__name__, str(exc)[:160])
    finally:
        if not dry_run:
            state.save(now)
    print("XPRONOS_FOOTBALL", json.dumps(counter), "dry_run", dry_run)
    return counter




def run_live_test(now: datetime) -> dict[str, Any]:
    """Envoie une fois six publications de verification reelles, marquees TEST.

    Les scores, les rencontres et les titres RSS restent authentiques. Les tests
    ne consomment PAS les quotas editoriaux et ne modifient PAS l'historique.
    Une erreur sur une rubrique n'empeche pas d'examiner les cinq autres.
    """
    now = now.astimezone(timezone.utc)
    today = now.astimezone(TZ).date()
    sender = Sender(dry_run=False)
    with tempfile.TemporaryDirectory(prefix="xpronos-test-historique-") as tmp:
        empty_history = History(Path(tmp) / "none.json")
        api = BSDClient(max_requests=int(os.getenv("FOOTBALL_BSD_REQUEST_BUDGET", "18")),
                        max_retries=1)
        cache: dict[str, list[dict]] = {}
        report: dict[str, Any] = {"mode": "live-test", "sent": {}, "skipped": {},
                                  "errors": {}}

        def day_events(day: date) -> list[dict]:
            key = day.isoformat()
            if key not in cache:
                page = api.list_events(day, day, max_pages=8, ttl=0)
                if not page.complete:
                    raise BSDAPIError("Liste BSD incomplete " + key)
                cache[key] = page.events
                print("TEST_BSD", key, "rencontres", len(page.events))
            return cache[key]

        def deliver(category: str, make) -> None:
            try:
                post = make()
                if not post:
                    report["skipped"][category] = "Pas de donnees verifiees"
                    print("TEST_INDISPONIBLE", category)
                    return
                # Les tests sont identifiables dans le canal pour permettre
                # de les effacer ensuite sans confusion avec l'edition normale.
                if post.poll:
                    question, choices = post.poll
                    post.poll = ("[TEST] " + question, choices)
                else:
                    post.text = "<b>🧪 TEST DE PUBLICATION — MR XPRONOS</b>\n\n" + post.text
                mid = sender.send(post)
                report["sent"][category] = mid
            except Exception as exc:
                report["errors"][category] = type(exc).__name__ + ": " + str(exc)[:180]
                print("TEST_ECHEC", category, report["errors"][category])

        def actual_programme() -> Publication | None:
            post = programme(day_events(today), today, as_of=now)
            # Si tous les matchs de ce jour sont deja commences, prendre demain,
            # sans falsifier les horaires ou scores.
            if not post:
                post = programme(day_events(today + timedelta(days=1)),
                                 today + timedelta(days=1), as_of=now)
                if post:
                    post.text = post.text.replace("MATCHS DU JOUR", "MATCHS DE DEMAIN")
            return post

        def actual_before() -> Publication | None:
            today_events = day_events(today)
            tomorrow_events = day_events(today + timedelta(days=1))
            future = [e for e in candidates(today_events + tomorrow_events)
                      if kick(e) > now + timedelta(minutes=20)
                      and final_score(e) is None]
            match = next(
                (e for e in future[:20]
                 if has_two_team_logos(e, allow_remote=True)),
                None,
            )
            if match is None:
                return None
            # Emulate a 2h-before-kickoff publication with real fixture/logos/forms.
            virtual_now = kick(match) - timedelta(hours=2)
            forms = fetch_prematch_forms(api, match)
            return avant_match([match], empty_history, virtual_now, [], forms)

        def actual_result() -> Publication | None:
            yesterday = day_events(today - timedelta(days=1))
            today_events = day_events(today)
            finished = [e for e in candidates(today_events + yesterday)
                        if final_score(e) is not None and kick(e) < now]
            finished = [
                e for e in finished[:8]
                if has_two_team_logos(e, allow_remote=True)
            ]
            if not finished:
                return None
            match = sorted(finished, key=lambda e: (-importance(e),
                            -kick(e).timestamp()))[0]
            # For a verified finished match, result() needs a 2h-old kickoff
            # for its 'recent' editorial window.
            virtual_now = kick(match) + timedelta(hours=2)
            return resultat([match], empty_history, virtual_now)

        def actual_stat() -> Publication | None:
            yesterday = today - timedelta(days=1)
            recent = day_events(yesterday) + day_events(today)
            post = statistique(recent, yesterday)
            if post:
                return post
            return statistique(day_events(yesterday - timedelta(days=1)), yesterday)

        def actual_flash() -> Publication | None:
            return flash(load_site_news(), empty_history, now)

        def actual_poll() -> Publication:
            return sondage(day_events(today), empty_history, now)

        for category, maker in [
            ("programme", actual_programme),
            ("avant_match", actual_before),
            ("resultat", actual_result),
            ("statistique", actual_stat),
            ("flash", actual_flash),
            ("sondage", actual_poll),
        ]:
            deliver(category, maker)
        print("XPRONOS_TEST_LIVE", json.dumps(report, ensure_ascii=False))
        if report["errors"] or report["skipped"]:
            raise RuntimeError("Verification partielle: consulter XPRONOS_TEST_LIVE")
        return report


def run_visual_live_test(now: datetime) -> dict[str, Any]:
    """Envoie uniquement Matchs du jour + Statistique dans le vrai canal.

    Destine aux validations visuelles. Les donnees viennent de BSD V2, les
    messages sont clairement marques TEST et aucun historique n'est modifie.
    """
    now = now.astimezone(timezone.utc)
    today = now.astimezone(TZ).date()
    sender = Sender(dry_run=False)
    api = BSDClient(max_requests=int(os.getenv("FOOTBALL_BSD_REQUEST_BUDGET", "18")),
                    max_retries=1)
    cache: dict[str, list[dict]] = {}
    report: dict[str, Any] = {"mode": "visual-live-test", "sent": {},
                              "skipped": {}, "errors": {}}

    def day_events(day: date) -> list[dict]:
        key = day.isoformat()
        if key not in cache:
            page = api.list_events(day, day, max_pages=8, ttl=0)
            if not page.complete:
                raise BSDAPIError("Liste BSD incomplete " + key)
            cache[key] = page.events
            print("VISUAL_TEST_BSD", key, "rencontres", len(page.events))
        return cache[key]

    def deliver(category: str, item: Publication | None) -> None:
        if item is None:
            report["skipped"][category] = "Pas de donnees verifiees"
            print("VISUAL_TEST_INDISPONIBLE", category)
            return
        item.text = "<b>🧪 TEST VISUEL — MR XPRONOS</b>\n\n" + item.text
        mid = sender.send(item)
        report["sent"][category] = mid

    try:
        post = programme(day_events(today), today, as_of=now)
        if post is None:
            tomorrow = today + timedelta(days=1)
            post = programme(day_events(tomorrow), tomorrow, as_of=now)
            if post:
                post.text = post.text.replace("MATCHS DU JOUR", "MATCHS DE DEMAIN")
        deliver("programme", post)
    except Exception as exc:
        report["errors"]["programme"] = type(exc).__name__ + ": " + str(exc)[:180]
        print("VISUAL_TEST_ECHEC programme", report["errors"]["programme"])

    try:
        yesterday = today - timedelta(days=1)
        recent = day_events(yesterday) + day_events(today)
        post = statistique(recent, yesterday)
        if post is None:
            post = statistique(day_events(yesterday - timedelta(days=1)), yesterday)
        deliver("statistique", post)
    except Exception as exc:
        report["errors"]["statistique"] = type(exc).__name__ + ": " + str(exc)[:180]
        print("VISUAL_TEST_ECHEC statistique", report["errors"]["statistique"])

    print("XPRONOS_VISUAL_TEST_LIVE", json.dumps(report, ensure_ascii=False))
    if report["errors"] or report["skipped"]:
        raise RuntimeError("Verification visuelle partielle")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="6 publications automatiques Mr XPRONOS")
    parser.add_argument("--dry-run", action="store_true", help="Simulation sans Telegram, ni historique")
    parser.add_argument("--live-test", action="store_true",
                        help="Envoie les six rubriques TEST au vrai canal, sans historique")
    parser.add_argument("--check-comments", action="store_true",
                        help="Verifie le groupe de discussion lie, sans publier")
    parser.add_argument("--visual-test", action="store_true",
                        help="Envoie Matchs du jour + Statistique au vrai canal")
    parser.add_argument("--force", action="store_true", help="Ignorer les limites et l'historique (test manuel)")
    parser.add_argument("--lifecycle-only", action="store_true",
                        help="Surveille uniquement composition/kickoff/but/mi-temps, sans RSS ni BSD")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    if args.check_comments:
        if args.dry_run or args.force or args.live_test or args.visual_test or args.lifecycle_only:
            parser.error("--check-comments doit etre utilise seul")
        sender = Sender(dry_run=False)
        linked = sender.verify_discussion()
        print("XPRONOS_COMMENTS_OK", linked)
    elif args.visual_test:
        if args.dry_run or args.force or args.live_test or args.lifecycle_only:
            parser.error("--visual-test doit etre utilise seul")
        run_visual_live_test(now)
    elif args.live_test:
        if args.dry_run or args.force or args.lifecycle_only:
            parser.error("--live-test ne peut pas etre combine avec --dry-run/--force/--lifecycle-only")
        run_live_test(now)
    elif args.lifecycle_only:
        run_lifecycle_only(now, dry_run=args.dry_run, force=args.force)
    else:
        run(now, dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    main()
