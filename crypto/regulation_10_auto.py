"""#10 fully automatic, conservative institutional-announcement reporting.

This verifies *publication of an official crypto/regulatory announcement*, not
the announcement's binding legal force. No external AI models, no paid APIs,
no human sign-off and no fabricated dates, translations or legal consequences.

Only first-party SEC/ESMA/European Commission RSS items are eligible.
A real HTTPS HTML article must independently contain a matching visible H1
or og:title. Every source failure or uncertainty fails closed.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from crypto import export_regulation_v2 as reg

UTC = timezone.utc
OUTPUT = Path("crypto/generated/test/regulation_10_auto.json")
MAX_AGE_HOURS = 48
USER_AGENT = "MrXPRONOS-CryptoNews/1.0 (official-source verifications)"
ALLOWED = reg.OFFICIAL_ALLOWED_HOSTS


class PageTitle(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.in_h1 = False
        self.titles = []
        self.headlines = []

    def handle_starttag(self, name, attrs):
        d = dict(attrs)
        if name == "title":
            self.in_title = True
        if name == "h1":
            self.in_h1 = True
        if name == "meta" and d.get("property", "").lower() in ("og:title", "twitter:title"):
            value = d.get("content", "")
            if value:
                self.titles.append(value)

    def handle_endtag(self, name):
        if name == "title":
            self.in_title = False
        if name == "h1":
            self.in_h1 = False

    def handle_data(self, data):
        if self.in_title:
            self.titles.append(data)
        if self.in_h1:
            self.headlines.append(data)


def significant_words(value):
    return set(re.findall(r"[a-z0-9]+", html.unescape(value).lower())) - {
        "a","an","the","on","of","in","to","and","for","or","as","with",
        "by","its","at","new","from","regarding","eu","us","news","press",
        "release","esma","sec","commission","european","announces",
    }


def headline_matches(rss_title, article_html):
    reader = PageTitle()
    reader.feed(article_html)
    original = significant_words(rss_title)
    if len(original) < 4:
        return False
    headlines = [" ".join(reader.headlines)] + reader.titles
    for headline in headlines:
        words = significant_words(headline)
        if len(words & original) >= max(4, int(0.65 * len(original))):
            return True
    return False


def is_authority_url(source: str, url: str) -> bool:
    u = urlsplit(str(url))
    host = (u.hostname or "").lower().removeprefix("www.")
    return bool(source in ALLOWED and host in ALLOWED[source] and
                u.scheme == "https" and u.username is None and u.password is None
                and u.port in (None, 443) and len(u.path) > 9)


def fetch_official_html(source, url, getter=requests.get):
    if not is_authority_url(source, url):
        raise ValueError("Source is not an authorized official authority")
    current = url
    for _ in range(3):
        if not is_authority_url(source, current):
            raise ValueError("Official article redirected away from allowed authority")
        response = getter(current, headers={"User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml"}, timeout=(8, 18),
            allow_redirects=False, stream=True)
        try:
            code = response.status_code
            if code in (301, 302, 303, 307, 308):
                target = urljoin(current, response.headers.get("Location", ""))
                if not is_authority_url(source, target):
                    raise ValueError("Official article redirects to untrusted host")
                current = target
                continue
            response.raise_for_status()
            ctype = response.headers.get("Content-Type", "").lower()
            if "text/html" not in ctype and "application/xhtml+xml" not in ctype:
                raise ValueError("Not an official HTML publication")
            blocks = []
            total = 0
            for block in response.iter_content(chunk_size=8192):
                total += len(block)
                if total > 1_500_000:
                    raise ValueError("Official page exceeds safe size")
                blocks.append(block)
            if total < 300:
                raise ValueError("Official page body too small")
            return b"".join(blocks).decode("utf-8",errors="replace"), current
        finally:
            response.close()
    raise ValueError("Too many official redirects")


def verify_publication(row, now=None, getter=requests.get):
    now = now or datetime.now(UTC)
    if row.get("source") not in reg.OFFICIAL or row.get("official") is not True:
        raise ValueError("Media articles alone can never self-authorize legal news")
    if not is_authority_url(row["source"], row["url"]):
        raise ValueError("Official URL tampered")
    title = row["title"]
    if not reg.CRYPTO.search(title) or not reg.REGULATION.search(title):
        raise ValueError("No verified crypto regulatory news subject")
    reg.iso_time(row["published_at"], now)
    published = datetime.fromisoformat(row["published_at"])
    if (now-published).total_seconds() > 3600*MAX_AGE_HOURS:
        raise ValueError("Institutional notice older than automatic publication limit")
    if row["region"] != reg.REGIONS[row["source"]] or row["stage"] != reg.stage(title):
        raise ValueError("Regulatory source classification mismatch")
    page, resolved_url = fetch_official_html(row["source"], row["url"],getter)
    if not headline_matches(title,page):
        raise ValueError("Official page headline does not independently match RSS article")
    return {
        "publication":10, "status":"official_announcement_verified",
        "is_demo":False, "legal_status_confirmed":False,
        "collected_at":now.isoformat(), "verified_at":now.isoformat(),
        "primary":row,
        "fingerprint":reg.fingerprint(row),
        "official_verified_url":resolved_url,
        "auto_check":{
            "rss_first_party":True,"official_html":True,
            "headline_matched":True,"fresh":True,
            "human_approval_required":False,
            "verification_scope":"Official publication existence, NOT binding legal status",
        },
    }


def validate_auto(document, now=None):
    now = now or datetime.now(UTC)
    if (document.get("publication") != 10 or
            document.get("status") != "official_announcement_verified" or
            document.get("is_demo") is not False or
            document.get("legal_status_confirmed") is not False):
        raise ValueError("No unverified legal ruling can be auto-published")
    row = document.get("primary")
    if not isinstance(row,dict) or row.get("source") not in reg.OFFICIAL:
        raise ValueError("News is not first-party regulator announcement")
    if row.get("official") is not True or row.get("region") != reg.REGIONS[row["source"]]:
        raise ValueError("Regulator identity or jurisdiction mismatch")
    if (not is_authority_url(row.get("url",""),row.get("source")) and
            not is_authority_url(row.get("source",""),row.get("url",""))):
        raise ValueError("Invalid institutional URL")
    if not is_authority_url(row["source"],document.get("official_verified_url","")):
        raise ValueError("Official target lost source origin")
    if (row.get("stage") != reg.stage(row["title"]) or
            not reg.CRYPTO.search(row["title"]) or
            not reg.REGULATION.search(row["title"])):
        raise ValueError("Altered regulatory article")
    if document.get("fingerprint") != reg.fingerprint(row):
        raise ValueError("Altered source URL identity")
    checks = document.get("auto_check",{})
    if (not isinstance(checks,dict) or
            any(checks.get(k) is not True for k in ("rss_first_party","official_html","headline_matched","fresh")) or
            checks.get("human_approval_required") is not False):
        raise ValueError("Official source checks missing")
    verified = datetime.fromisoformat(document["verified_at"])
    if verified.tzinfo is None or not -300 <= (now-verified).total_seconds() <= 15*60:
        raise ValueError("Institutional announcement verification too old")
    reg.iso_time(row["published_at"],now)
    if (now-datetime.fromisoformat(row["published_at"])).total_seconds()>MAX_AGE_HOURS*3600:
        raise ValueError("Stale institutional announcement")
    return document


def collect(state, now=None, fetcher=None, verifier=verify_publication):
    now = now or datetime.now(UTC)
    fetcher = fetcher or reg.fetch_feed
    rows = []
    for name,(url,_) in reg.REGULATOR_FEEDS.items():
        try:
            rows.extend(fetcher(name,url,now))
        except (requests.RequestException,ValueError):
            print("REG10_FEED_UNAVAILABLE",name)
    posted = {str(key).split(":")[-1] for key in state.get("sent",{})
              if str(key).startswith("reg10_official:")}
    rows = [x for x in rows if x.get("official") is True and
            reg.fingerprint(x) not in posted]
    rows.sort(key=lambda x:x["published_at"],reverse=True)
    for row in rows[:15]:
        try:
            verified=verifier(row,now)
            validate_auto(verified,now)
            return verified
        except (ValueError,requests.RequestException,KeyError,TypeError) as exc:
            print("REG10_OFFICIAL_REJECTED",row.get("source"),type(exc).__name__,str(exc)[:120])
    return None


def export(state, path=OUTPUT):
    path.unlink(missing_ok=True)
    verified=collect(state)
    if verified is None:
        print("REG10_NO_QUALIFIED_OFFICIAL_NEWS")
        return False
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(verified,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("REG10_OFFICIAL_AUTO_VERIFIED",verified["primary"]["source"],
          verified["fingerprint"],verified["primary"]["url"])
    return True
