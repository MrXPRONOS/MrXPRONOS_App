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
from bsd_api import BSDClient, BSDAPIError  # noqa: E402

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
    "real madrid", "barcelona", "barcelone", "manchester", "liverpool",
    "arsenal", "chelsea", "psg", "paris saint-germain", "bayern",
    "inter milan", "juventus", "ac milan", "napoli", "marseille",
    "atletico", "borussia dortmund", "al ahly", "wydad", "esperance",
    "senegal", "sénégal", "togo", "côte d'ivoire", "nigeria", "maroc",
)
CATEGORY_LABELS = {
    "flash": "📰 FLASH FOOT",
    "programme": "📅 MATCHS DU JOUR",
    "avant_match": "🔎 AVANT-MATCH",
    "resultat": "🏁 RÉSULTAT FINAL",
    "statistique": "📊 LE CHIFFRE DU JOUR",
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
    points = sum(12 for term in LEAGUE_TERMS if term in combined)
    points += sum(5 for term in TEAM_TERMS if term in combined)
    return points


def candidates(events: list[dict]) -> list[dict]:
    valid = [e for e in events if e.get("id") is not None
             and team(e, "home") and team(e, "away") and kick(e)]
    return sorted(valid, key=lambda e: (-importance(e), kick(e), str(e["id"])))


def time_label(dt: datetime) -> str:
    return dt.astimezone(TZ).strftime("%Hh%M")


def post_label(text: str) -> str:
    return text + "\n\n<i>⚽ Mr XPRONOS • L'actualité du football</i>"


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


class Sender:
    def __init__(self, *, dry_run: bool = False):
        self.dry_run = dry_run
        self.token = (os.getenv("FOOTBALL_NEWS_BOT_TOKEN") or
                      os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        self.chat = os.getenv(NEWS_CHAT_ENV, "").strip()
        if not dry_run and (not self.chat or not self.token):
            raise RuntimeError("Secrets manquants: FOOTBALL_NEWS_CHAT_ID et FOOTBALL_NEWS_BOT_TOKEN (ou TELEGRAM_BOT_TOKEN). Aucune publication vers le canal des pronostics.")
        self.session = requests.Session()

    def send(self, item: Publication) -> None:
        if self.dry_run:
            print("DRY_RUN", item.category, item.key, item.text[:500])
            if item.poll:
                print("DRY_RUN_POLL", item.poll)
            return
        method = "sendPoll" if item.poll else "sendMessage"
        data: dict[str, Any] = {"chat_id": self.chat}
        files = None
        card_dir = None
        if item.card and not item.poll:
            from football_cards import render_card
            card_dir = tempfile.TemporaryDirectory(prefix="xpronos-news-")
            try:
                graphic = render_card(item.category, item.card,
                                      Path(card_dir.name) / "publication.png")
                # Telegram limite la légende des photos à 1024 caractères :
                # un résumé court en texte brut évite toute balise HTML coupée.
                caption = plain(item.text.replace("<br>", " "), 840)
                data.update(caption=caption)
                method = "sendPhoto"
                files = {"photo": ("mrxpronos.png", graphic.open("rb"), "image/png")}
            except Exception:
                card_dir.cleanup()
                raise
        if item.poll:
            question, options = item.poll
            data.update(question=question[:300],
                        options=json.dumps(options, ensure_ascii=False),
                        is_anonymous="true", allows_multiple_answers="false")
        elif not item.card:
            data.update(text=item.text[:3900], parse_mode="HTML",
                        disable_web_page_preview="false")
        # Aucun retry automatique ambigu : Telegram peut avoir reçu le message.
        try:
            response = self.session.post(
                "https://api.telegram.org/bot" + self.token + "/" + method,
                data=data, files=files, timeout=(12, 55),
            )
            response.raise_for_status()
            payload = response.json()
        finally:
            if files:
                files["photo"][1].close()
            if card_dir:
                card_dir.cleanup()
        if payload.get("ok") is not True:
            raise RuntimeError("Telegram n'a pas confirmé l'envoi: " + str(payload.get("description", ""))[:180])
        identifier = payload.get("result", {}).get("message_id")
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
        description = plain(node.findtext("description"), 320)
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
                    "date": dt.astimezone(timezone.utc) if dt else None})
    return sorted(out, key=lambda r: r["date"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)


def fetch_rss(session: requests.Session) -> list[dict]:
    response = session.get(RSS_URL, timeout=(10, 25),
                           headers={"User-Agent": "MrXPRONOS-football-news/1.0"})
    response.raise_for_status()
    return parse_rss(response.content)


def flash(articles: list[dict], history: History, now: datetime) -> Publication | None:
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
            "<b>📰 FLASH FOOT • MR XPRONOS</b>\n\n"
            "<b>" + esc(a["title"]) + "</b>\n\n"
            + (esc(a["summary"]) + "\n\n" if a["summary"] else "")
            + "🗞️ Source : Foot Mercato\n"
            + '🔗 <a href="' + html.escape(a["url"], quote=True) + '">Lire l’article complet</a>'
        )
        return Publication("flash", key, post_label(msg))
    return None


