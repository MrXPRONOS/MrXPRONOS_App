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
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bsd"))
sys.path.insert(0, str(ROOT / "scripts"))
from bsd_api import BSDClient, BSDAPIError  # noqa: E402
from telegram_rich import post_photo, post_text  # noqa: E402

TZ = ZoneInfo("Africa/Lome")
STATE_PATH = Path(os.getenv("FOOTBALL_NEWS_STATE", ".state/mrxpronos-football.json"))
RSS_URL = os.getenv("FOOTBALL_RSS_FEED", "https://www.footmercato.net/flux-rss")
NEWS_CHAT_ENV = "FOOTBALL_NEWS_CHAT_ID"
MAX_MESSAGES_PER_RUN = 2
LIMITS = {"flash": 2, "programme": 1, "avant_match": 2, "resultat": 2,
          "statistique": 1, "sondage": 1}
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
    "sondage": "🗳️ LE DÉBAT XPRONOS",
}


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=False)


def plain(value: Any, max_len: int = 500) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", html.unescape(str(value or "")))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_len].rstrip()


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
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            entries = payload.get("sent", {}) if isinstance(payload, dict) else {}
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
                json.dump({"version": 1, "sent": compact}, handle, ensure_ascii=False, indent=2)
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
    keyboard: dict[str, Any] | None = None


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
                    graphic = render_card(
                        "sondage", item.card, Path(tmp) / "sondage.png"
                    )
                    post_photo(
                        self.session, self.token, self.chat, graphic,
                        "<h3>🗳️ LE DÉBAT DU JOUR • MR XPRONOS</h3><p><i>Votez dans le sondage ci-dessous.</i></p>",
                        {}, timeout=70, mime="image/png",
                    )
            response = self.session.post(
                "https://api.telegram.org/bot" + self.token + "/sendPoll",
                data={
                    "chat_id": self.chat,
                    "question": question[:300],
                    "options": json.dumps(options, ensure_ascii=False),
                    "is_anonymous": "true",
                    "allows_multiple_answers": "false",
                },
                timeout=(12, 55),
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("ok") is not True:
                raise RuntimeError("Telegram n'a pas confirmé le sondage")
            identifier = payload.get("result", {}).get("message_id")
            print("ENVOYE", item.category, item.key, "message_id", identifier)
            return identifier

        if item.card:
            from football_cards import render_card
            with tempfile.TemporaryDirectory(prefix="xpronos-news-") as tmp:
                graphic = render_card(
                    item.category, item.card, Path(tmp) / "publication.png"
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



def flash(articles: list[dict], history: History, now: datetime,
          session: requests.Session | None = None) -> Publication | None:
    last = history.newest("flash")
    if last and now - last < timedelta(hours=3):
        return None
    for a in articles:
        stamp = a["date"]
        if stamp is None or not (now - timedelta(hours=22) <= stamp <= now + timedelta(minutes=10)):
            continue
        uid = hashlib.sha256(a["url"].encode("utf-8")).hexdigest()[:24]
        key = "flash:" + uid
        if history.seen(key):
            continue
        msg = (
            "<h3>📰 FLASH FOOT • MR XPRONOS</h3>"
            "<p><b>" + esc(a["title"]) + "</b></p>"
            + ("<p><i>" + esc(a["summary"]) + "</i></p>" if a["summary"] else "")
            + "<blockquote><b>🗞️ SOURCE</b><br/>Foot Mercato</blockquote>"
            + "<p><b>💬 Votre avis ?</b><br/><i>Réagissez dans les commentaires.</i></p>"
            + "<p><i>⚽ Mr XPRONOS • L'actualité du football</i></p>"
        )
        buttons = {"inline_keyboard": [[
            {"text": "Lire sur Foot Mercato ↗", "url": a["url"], "style": "primary"}
        ]]}
        image_url = a.get("image") or ""
        if not image_url and session is not None:
            image_url = fetch_article_image(session, a["url"])
        card = {
            "day": now.astimezone(TZ).strftime("%d/%m/%Y"),
            "title": a["title"],
            "summary": a["summary"],
            "source": "Foot Mercato",
            "image_url": image_url,
        }
        return Publication("flash", key, msg, card=card, keyboard=buttons)
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
        "<p><i>Les affiches phares sélectionnées parmi les rencontres BSD du jour.</i></p>"
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
    return Publication("programme", "programme:" + today.isoformat(),
                       message, card=card)


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
        return Publication("resultat", key, text, card=card)
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


def fetch_prematch_forms(client: BSDClient, event: dict) -> dict[str, str]:
    """Charge les derniers matchs de chaque équipe directement via BSD."""
    before = kick(event)
    if before is None:
        return {"home": "", "away": ""}
    values: dict[str, str] = {"home": "", "away": ""}
    for side in ("home", "away"):
        obj = event.get(side + "_team")
        team_id = obj.get("id") if isinstance(obj, dict) else event.get(side + "_team_id")
        name = team(event, side)
        try:
            rows = client.list_team_recent_events(
                team_id=int(team_id) if team_id is not None else None,
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
                history_events: list[dict], form_values: dict[str, str] | None = None) -> Publication | None:
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
    message = (
        "<h3>🔎 AVANT-MATCH • MR XPRONOS</h3>"
        "<p><i>" + esc(league(e) or "Football") + "</i></p>"
        "<blockquote><b>⚽ " + esc(h) + " – " + esc(a) + "</b><br/>"
        "<b>🕒 " + time_label(kick(e)) + "</b> • Heure du Togo</blockquote>"
        + form_block +
        "<p><b>💬 Quel scénario imaginez-vous ?</b></p>"
    )
    card = {
        "day": kick(e).astimezone(TZ).strftime("%d/%m/%Y"),
        "league": league(e) or "Football",
        "home": h, "away": a, "time": time_label(kick(e)),
        "home_form": home_form, "away_form": away_form,
        "home_logo": team_visual_url(e, "home", allow_remote=True),
        "away_logo": team_visual_url(e, "away", allow_remote=True),
    }
    return Publication("avant_match", "avant_match:" + str(e["id"]), message, card=card)


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
    return Publication("statistique", "statistique:" + reference_day.isoformat(),
                       message, card=card)


def sondage(events: list[dict], history: History, now: datetime) -> Publication:
    today = now.astimezone(TZ).date()
    future = [e for e in candidates(events) if kick(e) > now + timedelta(minutes=20)
              and kick(e) < now + timedelta(hours=34) and final_score(e) is None]
    if future:
        e = future[0]
        h, a = team(e, "home"), team(e, "away")
        question = (
            "🗳️ MR XPRONOS • LE DÉBAT DU JOUR\n\n"
            "🔥 " + h + " vs " + a + "\n"
            "Qui prend les 3 points ?"
        )[:300]
        options = ["🏠 " + h, "🤝 Match nul", "✈️ " + a]
        if max(map(len, options)) <= 100:
            return Publication(
                "sondage", "sondage:" + today.isoformat(),
                "🗳️ Sondage Mr XPRONOS", (question, options),
                card={"day": today.strftime("%d/%m/%Y"),
                      "question": question, "options": options},
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
        card={"day": today.strftime("%d/%m/%Y"),
              "question": question, "options": options[:3]},
    )


def enough(history: History, cat: str, now: datetime) -> bool:
    return history.count(cat, now.astimezone(TZ).date()) < LIMITS[cat]


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

    def get_day(day: date) -> list[dict]:
        nonlocal client
        name = day.isoformat()
        if name not in cache:
            if client is None:
                client = BSDClient(max_requests=int(os.getenv("FOOTBALL_BSD_REQUEST_BUDGET", "18")),
                                   max_retries=1)
            page = client.list_events(day, day, max_pages=7, ttl=0)
            if not page.complete:
                raise BSDAPIError("BSD: journée incomplète " + name + " (" +
                                  str(len(page.events)) + "/" + str(page.total_reported) + ")")
            cache[name] = page.events
            print("BSD_JOUR", name, "rencontres", len(page.events),
                  "requêtes", client.requests_made)
        return cache[name]

    def publish(item: Publication | None) -> None:
        if item is None or counter["sent"] >= max_send:
            return
        if not force and (state.seen(item.key) or not enough(state, item.category, now)):
            counter["skipped"] += 1
            return
        sender.send(item)
        counter["sent"] += 1
        if not dry_run:
            state.mark(item.key, item.category, now)
            state.save(now)

    # Ordre : rendez-vous fixes, contenu événementiel, flash RSS.
    try:
        if hour == 7 and (force or enough(state, "programme", now)):
            try:
                publish(programme(get_day(today), today, as_of=now))
            except (BSDAPIError, requests.RequestException, ValueError) as exc:
                counter["errors"] += 1
                print("ERREUR_PROGRAMME", type(exc).__name__, str(exc)[:160])

        if hour == 12 and (force or enough(state, "statistique", now)):
            try:
                reference = today - timedelta(days=1)
                recent = get_day(reference) + get_day(today)
                post = statistique(recent, reference)
                if post is None:
                    older = reference - timedelta(days=1)
                    post = statistique(get_day(older), reference)
                publish(post)
            except (BSDAPIError, requests.RequestException, ValueError) as exc:
                counter["errors"] += 1
                print("ERREUR_STAT", type(exc).__name__, str(exc)[:160])

        if hour == 15 and (force or enough(state, "sondage", now)):
            try:
                publish(sondage(get_day(today), state, now))
            except (BSDAPIError, requests.RequestException, ValueError) as exc:
                # Le sondage éditorial reste disponible si BSD est indisponible.
                counter["errors"] += 1
                print("ERREUR_BSD_SONDAGE", type(exc).__name__, str(exc)[:160])
                publish(sondage([], state, now))

        if 8 <= hour <= 23 and counter["sent"] < max_send:
            try:
                matches = get_day(today)
                if hour >= 20:
                    matches = matches + get_day(today + timedelta(days=1))
                upcoming = [e for e in candidates(matches)
                            if timedelta(minutes=65) <= kick(e) - now <= timedelta(minutes=170)
                            and final_score(e) is None
                            and not state.seen("avant_match:" + str(e["id"]))]
                if upcoming and (force or enough(state, "avant_match", now)):
                    if client is None:
                        client = BSDClient(max_requests=int(os.getenv("FOOTBALL_BSD_REQUEST_BUDGET", "18")),
                                           max_retries=1)
                    selected_for_form = next(
                        (item for item in upcoming[:10]
                         if has_two_team_logos(item, allow_remote=True)),
                        None,
                    )
                    forms = fetch_prematch_forms(client, selected_for_form) if selected_for_form else {}
                    publish(avant_match(matches, state, now, [], forms))
                if counter["sent"] < max_send and (force or enough(state, "resultat", now)):
                    publish(resultat(get_day(today), state, now))
            except (BSDAPIError, requests.RequestException, ValueError) as exc:
                counter["errors"] += 1
                print("ERREUR_BSD_MATCH", type(exc).__name__, str(exc)[:160])

        if 8 <= hour <= 23 and counter["sent"] < max_send and (force or enough(state, "flash", now)):
            try:
                publish(flash(fetch_rss(sender.session), state, now, sender.session))
            except (ET.ParseError, requests.RequestException, ValueError) as exc:
                counter["errors"] += 1
                print("ERREUR_RSS", type(exc).__name__, str(exc)[:160])
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
            return flash(fetch_rss(sender.session), empty_history, now, sender.session)

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
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    if args.check_comments:
        if args.dry_run or args.force or args.live_test or args.visual_test:
            parser.error("--check-comments doit etre utilise seul")
        sender = Sender(dry_run=False)
        linked = sender.verify_discussion()
        print("XPRONOS_COMMENTS_OK", linked)
    elif args.visual_test:
        if args.dry_run or args.force or args.live_test:
            parser.error("--visual-test doit etre utilise seul")
        run_visual_live_test(now)
    elif args.live_test:
        if args.dry_run or args.force:
            parser.error("--live-test ne peut pas etre combine avec --dry-run/--force")
        run_live_test(now)
    else:
        run(now, dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    main()
