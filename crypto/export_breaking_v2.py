"""Mr XPRONOS #08 — actualités urgentes BTC/ETH, RSS gratuit et contrôle croisé.

Une seule source ne suffit jamais à qualifier un événement de "breaking".
Une réponse vide est normale; une simulation n'est jamais publiable.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import feedparser
import requests

UTC = timezone.utc
DEST = Path("crypto/generated/test")
FEEDS = {
    "CoinDesk": ("https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml", "coindesk.com"),
    "Cointelegraph": ("https://cointelegraph.com/rss", "cointelegraph.com"),
    "The Block": ("https://www.theblock.co/rss.xml", "theblock.co"),
}
COINS = {
    "bitcoin": {"bitcoin", "btc"},
    "ethereum": {"ethereum", "ether", "eth"},
}
STOP = set(("a an and are as at be by for from has have in into is it its of on or the "
            "their this to was were with will after before crypto cryptocurrency cryptocurrencies "
            "digital asset assets blockchain bitcoin btc ethereum eth ether price prices market markets "
            "trader traders token tokens says said news report reports latest today amid over "
            "under more less new up down why how what could may might see sees sees").split())
SIGNALS = {
    "etf", "sec", "approve", "approval", "approved", "reject", "rejection",
    "hack", "hacked", "exploit", "breach", "security", "outage", "upgrade",
    "launch", "launched", "regulation", "regulator", "lawsuit", "court",
    "liquidation", "liquidations", "treasury", "acquisition", "acquire",
    "buy", "buys", "bought", "sell", "sells", "sold", "record", "crash",
    "surge", "fall", "falls", "drop", "drops", "halt", "halts", "shutdown",
    "fork", "staking", "foundation", "bill", "ruling", "reserve",
    "blackrock", "fidelity", "strategy", "fund", "funds", "network", "fed",
}
EXCLUDE = (
    "sponsored", "advertorial", "press release", "partner content", "paid content",
    "opinion:", "op-ed", "how to", "guide to", "price prediction", "will bitcoin",
    "will ethereum", "could bitcoin", "could ethereum", "price analysis",
    "technical analysis", "daily roundup", "weekly roundup", "weekly recap",
    "what is bitcoin", "what is ethereum",
)
HEADERS = {"User-Agent": "MrXPRONOS-ActuCrypto/1.0 (RSS public; source attribution)",
           "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.3"}
MAX_AGE_H = 12


def clean_text(value: str, limit: int = 220) -> str:
    value = re.sub(r"<[^>]*>", " ", html.unescape(str(value or "")))
    return re.sub(r"\s+", " ", value).strip()[:limit]


def canonical_url(url: str, host: str) -> str:
    try:
        u = urlsplit(str(url or "").strip())
        hostname = (u.hostname or "").lower()
        if u.scheme != "https" or not (hostname == host or hostname == "www." + host):
            raise ValueError("Domaine source non autorisé")
        if u.username or u.password or u.port not in (None, 443):
            raise ValueError("URL source suspecte")
        path = u.path if u.path.startswith("/") else "/" + u.path
        if path in ("", "/"):
            raise ValueError("URL article absente")
        return urlunsplit(("https", hostname, path.rstrip("/"), "", ""))
    except (ValueError, TypeError) as exc:
        raise ValueError("Lien article incorrect") from exc


def iso_time(raw, now: datetime) -> str:
    if not raw:
        raise ValueError("Article sans date fiable")
    if isinstance(raw, str):
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    else:
        dt = datetime(*raw[:6], tzinfo=UTC)
    if dt.tzinfo is None:
        raise ValueError("Fuseau manquant")
    dt = dt.astimezone(UTC)
    age = (now - dt).total_seconds()
    if not -300 <= age <= MAX_AGE_H * 3600:
        raise ValueError("Article périmé ou futur")
    return dt.isoformat()


def topic(title: str) -> str | None:
    words = set(re.findall(r"[a-z]+", title.casefold()))
    matches = [name for name, variants in COINS.items() if words & variants]
    return matches[0] if len(matches) == 1 else None


def terms(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", title.casefold())
            if len(w) > 2 and w not in STOP}


def newsworthy(title: str) -> bool:
    lower = title.casefold()
    if any(p in lower for p in EXCLUDE):
        return False
    return bool(terms(title) & SIGNALS)


def parse_entry(entry, source: str, now: datetime) -> dict:
    title = clean_text(entry.get("title"), 180)
    if len(title) < 24:
        raise ValueError("Titre trop court")
    if not topic(title):
        raise ValueError("Aucun sujet BTC/ETH unique dans le titre")
    if not newsworthy(title):
        raise ValueError("Pas de signal d'importance ou article exclu")
    host = FEEDS[source][1]
    url = canonical_url(entry.get("link"), host)
    time_data = entry.get("published_parsed") or entry.get("updated_parsed")
    if time_data:
        published = iso_time(time_data, now)
    else:
        published = iso_time(entry.get("published") or entry.get("updated"), now)
    return {"source": source, "title": title, "url": url,
            "published_at": published, "topic": topic(title)}


def fetch_feed(source: str, url: str, now: datetime, getter=requests.get) -> list[dict]:
    try:
        r = getter(url, timeout=(8, 18), headers=HEADERS, allow_redirects=True)
        r.raise_for_status()
        if len(r.content) > 2_000_000 or not r.content:
            raise ValueError("Taille du flux anormale")
        feed = feedparser.parse(r.content)
        if feed.bozo or not feed.entries:
            raise ValueError("Flux invalide ou vide")
        articles = []
        rejection_reasons = {}
        for entry in feed.entries[:40]:
            try:
                articles.append(parse_entry(entry, source, now))
            except (ValueError, TypeError, OverflowError) as exc:
                reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
        print("RSS_SCAN", source, "feed_entries", len(feed.entries),
              "qualified_recent", len(articles),
              "rejection_reasons", json.dumps(rejection_reasons, ensure_ascii=False, sort_keys=True))
        return articles
    except (requests.RequestException, ValueError, TypeError) as exc:
        print("RSS_UNAVAILABLE", source, type(exc).__name__)
        return []


def corroborates(a: dict, b: dict) -> bool:
    if a["source"] == b["source"] or a["topic"] != b["topic"]:
        return False
    ta, tb = terms(a["title"]), terms(b["title"])
    shared = ta & tb
    # Au moins deux détails communs dont un marqueur d'événement, hors nom de la crypto.
    if len(shared) < 2 or not (shared & SIGNALS):
        return False
    if len(shared) / max(1, len(ta | tb)) < 0.22:
        return False
    return abs((datetime.fromisoformat(a["published_at"]) -
                datetime.fromisoformat(b["published_at"])).total_seconds()) <= 12 * 3600


def fingerprint(article: dict) -> str:
    return hashlib.sha256(article["url"].encode("utf-8")).hexdigest()[:20]


def already_published(items: list[dict], state: dict) -> bool:
    ids = set(state.get("sent_urls", []))
    return any(fingerprint(x) in ids for x in items)


def candidate_pairs(rows: list[dict], state: dict) -> list[tuple]:
    pairs = []
    rows = sorted(rows, key=lambda x: x["published_at"], reverse=True)
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if corroborates(a, b) and not already_published([a, b], state):
                published_at = max(a["published_at"], b["published_at"])
                score = len(terms(a["title"]) & terms(b["title"]))
                pairs.append((published_at, score, a, b))
    return sorted(pairs, key=lambda x: (x[0], x[1]), reverse=True)


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"sent_urls": []}
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or not isinstance(obj.get("sent_urls"), list):
        raise ValueError("État anti-doublon invalide : arrêt de sécurité")
    return obj


def build_report(pair: tuple, now: datetime) -> dict:
    a, b = pair
    if not corroborates(a, b):
        raise ValueError("Deux confirmations indépendantes requises")
    items = sorted([a, b], key=lambda x: x["published_at"])
    return {"status": "real_data", "is_demo": False, "publication": 8,
            "topic": a["topic"], "collected_at": now.isoformat(),
            "main": items[0], "confirmation": items[1],
            "fingerprints": [fingerprint(x) for x in items]}


def validate_real(data: dict, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    if not isinstance(data, dict) or data.get("publication") != 8:
        raise ValueError("Rubrique incorrecte")
    if data.get("status") != "real_data" or data.get("is_demo") is not False:
        raise ValueError("Simulation interdite")
    dt = datetime.fromisoformat(data["collected_at"])
    if dt.tzinfo is None or not -300 <= (now - dt).total_seconds() <= 45 * 60:
        raise ValueError("Collecte trop ancienne")
    items = []
    for label in ("main", "confirmation"):
        a = data.get(label)
        if not isinstance(a, dict) or a.get("source") not in FEEDS:
            raise ValueError("Source non reconnue")
        expected = canonical_url(a.get("url"), FEEDS[a["source"]][1])
        if a["url"] != expected or not a.get("title") or not newsworthy(a["title"]):
            raise ValueError("Article altéré ou non qualifié")
        if topic(a["title"]) != a.get("topic"):
            raise ValueError("Sujet non conforme")
        iso_time(a["published_at"], now)
        items.append(a)
    if data.get("topic") != items[0]["topic"] or not corroborates(*items):
        raise ValueError("Événement non corroboré")
    if data.get("fingerprints") != [fingerprint(x) for x in items]:
        raise ValueError("Empreintes incohérentes")


def demo_report() -> dict:
    now = datetime(2026, 10, 18, 9, tzinfo=UTC)
    a = {"source": "CoinDesk", "title": "Bitcoin ETF receives approval after regulator review",
         "url": "https://www.coindesk.com/demo/btc-example-a",
         "published_at": (now - timedelta(hours=3)).isoformat(), "topic": "bitcoin"}
    b = {"source": "The Block", "title": "Bitcoin ETF approval announced following regulator review",
         "url": "https://www.theblock.co/demo/btc-example-b",
         "published_at": (now - timedelta(hours=2)).isoformat(), "topic": "bitcoin"}
    d = build_report((a, b), now)
    d.update(status="demo", is_demo=True)
    return d


def export(demo: bool = False, state_file: Path = Path("crypto/breaking_08_state.json")) -> bool:
    DEST.mkdir(parents=True, exist_ok=True)
    if demo:
        target = DEST / "breaking_v2_demo.json"
        target.write_text(json.dumps(demo_report(), ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
        print("BREAKING_08_DEMO", target)
        return True
    real = DEST / "breaking_v2_data.json"
    real.unlink(missing_ok=True)
    now = datetime.now(UTC)
    state = load_state(state_file)
    rows = []
    for name, (url, _) in FEEDS.items():
        rows.extend(fetch_feed(name, url, now))
    print("BREAKING_08_FEEDS", len(rows), "qualified articles")
    pairs = candidate_pairs(rows, state)
    if not pairs:
        print("BREAKING_08_NO_NEWS — nothing verified by two sources; no publication")
        return False
    d = build_report((pairs[0][2], pairs[0][3]), now)
    validate_real(d, now)
    real.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print("BREAKING_08_REAL", d["topic"], d["main"]["source"],
          d["confirmation"]["source"], real)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--state-file", type=Path, default=Path("crypto/breaking_08_state.json"))
    args = parser.parse_args()
    export(demo=args.demo, state_file=args.state_file)