def programme(events: list[dict], today: date, *, as_of: datetime | None = None) -> Publication | None:
    future = [e for e in candidates(events) if kick(e).astimezone(TZ).date() == today
              and (as_of is None or kick(e) > as_of)
              and final_score(e) is None
              and str(e.get("status", "")).lower() not in ("cancelled", "postponed", "finished", "live")]
    if not future:
        return None
    chosen = future[:7]
    lines = ["<b>📅 MATCHS DU JOUR — MR XPRONOS</b>",
             "🕒 Heures du Togo (GMT)\n"]
    for event in chosen:
        label = (" • " + esc(league(event))) if league(event) else ""
        lines.append("⚽ <b>" + esc(team(event, "home")) + " – " +
                     esc(team(event, "away")) + "</b>\n" +
                     "   🕒 " + time_label(kick(event)) + label)
    lines.append("\n💬 Quel match attendez-vous le plus ?")
    card = {"day": today.strftime("%d/%m/%Y"), "matches": [
        {"home": team(e, "home"), "away": team(e, "away"), "time": time_label(kick(e))}
        for e in chosen]}
    return Publication("programme", "programme:" + today.isoformat(),
                       post_label("\n\n".join(lines)), card=card)


def finished_recent(events: list[dict], now: datetime) -> list[dict]:
    return [e for e in candidates(events) if final_score(e) is not None
            and kick(e) < now - timedelta(minutes=85)
            and kick(e) >= now - timedelta(hours=9)]


def resultat(events: list[dict], history: History, now: datetime) -> Publication | None:
    for e in finished_recent(events, now):
        key = "resultat:" + str(e["id"])
        if history.seen(key):
            continue
        a, b = final_score(e)
        text = ("<b>🏁 RÉSULTAT FINAL • MR XPRONOS</b>\n\n"
                + "🏆 " + esc(league(e) or "Football") + "\n\n"
                + "⚽ <b>" + esc(team(e, "home")) + "  " + str(a) +
                " – " + str(b) + "  " + esc(team(e, "away")) + "</b>\n\n"
                + ("🤝 Match nul." if a == b else
                   "🏅 Victoire de " + esc(team(e, "home") if a > b else team(e, "away")) + ".")
                + "\n💬 Votre réaction ?")
        card = {"day": now.astimezone(TZ).strftime("%d/%m/%Y"),
                "league": league(e), "home": team(e, "home"),
                "away": team(e, "away"), "scores": (a, b)}
        return Publication("resultat", key, post_label(text), card=card)
    return None


def form(team_id: Any, name: str, events: list[dict], before: datetime) -> str:
    recent = []
    for e in events:
        when = kick(e)
        result = final_score(e)
        if not when or not result or when >= before:
            continue
        side = None
        for s in ("home", "away"):
            current = e.get(s + "_team")
            current_id = (current.get("id") if isinstance(current, dict) else
                          e.get(s + "_team_id"))
            if team_id is not None and str(current_id) == str(team_id):
                side = s
                break
            if team_id is None and team(e, s).casefold() == name.casefold():
                side = s
                break
        if side:
            x, y = result if side == "home" else result[::-1]
            recent.append((when, "V" if x > y else "N" if x == y else "D"))
    recent.sort(reverse=True)
    vals = [x[1] for x in recent[:5]]
    if not vals:
        return "forme récente non disponible"
    return str(len(vals)) + " match(s) retrouvés : " + ", ".join(vals)


def avant_match(events: list[dict], history: History, now: datetime,
                history_events: list[dict]) -> Publication | None:
    selected = [e for e in candidates(events)
                if timedelta(minutes=65) <= kick(e) - now <= timedelta(minutes=170)
                and final_score(e) is None and not history.seen("avant_match:" + str(e["id"]))]
    if not selected:
        return None
    e = selected[0]
    def team_id(side: str):
        obj = e.get(side + "_team")
        return obj.get("id") if isinstance(obj, dict) else e.get(side + "_team_id")
    h, a = team(e, "home"), team(e, "away")
    lines = [
        "<b>🔎 AVANT-MATCH • MR XPRONOS</b>\n",
        "🏆 " + esc(league(e) or "Football"),
        "⚽ <b>" + esc(h) + " – " + esc(a) + "</b>",
        "🕒 Coup d'envoi : <b>" + time_label(kick(e)) + "</b> (Togo)",
        "\n📈 <b>Forme récente connue (7 derniers jours)</b>",
        "• " + esc(h) + " : " + esc(form(team_id("home"), h, history_events, kick(e))),
        "• " + esc(a) + " : " + esc(form(team_id("away"), a, history_events, kick(e))),
        "\n💬 Quel scénario imaginez-vous pour cette rencontre ?",
    ]
    return Publication("avant_match", "avant_match:" + str(e["id"]), post_label("\n".join(lines)))


