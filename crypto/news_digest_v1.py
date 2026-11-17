"""Actu Crypto #11: factual global RSS news, polled every 30 minutes.

Free feeds only. No AI-generated facts, no fabricated translations.
Cross-source story matching uses actor/country/event/tokens plus URL fingerprints.
The production caller records messages only AFTER Telegram confirms delivery.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import textwrap
import unicodedata
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import feedparser
import requests
from PIL import Image, ImageDraw, ImageFont
from crypto.news_sources_v2 import GLOBAL_NEWS_FEEDS, FRENCH_NEWS_FEEDS
from crypto import news_media_v1 as media

UTC = timezone.utc
MAX_AGE_HOURS = 30
MAX_PER_RUN = 3
MAX_PER_DAY = 18
STORY_HISTORY_DAYS = 21
OUTPUT = Path("crypto/generated/test/news_v1.png")
HEADERS = {
    "User-Agent": "MrXPRONOS-ActuCrypto/1.1 (RSS reading, original-source attribution)",
    "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.3",
}

# These are *headlines*, not endorsements or verified legal effects.
EXCLUDED = (
    "sponsored", "advertorial", "partner content", "press release distribution",
    "opinion:", "op-ed", "price prediction", "technical analysis",
    "daily roundup", "weekly roundup", "weekly recap", "what is ",
    "how to buy", "how to ", "top 10 coins", "top 5 coins",
    "not financial advice", "buy now", "best cryptos to buy",
    "analyse technique", "cours du bitcoin", "prevision de prix",
    "prévision de prix", "prédiction de prix", "guide complet",
    "ce qu'il faut savoir", "le prix de ", "why bitcoin ",
)
# "Price-only" news stays in the existing numeric market posts, not this news channel.
PRICE_ONLY = re.compile(
    r"\b(price prediction|price analysis|technical analysis|prix du bitcoin|"
    r"forecast|resistance level|support level|price target|outlook)\b", re.I
)
CRYPTO_CUES = {
    "crypto", "cryptocurrency", "cryptocurrencies", "cryptomonnaie",
    "cryptomonnaies", "bitcoin", "btc", "ethereum", "ether", "eth",
    "blockchain", "stablecoin", "stablecoins", "usdt", "usdc", "defi",
    "web3", "token", "tokens", "solana", "xrp", "binance", "coinbase",
    "kraken", "okx", "bybit", "tether", "circle", "wallet",
}
ALIASES = {
    "btc": "bitcoin", "eth": "ethereum", "ether": "ethereum",
    "cryptocurrencies": "crypto", "cryptocurrency": "crypto",
    "cryptomonnaie": "crypto", "cryptomonnaies": "crypto",
    "blockchains": "blockchain", "stablecoins": "stablecoin",
    "tokens": "token", "cryptos": "crypto",
    "nigerian": "nigeria", "nigeriane": "nigeria", "nigerianes": "nigeria",
    "nigeria": "nigeria", "ghanaian": "ghana", "ghanaeennes": "ghana",
    "togolese": "togo", "togolais": "togo", "beninese": "benin",
    "kenyan": "kenya", "african": "africa", "africain": "africa",
    "etats": "usa", "united": "usa", "americain": "usa",
    "approves": "approve", "approved": "approve", "approval": "approve",
    "approuve": "approve", "approuvee": "approve", "approuvent": "approve",
    "authorizes": "approve", "autorise": "approve",
    "banned": "ban", "bans": "ban", "interdit": "ban", "interdiction": "ban",
    "launches": "launch", "launched": "launch", "lance": "launch",
    "lancement": "launch", "unveils": "launch", "devoile": "launch",
    "adopts": "adopt", "adopted": "adopt", "adopte": "adopt",
    "adoption": "adopt", "accepts": "adopt", "accepte": "adopt",
    "introduces": "introduce", "introduit": "introduce",
    "announces": "announce", "announced": "announce", "annonce": "announce",
    "partnership": "partner", "partnerships": "partner",
    "partners": "partner", "partenariat": "partner", "associe": "partner",
    "hack": "hack", "hacked": "hack", "piratage": "hack", "pirate": "hack",
    "stolen": "hack", "vol": "hack", "breach": "hack",
    "lawsuit": "lawsuit", "poursuites": "lawsuit",
    "fine": "fine", "fines": "fine", "amende": "fine",
    "licensed": "license", "licence": "license", "licenses": "license",
    "retrait": "withdrawal", "retraits": "withdrawal",
    "withdrawals": "withdrawal", "withdrawal": "withdrawal",
    "payments": "payment", "paiements": "payment", "paiement": "payment",
    "regulations": "regulation", "reglementation": "regulation",
    "regulatory": "regulation", "regulateur": "regulation",
}
COUNTRY_TERMS = {
    "nigeria", "ghana", "togo", "benin", "kenya", "uganda",
    "rwanda", "cameroon", "cameroun", "senegal", "senegalais",
    "cotedivoire", "ivoire", "mali", "burkina", "morocco", "maroc",
    "southafrica", "zimbabwe", "usa", "canada", "france", "germany",
    "allemagne", "india", "inde", "china", "chine", "japan", "japon",
    "brazil", "bresil", "argentina", "argentine", "uae", "dubai",
    "europe", "european", "uk", "britain", "africa", "afrique",
}
COUNTRY_NORMALIZE = {
    "cameroun": "cameroon", "ivoire": "cotedivoire", "maroc": "morocco",
    "allemagne": "germany", "inde": "india", "chine": "china",
    "japon": "japan", "bresil": "brazil", "argentine": "argentina",
    "european": "europe", "britain": "uk", "afrique": "africa",
    "senegalais": "senegal",
}
ACTORS = {
    "bitcoin", "ethereum", "solana", "xrp", "tether", "circle", "usdt",
    "usdc", "binance", "coinbase", "okx", "bybit", "kraken", "bitget",
    "blackrock", "fidelity", "strategy", "microstrategy", "sec",
    "cftc", "esma", "visa", "mastercard", "paypal", "stripe",
    "swift", "imf", "fmi", "ecb", "bce", "fed", "uniswap", "aave",
    "tron", "bnb", "blockchain", "stablecoin",
}
STOP = set((
    "a an and are as at be by can did do for from has have how in into is it its "
    "of on or over the their this to was were what when where who will with you "
    "after amid around about report reports reported says said latest news crypto "
    "cryptocurrency cryptos blockchain digital asset assets tokens token new more "
    "than first major market markets firm platform platforms users companies company "
    "des les le la un une du de en et sur pour dans aux au avec apres que qui "
    "est sont selon annonce annonces nouvelle nouvelles actualite pourquoi comme "
    "aussi ses son leur leurs plus cette ce ces fait faire face contre aux "
    "usd us dollar dollars 2025 2026 2027"
).split())
CATEGORY_PATTERNS = (
    ("SÉCURITÉ", r"\b(hack|piratage|breach|exploit|stolen|scam|fraud|arrest|attack|vol|ransomware|phishing)\b"),
    ("RÉGLEMENTATION", r"\b(regulation|regulator|regulatory|law|laws|bill|license|sec|cftc|esma|"
     r"court|lawsuit|fine|ban|interdiction|tax|legal|compliance|legislation|"
     r"reglementation|loi|regle|sanction|autorise|approve|directive)\b"),
    ("PAIEMENTS & ADOPTION", r"\b(payment|paiement|adopt|accept|merchant|remittance|"
     r"transfer|transfert|stablecoin|usdt|usdc|visa|mastercard|bank|banque|integration)\b"),
    ("ENTREPRISES", r"\b(acquire|acquisition|merger|funding|raised|invest|"
     r"partnership|partner|buy|buys|treasury|entreprise|partenariat|rachete|levee)\b"),
    ("TECHNOLOGIE", r"\b(upgrade|protocol|mainnet|network|launch|"
     r"blockchain|layer|fork|staking|wallet|reseau|mise|deploie)\b"),
)
SENSITIVE = re.compile(
    r"\b(hack|piratage|breach|stolen|fraud|scam|bankrupt|insolvent|"
    r"sanction|ban|interdiction|law\s+approved|law\s+passed|"
    r"withdrawals?\s+halted|retraits?\s+suspendus)\b", re.I
)
AFRICAN = {
    "nigeria", "ghana", "togo", "benin", "kenya", "uganda", "rwanda",
    "cameroon", "senegal", "cotedivoire", "mali", "burkina", "morocco",
    "southafrica", "zimbabwe", "africa",
}


def clean(value, limit=300):
    v = re.sub(r"<[^>]+>", " ", html.unescape(str(value or "")))
    return re.sub(r"[\x00-\x1f\x7f]+", " ", re.sub(r"\s+", " ", v)).strip()[:limit]


def normalize(value):
    value = unicodedata.normalize("NFKD", str(value or "").lower())
    return value.encode("ascii", "ignore").decode("ascii")


def words(value):
    value = normalize(value).replace("cote d'ivoire", "cotedivoire")
    value = value.replace("ivory coast", "cotedivoire")
    value = value.replace("united states", "usa").replace("south africa", "southafrica")
    value = value.replace("european union", "europe")
    raw = re.findall(r"[a-z0-9]+", value)
    return [ALIASES.get(w, w) for w in raw]


def category(title):
    w = " ".join(words(title))
    for label, pattern in CATEGORY_PATTERNS:
        if re.search(pattern, w, re.I):
            return label
    return "ACTUALITÉ CRYPTO"


def signature(item):
    w = words(item["title"])
    significant = {x for x in w if len(x) > 2 and x not in STOP}
    countries = {COUNTRY_NORMALIZE.get(x, x) for x in w if x in COUNTRY_TERMS}
    actors = {x for x in w if x in ACTORS}
    figures = {x for x in w if re.fullmatch(r"\d+(?:m|b|k)", x)}
    return {
        "tokens": sorted(significant),
        "countries": sorted(countries),
        "actors": sorted(actors),
        "figures": sorted(figures),
        "category": category(item["title"]),
    }


def canonical_url(url, allowed_host):
    u = urlsplit(str(url or "").strip())
    host = (u.hostname or "").lower()
    base = allowed_host.lower()
    if (u.scheme != "https" or host not in {base, "www." + base}
            or u.username or u.password or u.port not in (None, 443)
            or len(u.path.strip("/")) < 5):
        raise ValueError("RSS article URL is not on approved publisher host")
    return urlunsplit(("https", host, u.path.rstrip("/"), "", ""))


def published_at(entry, now):
    raw = entry.get("published_parsed") or entry.get("updated_parsed")
    if raw:
        dt = datetime(*raw[:6], tzinfo=UTC)
    else:
        raw = entry.get("published") or entry.get("updated")
        if not raw:
            raise ValueError("RSS publication timestamp missing")
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            dt = parsedate_to_datetime(str(raw))
        if dt.tzinfo is None:
            raise ValueError("RSS timestamp lacks timezone")
        dt = dt.astimezone(UTC)
    if not -300 <= (now - dt).total_seconds() <= MAX_AGE_HOURS * 3600:
        raise ValueError("RSS news expired or timestamp in future")
    return dt.isoformat()


def is_relevant(title, summary):
    t = normalize(title)
    if len(title) < 30 or any(term in t for term in EXCLUDED) or PRICE_ONLY.search(t):
        return False
    tokens = set(words(title + " " + summary[:140]))
    if not (tokens & {ALIASES.get(x, x) for x in CRYPTO_CUES} or
            tokens & ACTORS):
        return False
    # News should describe a concrete development, not a vague prediction/opinion.
    w = " ".join(words(title))
    return category(title) != "ACTUALITÉ CRYPTO" or bool(
        re.search(r"\b(announce|approve|launch|adopt|introduce|"
                  r"invest|fund|rise|fall|crash|record|"
                  r"vote|buy|sell|accept|regulate|partner|"
                  r"annule|ouvre|ferme|annonce|devoile|"
                  r"programme|developpe|developpement)\b", w)
    )


def parse_entry(entry, source, now):
    title = clean(entry.get("title"), 210)
    summary = clean(entry.get("summary") or entry.get("description"), 300)
    if not is_relevant(title, summary):
        raise ValueError("Non-event or unrelated RSS headline")
    url = canonical_url(entry.get("link"), GLOBAL_NEWS_FEEDS[source][1])
    row = {
        "source": source, "title": title, "summary": summary, "url": url,
        "published_at": published_at(entry, now),
        "french": source in FRENCH_NEWS_FEEDS,
        "image_candidates": media.images_from_rss(entry, url),
    }
    row.update(signature(row))
    row["sensitive"] = bool(SENSITIVE.search(normalize(title)))
    return row


def fetch_feed(source, url, now, getter=requests.get):
    try:
        resp = getter(url, headers=HEADERS, timeout=(8, 18))
        resp.raise_for_status()
        if not 0 < len(resp.content) <= 2_000_000:
            raise ValueError("Bad RSS byte length")
        feed = feedparser.parse(resp.content)
        if not feed.entries:
            raise ValueError("RSS feed empty or unreadable")
        accepted = []
        for entry in feed.entries[:75]:
            try:
                accepted.append(parse_entry(entry, source, now))
            except (TypeError, ValueError, OverflowError, AttributeError):
                pass
        print("CRYPTO_NEWS11_RSS", source, "total", len(feed.entries),
              "valid_recent", len(accepted), "bozo", bool(feed.bozo))
        return accepted, True
    except (requests.RequestException, ValueError, TypeError, OverflowError) as exc:
        print("CRYPTO_NEWS11_RSS_FAILED", source, type(exc).__name__)
        return [], False


def hashes(url):
    raw = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return (raw[:20], raw[:24])


def same_event(left, right):
    if left.get("url") and left.get("url") == right.get("url"):
        return True
    a = signature(left) if "tokens" not in left else left
    b = signature(right) if "tokens" not in right else right
    if a["category"] != b["category"]:
        return False
    a_country, b_country = set(a["countries"]), set(b["countries"])
    if a_country and b_country and not a_country.intersection(b_country):
        return False
    a_actor, b_actor = set(a["actors"]), set(b["actors"])
    if a_actor and b_actor and not a_actor.intersection(b_actor):
        return False
    a_fig, b_fig = set(a["figures"]), set(b["figures"])
    if a_fig and b_fig and not a_fig.intersection(b_fig):
        return False
    a_tok, b_tok = set(a["tokens"]), set(b["tokens"])
    shared = a_tok & b_tok
    union = a_tok | b_tok
    # Broad crypto buzzwords never identify a specific event on their own.
    informative = shared - {"bitcoin", "ethereum", "stablecoin", "blockchain", "crypto"}
    same_anchor = bool(a_actor & b_actor or a_country & b_country)
    if len(informative) < 2:
        return False
    overlap = len(shared) / max(len(union), 1)
    return (overlap >= .43 or
            (same_anchor and len(informative) >= 3 and overlap >= .29))


def already_sent(item, state):
    urls = state.get("news_fingerprints") or {}
    if any(h in urls for h in hashes(item["url"])):
        return True
    for old in state.get("news_stories") or []:
        if not isinstance(old, dict) or not old.get("title"):
            continue
        try:
            at = datetime.fromisoformat(old["sent_at"].replace("Z", "+00:00"))
            bt = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
            if abs((bt - at).total_seconds()) > STORY_HISTORY_DAYS * 86400:
                continue
            if same_event(item, old):
                return True
        except (ValueError, KeyError, TypeError):
            continue
    return False


def score(item, group_size, now):
    age = (now - datetime.fromisoformat(item["published_at"])).total_seconds() / 3600
    rank = {"SÉCURITÉ": 44, "RÉGLEMENTATION": 42,
            "PAIEMENTS & ADOPTION": 38, "ENTREPRISES": 32,
            "TECHNOLOGIE": 30, "ACTUALITÉ CRYPTO": 20}
    pts = rank[item["category"]] + min(group_size, 3) * 7
    pts += max(0, 18 - int(age))
    if set(item["countries"]) & AFRICAN:
        pts += 19
    if item["french"]:
        pts += 5
    return pts


def collect(state, now=None, fetcher=fetch_feed):
    now = now or datetime.now(UTC)
    all_items, working = [], 0
    for source, (url, _host) in GLOBAL_NEWS_FEEDS.items():
        items, ok = fetcher(source, url, now)
        working += bool(ok)
        all_items.extend(items)
    print("CRYPTO_NEWS11_COVERAGE", working, "/", len(GLOBAL_NEWS_FEEDS),
          "RSS sources,", len(all_items), "relevant recent articles")
    if working < 3:
        raise RuntimeError("Less than 3 live crypto RSS sources: publication halted")

    groups = []
    # Deduplicate within every scan before ranking. Also protect existing sent events.
    all_items.sort(key=lambda a: a["published_at"], reverse=True)
    for item in all_items:
        if already_sent(item, state):
            continue
        found = next((g for g in groups if any(same_event(item, x) for x in g)), None)
        if found is None:
            groups.append([item])
        else:
            if not any(x["url"] == item["url"] for x in found):
                found.append(item)
    candidates = []
    for group in groups:
        distinct = {x["source"] for x in group}
        # Independent confirmation required for sensitive allegations/headlines.
        if any(x["sensitive"] for x in group) and len(distinct) < 2:
            print("CRYPTO_NEWS11_HOLD_SENSITIVE", group[0]["title"][:90])
            continue
        lead = sorted(group, key=lambda x: (x["french"], x["published_at"]), reverse=True)[0]
        # Strictly freshest-first within the same priority class.
        candidate = {"main": lead, "others": [x for x in group if x["source"] != lead["source"]][:2]}
        candidate["score"] = score(lead, len(distinct), now)
        candidates.append(candidate)
    candidates.sort(key=lambda x: (x["score"], x["main"]["published_at"]), reverse=True)
    print("CRYPTO_NEWS11_CANDIDATES", len(candidates),
          "cross-source grouped; publishable, remaining")
    return candidates


def day_count(state, now=None):
    now = now or datetime.now(UTC)
    count = 0
    for meta in (state.get("sent") or {}).values():
        if not isinstance(meta, dict) or meta.get("number") != 11:
            continue
        try:
            when = datetime.fromisoformat(meta["sent_at"].replace("Z", "+00:00"))
            if when.astimezone(UTC).date() == now.date():
                count += 1
        except (ValueError, KeyError):
            pass
    return count


def mark_sent(state, candidate, message_id, sent_at=None):
    stamped = (sent_at or datetime.now(UTC)).isoformat()
    main = candidate["main"]
    key = "news:11:" + hashes(main["url"])[1]
    sent = state.setdefault("sent", {})
    if key in sent:
        raise ValueError("Already-confirmed send cannot be re-recorded")
    sent[key] = {"number": 11, "message_id": message_id,
                 "sent_at": stamped, "source": main["source"],
                 "title": main["title"], "url": main["url"]}
    register_story(state, main, message_id, candidate["others"], stamped)


def register_story(state, main, message_id, others=(), stamped=None):
    """Shared dedupe record for #08, #09 and #11 after a CONFIRMED send."""
    stamped = stamped or datetime.now(UTC).isoformat()
    entry = dict(main)
    entry.update(signature(entry))
    entry["sent_at"] = stamped
    entry["message_id"] = message_id
    state.setdefault("news_stories", []).append({
        k: entry[k] for k in (
            "title", "url", "source", "published_at", "sent_at",
            "message_id", "tokens", "countries", "actors", "figures", "category"
        ) if k in entry
    })
    # Stable URLs are remembered even when syndicated by multiple publishers.
    fp = state.setdefault("news_fingerprints", {})
    for row in [main] + list(others):
        if not row:
            continue
        for h in hashes(row["url"]):
            fp[h] = {"number": 11, "message_id": message_id}
    state["news_stories"] = state["news_stories"][-600:]


