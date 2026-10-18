"""Publication #10 — Réglementation crypto mondiale.

Collect free editorial + official regulatory RSS; select *review candidates*.
No automated legal conclusion, no automated real Telegram send.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests
import feedparser
from crypto.news_sources_v2 import EDITORIAL_FEEDS

UTC = timezone.utc
DEST = Path("crypto/generated/test")
STATE = Path("crypto/regulation_10_state.json")
MAX_AGE_H = 96

# Official feeds validated at the publisher website. Public, key-free.
REGULATOR_FEEDS = {
    "SEC": ("https://www.sec.gov/news/pressreleases.rss", "sec.gov"),
    "ESMA": ("https://www.esma.europa.eu/rss.xml", "esma.europa.eu"),
    "Commission européenne": (
        "https://ec.europa.eu/commission/presscorner/api/rss?language=en", "ec.europa.eu"),
}
FEEDS = {**EDITORIAL_FEEDS, **REGULATOR_FEEDS}
OFFICIAL = frozenset(REGULATOR_FEEDS)
CRYPTO = re.compile(
    r"\b(crypto(?:currency|currencies|asset|assets)?|bitcoin|ethereum|"
    r"stablecoin|stablecoins|virtual asset|virtual assets|digital asset|digital assets|"
    r"tokeni[sz](?:ation|ed)|mica|v[i]?asp|usdt|usdc|defi|web3)\b", re.I)
REGULATION = re.compile(
    r"\b(regulat(?:or|ors|ion|ions|ory|e|ed|es)|legislat(?:ion|ive)|"
    r"law|laws|bill|bills|ban|bans|banned|restrict(?:ion|ions|ed)?|"
    r"licen[sc](?:e|es|ing|ed)|authori[sz](?:ation|ed|e|es)|"
    r"compliance|sanction|fine|fined|tax|taxation|anti.money.launder|aml|"
    r"kyc|securit(?:ies|y) law|rules?|proposal|propos(?:e|es|ed)|"
    r"supervis(?:ion|or|ory)|enforcement|approved|adopted|"
    r"guidance|framework|court|lawsuit|consultation|legality)\b", re.I)
EXCLUDE = ("sponsored", "advertorial", "price prediction", "price analysis",
           "technical analysis", "opinion:", "op-ed", "weekly roundup", "daily roundup",
           "press release distribution", "what is crypto", "how to buy", "could bitcoin",
           "will bitcoin", "rumor", "rumour", "unconfirmed", "partner content")
HEADERS = {"User-Agent": "MrXPRONOS-CryptoNews/1.0 (public RSS, linked attribution)",
           "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.2"}

# These labels classify *headline language*, not the binding legal status.
STAGE_PATTERNS = (
    ("CONSULTATION", re.compile(r"\b(consultation|seeks? comments?|public feedback|comment period)\b", re.I)),
    ("PROPOSITION", re.compile(r"\b(proposal|proposed|proposes|draft|bill|seeks? to)\b", re.I)),
    ("ADOPTION ANNONCÉE", re.compile(r"\b(adopts?|adopted|passed|passes|approves?|approved|signed into law)\b", re.I)),
    ("ENTRÉE EN VIGUEUR ANNONCÉE", re.compile(r"\b(enters? into force|takes? effect|effective from|comes? into effect)\b", re.I)),
    ("SANCTION / DÉCISION", re.compile(r"\b(fines?|fined|penalt(?:y|ies)|sanctions?|enforcement action|court rules?|settles?|settlement)\b", re.I)),
)
REGIONS = {
    "SEC": "ÉTATS-UNIS",
    "ESMA": "UNION EUROPÉENNE",
    "Commission européenne": "UNION EUROPÉENNE",
}
MEDIA_REGIONS = (
    ("UNION EUROPÉENNE", r"\b(european union|eu|europe|mica)\b"),
    ("ÉTATS-UNIS", r"\b(united states|u\.s\.|usa|sec|cftc)\b"),
    ("ROYAUME-UNI", r"\b(united kingdom|britain|uk|fca)\b"),
    ("HONG KONG", r"\b(hong kong|hkma|sfc)\b"),
    ("NIGERIA", r"\b(nigeria|nigerian)\b"),
    ("GHANA", r"\b(ghana|ghanaian)\b"),
    ("TOGO", r"\b(togo|togolese|togolais)\b"),
)
OFFICIAL_ALLOWED_HOSTS = {
    "SEC": {"sec.gov"},
    "ESMA": {"esma.europa.eu"},
    "Commission européenne": {"ec.europa.eu", "commission.europa.eu"},
}


def clean(value: object, limit: int = 200) -> str:
    stripped = re.sub(r"<[^>]*>", " ", html.unescape(str(value or "")))
    return re.sub(r"\s+", " ", stripped).strip()[:limit]


def canonical_url(link: str, publisher: str) -> str:
    u = urlsplit(str(link or "").strip())
    host = (u.hostname or "").lower().removeprefix("www.")
    allowed = OFFICIAL_ALLOWED_HOSTS.get(publisher, {FEEDS[publisher][1]})
    if (u.scheme != "https" or host not in allowed or u.username or u.password
            or u.port not in (None, 443) or len(u.path.strip("/")) < 5):
        raise ValueError("Article link is not on approved official/editorial host")
    return urlunsplit(("https", u.hostname.lower(), u.path.rstrip("/"), "", ""))


def iso_time(value, now: datetime) -> str:
    if not value:
        raise ValueError("Article date missing")
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            dt = parsedate_to_datetime(value)
    else:
        dt = datetime(*value[:6], tzinfo=UTC)
    if dt.tzinfo is None:
        raise ValueError("Article timezone missing")
    dt = dt.astimezone(UTC)
    lag = (now - dt).total_seconds()
    if not -300 <= lag <= MAX_AGE_H * 3600:
        raise ValueError("Article older than review window / from future")
    return dt.isoformat()


def stage(title: str) -> str:
    for label, pattern in STAGE_PATTERNS:
        if pattern.search(title):
            return label
    return "STATUT JURIDIQUE À VÉRIFIER"


def region(title: str, publisher: str) -> str:
    if publisher in REGIONS:
        return REGIONS[publisher]
    hits = [label for label, pattern in MEDIA_REGIONS if re.search(pattern, title, re.I)]
    return hits[0] if len(hits) == 1 else "ZONE À VÉRIFIER"


def parse_entry(entry, source: str, now: datetime) -> dict:
    title = clean(entry.get("title"), 190)
    if (len(title) < 27 or any(x in title.lower() for x in EXCLUDE)
            or not CRYPTO.search(title) or not REGULATION.search(title)):
        raise ValueError("Title insufficiently relevant for crypto regulation")
    link = canonical_url(entry.get("link"), source)
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    if not published:
        published = entry.get("published") or entry.get("updated")
    return {
        "source": source, "official": source in OFFICIAL,
        "title": title, "url": link,
        "published_at": iso_time(published, now),
        "region": region(title, source),
        "stage": stage(title),
    }


def fetch_feed(source, url, now, getter=requests.get):
    try:
        r = getter(url, headers=HEADERS, timeout=(8, 18))
        r.raise_for_status()
        if not 0 < len(r.content) < 2_000_000:
            raise ValueError("RSS invalid size")
        parsed = feedparser.parse(r.content)
        if parsed.bozo or not parsed.entries:
            raise ValueError("Malformed or empty RSS")
        rows = []
        for entry in parsed.entries[:75]:
            try:
                rows.append(parse_entry(entry, source, now))
            except (ValueError, TypeError, OverflowError):
                pass
        print("REG10_RSS", source, "entries", len(parsed.entries), "candidates", len(rows))
        return rows
    except (requests.RequestException, ValueError, TypeError) as exc:
        print("REG10_SOURCE_UNAVAILABLE", source, type(exc).__name__)
        return []


def fingerprint(item: dict) -> str:
    return hashlib.sha256(item["url"].encode("utf-8")).hexdigest()[:24]


def load_state(path=STATE) -> dict:
    if not path.exists():
        return {"reviewed_urls": []}
    obj = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(obj, dict) or not isinstance(obj.get("reviewed_urls"), list)
            or any(not isinstance(x, str) for x in obj["reviewed_urls"])):
        raise ValueError("Invalid review registry; stop")
    return obj


def select_candidate(rows: list[dict], state: dict, now: datetime) -> dict | None:
    checked = set(state["reviewed_urls"])
    usable = [a for a in rows if fingerprint(a) not in checked]
    usable.sort(key=lambda a: (a["official"], a["published_at"]), reverse=True)
    if not usable:
        return None
    article = usable[0]
    out = {
        "publication": 10, "status": "pending_human_review",
        "is_demo": False, "legal_status_confirmed": False,
        "collected_at": now.isoformat(),
        "primary": article, "fingerprint": fingerprint(article),
        "approval_required": True,
        "review_items": [
            "Vérifier le texte primaire et la compétence de l'autorité",
            "Distinguer proposition, adoption et entrée en vigueur",
            "Vérifier juridiction, date d'application et éventuelles exceptions",
            "Faire relire les implications avant toute diffusion",
        ],
    }
    validate_candidate(out, now)
    return out


def validate_candidate(d: dict, now: datetime | None = None):
    now = now or datetime.now(UTC)
    if (d.get("publication") != 10 or d.get("status") != "pending_human_review"
            or d.get("approval_required") is not True
            or d.get("is_demo") is not False or d.get("legal_status_confirmed") is not False):
        raise ValueError("Human review flag required; no auto publication")
    dt = datetime.fromisoformat(d["collected_at"])
    if dt.tzinfo is None or not -300 <= (now - dt).total_seconds() <= 60 * 60:
        raise ValueError("Candidate expired")
    a = d.get("primary")
    if not isinstance(a, dict) or a.get("source") not in FEEDS:
        raise ValueError("Invalid feed source")
    if a.get("official") is not (a["source"] in OFFICIAL):
        raise ValueError("Source identity tampered")
    if (a.get("url") != canonical_url(a["url"], a["source"])
            or not isinstance(a.get("title"), str)
            or not CRYPTO.search(a["title"]) or not REGULATION.search(a["title"])):
        raise ValueError("Unqualified or invalid source record")
    iso_time(a.get("published_at"), now)
    if (a.get("stage") != stage(a["title"])
            or a.get("region") != region(a["title"], a["source"])
            or d.get("fingerprint") != fingerprint(a)):
        raise ValueError("Altered headline classification")
    if not isinstance(d.get("review_items"), list) or len(d["review_items"]) != 4:
        raise ValueError("Review checklist incomplete")


def demo_report():
    now = datetime.now(UTC)
    item = {
        "source": "ESMA", "official": True,
        "title": "ESMA proposes new consultation rules for crypto asset service providers",
        "url": "https://www.esma.europa.eu/press-news/esma-news/simulation-crypto-regulation-demo",
        "published_at": (now-timedelta(hours=3)).isoformat(),
        "region": "UNION EUROPÉENNE", "stage": "CONSULTATION",
    }
    return {
        "publication": 10, "status": "demo", "is_demo": True,
        "legal_status_confirmed": False, "collected_at": now.isoformat(),
        "primary": item, "fingerprint": fingerprint(item),
        "approval_required": True,
        "review_items": [
            "Vérifier le texte primaire et la compétence de l'autorité",
            "Distinguer proposition, adoption et entrée en vigueur",
            "Vérifier juridiction, date d'application et éventuelles exceptions",
            "Faire relire les implications avant toute diffusion",
        ],
    }


def export(demo=False, state_file=STATE):
    DEST.mkdir(parents=True, exist_ok=True)
    if demo:
        p = DEST / "regulation_v2_demo.json"
        p.write_text(json.dumps(demo_report(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("REG10_DEMO", p)
        return True
    p = DEST / "regulation_v2_candidate.json"
    p.unlink(missing_ok=True)
    now = datetime.now(UTC)
    state = load_state(state_file)
    rows = []
    for source, (url, _) in FEEDS.items():
        rows.extend(fetch_feed(source, url, now))
    selected = select_candidate(rows, state, now)
    if not selected:
        print("REG10_NO_REVIEW_CANDIDATE — no claims, no Telegram message")
        return False
    p.write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("REG10_REVIEW_REQUIRED", selected["primary"]["source"],
          selected["primary"]["region"], selected["primary"]["stage"])
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    export(demo=args.demo)
