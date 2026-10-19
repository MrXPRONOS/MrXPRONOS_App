"""Publication #09 — exchange news from free, attributed RSS feeds.

No LLM, fake news, paid API or production schedule. Editorial coverage is
attributed to its publisher; high-impact incidents require two independent
publishers with matching event details.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import feedparser
import requests
from crypto.news_sources_v2 import EDITORIAL_FEEDS, OFFICIAL_STATUS_APIS
from crypto.editorial_fr import exchange_synopsis, validate_synopsis

UTC = timezone.utc
OUTPUT = Path("crypto/generated/test")
STATE = Path("crypto/exchanges_09_state.json")
MAX_AGE_HOURS = 48
FEEDS = EDITORIAL_FEEDS
EXCHANGES = ("BINANCE", "COINBASE", "OKX", "KRAKEN", "BYBIT", "BITGET", "KUCOIN", "GEMINI")
CATEGORIES = {
    "SÉCURITÉ": ("hack", "hacked", "breach", "exploit", "stolen", "theft", "compromise", "attack", "phishing"),
    "ACCÈS & SERVICES": ("withdrawal", "withdrawals", "deposit", "deposits", "suspend", "suspended", "resume", "resumes", "halt", "halts", "maintenance", "outage", "freeze", "frozen", "restrictions", "restrict", "block", "blocked"),
    "FRAIS & TRADING": ("trading fee", "fees", "fee ", "fee-", "maker", "taker", "delist", "delisting", "listing", "listings", "list ", "lists ", "liquidity"),
    "RÉGLEMENTATION": ("regulator", "regulatory", "license", "licence", "sec ", "lawsuit", "settlement", "court", "fine", "penalty", "investigation"),
    "INNOVATION": ("launch", "launched", "introduce", "introduces", "integrate", "integration", "partner", "partnership", "acquire", "acquisition", "wallet", "payment", "payments", "stablecoin"),
}
SEVERE_WORDS = ("hack", "hacked", "breach", "exploit", "stolen", "theft", "compromised",
                "attack", "phishing", "insolvency", "bankrupt", "bankruptcy", "outage",
                "withdrawal halt", "withdrawals halted", "funds frozen")
EXCLUDED = ("sponsored", "advertorial", "price prediction", "technical analysis",
            "weekly recap", "daily roundup", "newsletter", "how to buy",
            "opinion:", "op-ed", "rumor", "rumour", "unconfirmed", "might ",
            "could ", "should you buy", "press release", "pr newswire")
STOP = set(("the a an and or of to for on in with as its is has have after before from says say "
            "will at by are was were that this crypto cryptocurrency digital asset assets "
            "exchange exchanges trading bitcoin btc ethereum eth new more into over about "
            "report reports reported latest news markets market firm company major amid "
            "platform token tokens binance coinbase okx kraken bybit bitget kucoin gemini").split())
HEADERS = {"User-Agent": "MrXPRONOS-ActuCrypto/1.0 (public news feed attribution)",
           "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.2"}


def clean(v, limit=190):
    txt = re.sub(r"<[^>]+>", " ", html.unescape(str(v or "")))
    return re.sub(r"\s+", " ", txt).strip()[:limit]


def canonical_url(url: str, domain: str) -> str:
    u = urlsplit(str(url or "").strip())
    host = (u.hostname or "").lower()
    if (u.scheme != "https" or not (host == domain or host == "www." + domain)
            or u.username or u.password or u.port not in (None, 443)
            or len(u.path.strip("/")) < 5):
        raise ValueError("Article URL outside trusted publisher")
    return urlunsplit(("https", host, u.path.rstrip("/"), "", ""))


def parse_time(value, now: datetime) -> str:
    if value is None or value == "":
        raise ValueError("Missing publication date")
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            dt = parsedate_to_datetime(value)
    else:
        dt = datetime(*value[:6], tzinfo=UTC)
    if dt.tzinfo is None:
        raise ValueError("Publication date must have timezone")
    dt = dt.astimezone(UTC)
    diff = (now - dt).total_seconds()
    if not -300 <= diff <= MAX_AGE_HOURS * 3600:
        raise ValueError("Stale or future article")
    return dt.isoformat()


def exchange_of(title: str) -> str | None:
    found = [s for s in EXCHANGES if re.search(r"\b" + s + r"\b", title.upper())]
    return found[0] if len(found) == 1 else None


# News centered on laws, regulators, issuers or policy belongs in #10,
# even if an exchange name and a generic word like "listing" appear later.
POLICY_ROUTE = re.compile(
    r"\b(sec|cftc|fca|esma|regulator|regulation|regulatory|"
    r"legislation|lawmakers?|framework|securities law|tokenized stock|"
    r"issuer pushback|court ruling|lawsuit|compliance rules?)\b", re.I
)


def category_of(title: str) -> str | None:
    lower = title.lower()
    if any(s in lower for s in EXCLUDED) or POLICY_ROUTE.search(title):
        return None
    for label, cues in CATEGORIES.items():
        if label == "RÉGLEMENTATION":
            continue  # Publication 10 handles the legal/regulatory domain.
        if any(x in lower for x in cues):
            return label
    return None


def severe(title: str) -> bool:
    return any(t in title.lower() for t in SEVERE_WORDS)


def terms(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", title.casefold())
            if len(w) > 2 and w not in STOP}


def parse_entry(entry, source: str, now: datetime) -> dict:
    title = clean(entry.get("title"))
    # Editorial category #09 requires the PLATFORM to lead the headline.
    # A mention of OKX near the end of a SEC article is NOT an OKX news item.
    first_part = re.split(r"[:—–]", title, maxsplit=1)[0][:85]
    if (len(title) < 23 or exchange_of(title) is None or category_of(title) is None
            or exchange_of(first_part) != exchange_of(title)
            or not re.match(r"^\s*(?:"
                + "|".join(EXCHANGES) + r")\b", title, re.I)):
        raise ValueError("Exchange is not the principal subject")
    uri = canonical_url(entry.get("link"), FEEDS[source][1])
    stamp = entry.get("published_parsed") or entry.get("updated_parsed")
    if stamp is None:
        stamp = entry.get("published") or entry.get("updated")
    return {"source": source, "title": title, "url": uri,
            "published_at": parse_time(stamp, now),
            "exchange": exchange_of(title), "category": category_of(title),
            "severe": severe(title)}


def fetch_feed(name, url, now, getter=requests.get):
    try:
        response = getter(url, headers=HEADERS, timeout=(8, 18))
        response.raise_for_status()
        if not 0 < len(response.content) < 2_000_000:
            raise ValueError("Invalid feed size")
        feed = feedparser.parse(response.content)
        if feed.bozo or not feed.entries:
            raise ValueError("Invalid RSS feed")
        entries = []
        for item in feed.entries[:65]:
            try:
                entries.append(parse_entry(item, name, now))
            except (ValueError, TypeError, OverflowError):
                pass
        print("EXCHANGE_09_RSS", name, "total", len(feed.entries), "qualified", len(entries))
        return entries
    except (requests.RequestException, ValueError, TypeError) as exc:
        print("EXCHANGE_09_SOURCE_UNAVAILABLE", name, type(exc).__name__)
        return []


def corroborates(a, b) -> bool:
    if (a.get("official") or b.get("official") or a["source"] == b["source"]
            or a["exchange"] != b["exchange"] or a["category"] != b["category"]):
        return False
    ta, tb = terms(a["title"]), terms(b["title"])
    shared = ta & tb
    if len(shared) < 2 or len(shared) / max(1, len(ta | tb)) < .2:
        return False
    return abs((datetime.fromisoformat(a["published_at"]) -
                datetime.fromisoformat(b["published_at"])).total_seconds()) < 24 * 3600


def parse_official_incident(raw: dict, name: str, now: datetime) -> dict:
    """Validate one incident from the first-party, key-free Statuspage API."""
    endpoint, host, exchange = OFFICIAL_STATUS_APIS[name]
    if raw.get("status") not in ("investigating", "identified", "monitoring"):
        raise ValueError("Incident is no longer active")
    if raw.get("impact") not in ("minor", "major", "critical"):
        raise ValueError("Operational impact not declared")
    incident_id = str(raw.get("id") or "")
    if not re.fullmatch(r"[a-z0-9]{8,32}", incident_id):
        raise ValueError("Invalid incident ID")
    title = clean(exchange + ": " + clean(raw.get("name"), 145))
    if len(title) < 23 or category_of(title) is None:
        raise ValueError("Operational incident not relevant")
    created = parse_time(raw.get("created_at"), now)
    return {"source": name, "title": title, "url": endpoint,
            "published_at": created, "exchange": exchange,
            "category": category_of(title), "severe": severe(title),
            "official": True, "incident_id": incident_id,
            "incident_status": raw["status"]}


def fetch_status_incidents(name: str, now: datetime, getter=requests.get) -> list[dict]:
    """Free official JSON API, fail-closed and tolerant of outages."""
    url, host, exchange = OFFICIAL_STATUS_APIS[name]
    try:
        response = getter(url, headers={"User-Agent": HEADERS["User-Agent"],
                                        "Accept": "application/json"}, timeout=(8, 18))
        response.raise_for_status()
        if not 0 < len(response.content) < 2_000_000:
            raise ValueError("Invalid official feed size")
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("incidents"), list):
            raise ValueError("Invalid official incidents payload")
        rows = []
        for raw in payload["incidents"][:50]:
            if isinstance(raw, dict):
                try:
                    rows.append(parse_official_incident(raw, name, now))
                except (ValueError, TypeError, OverflowError):
                    pass
        print("EXCHANGE_09_OFFICIAL_API", name, "incidents",
              len(payload["incidents"]), "qualified", len(rows))
        return rows
    except (requests.RequestException, ValueError, TypeError) as exc:
        print("EXCHANGE_09_OFFICIAL_API_UNAVAILABLE", name, type(exc).__name__)
        return []


def fingerprint(item):
    identity = item["url"]
    if item.get("official") is True:
        identity += "#" + item["incident_id"]
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def load_state(path=STATE):
    if not path.is_file():
        return {"sent_urls": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(value, dict) or not isinstance(value.get("sent_urls"), list)
            or any(not isinstance(x, str) for x in value["sent_urls"])):
        raise ValueError("Corrupt anti-duplicate register")
    return value


def select_report(items, state, now):
    sent = set(state["sent_urls"])
    rows = [r for r in items if fingerprint(r) not in sent]
    rows.sort(key=lambda r: r["published_at"], reverse=True)
    for article in rows:
        alternatives = [x for x in rows if corroborates(article, x)]
        confirmation = alternatives[0] if alternatives else None
        if article["severe"] and confirmation is None and article.get("official") is not True:
            print("EXCHANGE_09_HOLD_SENSITIVE_UNCORROBORATED", article["exchange"])
            continue
        # Every item is explicitly attributed. High-impact incidents need two sources.
        used = [article] + ([confirmation] if confirmation else [])
        if any(fingerprint(i) in sent for i in used):
            continue
        result = {
            "publication": 9, "status": "real_data", "is_demo": False,
            "collected_at": now.isoformat(), "exchange": article["exchange"],
            "category": article["category"],
            "verification": "official_notice" if article.get("official") else ("cross_reported" if confirmation else "attributed_report"),
            "main": article, "confirmation": confirmation,
            "headline_fr": validate_synopsis(exchange_synopsis(article["exchange"], article["title"], article["category"])),
            "fingerprints": [fingerprint(i) for i in used],
        }
        validate_real(result, now)
        return result
    return None


def validate_real(d, now=None):
    now = now or datetime.now(UTC)
    if (not isinstance(d, dict) or d.get("publication") != 9
            or d.get("status") != "real_data" or d.get("is_demo") is not False):
        raise ValueError("Refuse non-real #09 report")
    dt = datetime.fromisoformat(d["collected_at"])
    if dt.tzinfo is None or not -300 <= (now - dt).total_seconds() <= 45 * 60:
        raise ValueError("Stale report")
    main = d.get("main")
    confirm = d.get("confirmation")
    if not isinstance(main, dict):
        raise ValueError("Main news missing")
    for item in [main] + ([confirm] if confirm else []):
        if item.get("source") in FEEDS:
            verified_url = canonical_url(item.get("url"), FEEDS[item["source"]][1])
            if item.get("official") is True or item.get("incident_id"):
                raise ValueError("False official claim on press item")
        elif item.get("source") in OFFICIAL_STATUS_APIS:
            official_url, host, exchange = OFFICIAL_STATUS_APIS[item["source"]]
            verified_url = official_url
            if (item.get("official") is not True
                    or not re.fullmatch(r"[a-z0-9]{8,32}", str(item.get("incident_id") or ""))
                    or item.get("exchange") != exchange
                    or item.get("incident_status") not in ("investigating", "identified", "monitoring")
                    or item.get("category") not in ("ACCÈS & SERVICES", "SÉCURITÉ")):
                raise ValueError("Invalid official status report")
        else:
            raise ValueError("Unknown publisher or status source")
        if verified_url != item.get("url") or not isinstance(item.get("title"), str):
            raise ValueError("Altered article")
        if (exchange_of(item["title"]) != item.get("exchange")
                or category_of(item["title"]) != item.get("category")
                or severe(item["title"]) != item.get("severe")):
            raise ValueError("Article classification mismatch")
        parse_time(item.get("published_at"), now)
    if d.get("headline_fr") != validate_synopsis(exchange_synopsis(main["exchange"], main["title"], main["category"])):
        raise ValueError("French synopsis does not reflect source")
    if main["exchange"] != d.get("exchange") or main["category"] != d.get("category"):
        raise ValueError("Unmatched main event")
    if confirm and not corroborates(main, confirm):
        raise ValueError("Unsupported cross-source confirmation")
    if main["severe"] and not confirm and main.get("official") is not True:
        raise ValueError("Sensitive media news requires two publishers")
    if confirm and (main.get("official") or confirm.get("official")):
        raise ValueError("Official source is not a second independent publisher")
    verified_class = ("official_notice" if main.get("official") else
                      ("cross_reported" if confirm else "attributed_report"))
    if d.get("verification") != verified_class:
        raise ValueError("Bad attribution class")
    if d.get("fingerprints") != [fingerprint(a) for a in ([main] + ([confirm] if confirm else []))]:
        raise ValueError("Fingerprint mismatch")


def demo_report():
    now = datetime.now(UTC)
    main = {
        "source": "CoinDesk", "title": "Binance introduces a new wallet payment service for users",
        "url": "https://www.coindesk.com/demo/fictional-binance-wallet-example",
        "published_at": (now - timedelta(hours=3)).isoformat(),
        "exchange": "BINANCE", "category": "INNOVATION", "severe": False,
    }
    return {
        "publication": 9, "status": "demo", "is_demo": True,
        "collected_at": now.isoformat(), "exchange": main["exchange"],
        "category": main["category"], "verification": "attributed_report",
        "main": main, "confirmation": None,
        "headline_fr": validate_synopsis(exchange_synopsis(main["exchange"], main["title"], main["category"])),
        "fingerprints": [fingerprint(main)],
    }


def export(demo=False, state_path=STATE):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if demo:
        dest = OUTPUT / "exchanges_v2_demo.json"
        dest.write_text(json.dumps(demo_report(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("EXCHANGE_09_DEMO", dest)
        return True
    dest = OUTPUT / "exchanges_v2_data.json"
    dest.unlink(missing_ok=True)
    now = datetime.now(UTC)
    state = load_state(state_path)
    items = []
    for name, (url, _) in FEEDS.items():
        items.extend(fetch_feed(name, url, now))
    for name in OFFICIAL_STATUS_APIS:
        items.extend(fetch_status_incidents(name, now))
    print("EXCHANGE_09_SOURCE_COVERAGE", len(FEEDS), "RSS",
          len(OFFICIAL_STATUS_APIS), "official APIs", len(items), "qualified")
    report = select_report(items, state, now)
    if report is None:
        print("EXCHANGE_09_NO_VERIFIED_NEWS — no real report or Telegram publication")
        return False
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("EXCHANGE_09_REAL", report["exchange"], report["verification"], report["main"]["source"])
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    export(demo=args.demo)