def statistique(events: list[dict], yesterday: date) -> Publication | None:
    finished = [e for e in events if final_score(e) is not None and
                kick(e) and kick(e).astimezone(TZ).date() == yesterday]
    if not finished:
        return None
    e = sorted(finished, key=lambda x: (-(sum(final_score(x))), -importance(x), str(x.get("id"))))[0]
    h, a = final_score(e)
    message = (
        "<b>📊 LE CHIFFRE DU JOUR • MR XPRONOS</b>\n\n"
        + "🔢 <b>" + str(h + a) + " buts</b> dans cette rencontre d'hier :\n"
        + "⚽ " + esc(team(e, "home")) + " <b>" + str(h) + " – " + str(a) +
        "</b> " + esc(team(e, "away")) + "\n"
        + "🏆 " + esc(league(e) or "Football") + "\n\n"
        + "💬 Quel autre match d'hier vous a marqué ?"
    )
    card = {"day": yesterday.strftime("%d/%m/%Y"), "league": league(e),
            "home": team(e, "home"), "away": team(e, "away"), "scores": (h, a)}
    return Publication("statistique", "statistique:" + yesterday.isoformat(),
                       post_label(message), card=card)


def sondage(events: list[dict], history: History, now: datetime) -> Publication:
    today = now.astimezone(TZ).date()
    future = [e for e in candidates(events) if kick(e) > now + timedelta(minutes=20)
              and kick(e) < now + timedelta(hours=34) and final_score(e) is None]
    if future:
        e = future[0]
        h, a = team(e, "home"), team(e, "away")
        question = ("⚽ " + h + " - " + a + " : votre favori ?")[:300]
        options = ["Victoire " + h, "Match nul", "Victoire " + a]
        if max(map(len, options)) <= 100:
            return Publication("sondage", "sondage:" + today.isoformat(),
                               "🗳️ Sondage Mr XPRONOS", (question, options))
    topics = [
        ("Quel championnat aimez-vous suivre ?", ["Premier League", "Liga", "Ligue 1", "Autre"]),
        ("Vous préférez quel type de match ?", ["Festival de buts", "Duel tactique", "Derby intense"]),
        ("Qu'aimez-vous lire sur Mr XPRONOS ?", ["Actualités", "Résultats", "Statistiques", "Analyses"]),
        ("Quel contenu souhaitez-vous davantage ?", ["Mercato", "Football africain", "Quiz", "Débats"]),
    ]
    question, options = topics[today.toordinal() % len(topics)]
    return Publication("sondage", "sondage:" + today.isoformat(), "🗳️ Sondage Mr XPRONOS",
                       (question, options))


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
                publish(statistique(get_day(today - timedelta(days=1)),
                                    today - timedelta(days=1)))
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
                    past: list[dict] = []
                    try:
                        # Fenêtre de forme récente : ne jamais inventer les résultats manquants.
                        if client is None:
                            client = BSDClient(max_requests=18)
                        page = client.list_events(today - timedelta(days=7),
                                                  today - timedelta(days=1),
                                                  max_pages=5, ttl=0)
                        past = page.events
                    except (BSDAPIError, requests.RequestException, ValueError) as exc:
                        print("INFO_FORME_INDISPONIBLE", type(exc).__name__)
                    publish(avant_match(matches, state, now, past))
                if counter["sent"] < max_send and (force or enough(state, "resultat", now)):
                    publish(resultat(get_day(today), state, now))
            except (BSDAPIError, requests.RequestException, ValueError) as exc:
                counter["errors"] += 1
                print("ERREUR_BSD_MATCH", type(exc).__name__, str(exc)[:160])

        if 8 <= hour <= 23 and counter["sent"] < max_send and (force or enough(state, "flash", now)):
            try:
                publish(flash(fetch_rss(sender.session), state, now))
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
            if not future:
                return None
            # Emulate a 2h-before-kickoff publication (the fixture time
            # displayed is genuine). It is clearly identified as a TEST.
            match = future[0]
            virtual_now = kick(match) - timedelta(hours=2)
            return avant_match([match], empty_history, virtual_now, [])

        def actual_result() -> Publication | None:
            yesterday = day_events(today - timedelta(days=1))
            today_events = day_events(today)
            finished = [e for e in candidates(today_events + yesterday)
                        if final_score(e) is not None and kick(e) < now]
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
            return statistique(day_events(yesterday), yesterday)

        def actual_flash() -> Publication | None:
            return flash(fetch_rss(sender.session), empty_history, now)

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


def main() -> None:
    parser = argparse.ArgumentParser(description="6 publications automatiques Mr XPRONOS")
    parser.add_argument("--dry-run", action="store_true", help="Simulation sans Telegram, ni historique")
    parser.add_argument("--live-test", action="store_true",
                        help="Envoie les six rubriques TEST au vrai canal, sans historique")
    parser.add_argument("--force", action="store_true", help="Ignorer les limites et l'historique (test manuel)")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    if args.live_test:
        if args.dry_run or args.force:
            parser.error("--live-test ne peut pas etre combine avec --dry-run/--force")
        run_live_test(now)
    else:
        run(now, dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    main()