def article_title(candidate):
    a = candidate["main"]
    if a["french"]:
        return a["title"]
    return a["title"]  # Original verified headline; never machine-invent a translation.


def caption(candidate):
    a = candidate["main"]
    label = a["category"]
    place = next(iter(a["countries"]), "MONDE").upper()
    title = article_title(candidate)
    lead = (
        "📰 ACTU CRYPTO · " + label + "\n"
        + "🌍 " + place + " | " + a["source"] + "\n\n"
        + title + "\n\n"
    )
    if a["summary"] and a["french"]:
        lead += "Selon le résumé RSS : " + a["summary"][:190] + "\n\n"
    elif not a["french"]:
        lead += "Titre original du média (anglais) ; information attribuée à sa source.\n\n"
    lead += "Source : " + a["source"] + "\n" + a["url"] + "\n"
    if candidate["others"]:
        co = candidate["others"][0]
        lead += "Autre média : " + co["source"] + "\n" + co["url"] + "\n"
    lead += "📅 " + a["published_at"][:16].replace("T", " ") + " UTC"
    if len(lead) > 1024:
        lead = lead.replace("Selon le résumé RSS : " + a["summary"][:190] + "\n\n", "")
    if len(lead) > 1024:
        raise ValueError("News caption over Telegram 1024-character limit")
    return lead


def render(candidate, path=OUTPUT):
    main = candidate["main"]
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1200, 630), (11, 15, 24))
    draw = ImageDraw.Draw(image)
    for y in range(630):
        v = y / 630
        draw.line((0, y, 1200, y), fill=(11 + int(14 * v),
                                       15 + int(12 * v), 24 + int(18 * v)))
    draw.rectangle((0, 0, 1200, 13), fill=(215, 172, 69))
    draw.rectangle((62, 102, 1137, 105), fill=(215, 172, 69))
    bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    def font(path_name, size):
        return ImageFont.truetype(path_name, size) if os.path.isfile(path_name) else ImageFont.load_default()
    draw.text((62, 43), "MR XPRONOS  /  ACTU CRYPTO", font=font(bold, 31),
              fill=(232, 193, 107))
    draw.text((62, 136), main["category"], font=font(bold, 26),
              fill=(232, 193, 107))
    title = article_title(candidate)
    size = 47 if len(title) < 115 else 39
    f = font(bold, size)
    lines, line = [], ""
    for w in title.split():
        candidate_line = (line + " " + w).strip()
        if draw.textbbox((0, 0), candidate_line, font=f)[2] > 1060 and line:
            lines.append(line)
            line = w
        else:
            line = candidate_line
    if line:
        lines.append(line)
    for idx, sentence in enumerate(lines[:5]):
        draw.text((62, 201 + idx * (size + 11)), sentence, font=f,
                  fill=(248, 248, 250))
    draw.rectangle((62, 557, 1137, 560), fill=(215, 172, 69))
    draw.text((62, 572), main["source"] + "  |  " + main["published_at"][:10],
              font=font(regular, 22), fill=(224, 225, 227))
    image.save(path, "PNG", optimize=True)
    return path
