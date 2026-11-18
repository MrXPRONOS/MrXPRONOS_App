#!/usr/bin/env python3
"""Prime Cine Radar D1 with real public Simkl weekly community trends.

Runs in GitHub Actions with existing Cloudflare D1 token. Stores metadata only:
titles, descriptions, safe original poster links and Simkl reference URLs.
No Telegram messages, channel writes, media files, or private user records.
"""
import json
import os
import re
import time
from datetime import datetime, timezone
from html import unescape
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ACCOUNT = "9c86118191b804d91b5f5b2c89114999"
DATABASE = "fa8b5009-bc1a-4a6e-b143-7a487c7297a5"
KINDS = (("films", "movies"), ("series", "tv"), ("animes", "anime"))
URL_RE = re.compile(r"^/(movies|tv|anime)/([1-9][0-9]{0,11})(?:/[a-z0-9-]+)?/?$", re.I)
POSTER_RE = re.compile(r"^[a-z0-9_/-]{2,160}$", re.I)
TITLE_RE = re.compile(r"<[^>]{0,200}>")
SQL = (
    "INSERT INTO radar_titles"
    "(id,kind,title,title_original,aliases,summary,year,poster_url,source_url,source,trend_rank)"
    " VALUES(?,?,?,?,?,?,?,?,?,?,?)"
    " ON CONFLICT(id) DO UPDATE SET title=excluded.title,"
    "title_original=excluded.title_original,aliases=excluded.aliases,"
    "summary=excluded.summary,year=excluded.year,poster_url=excluded.poster_url,"
    "source_url=excluded.source_url,trend_rank=excluded.trend_rank,"
    "last_seen_at=CURRENT_TIMESTAMP"
)


def fetch_chart(category):
    url = f"https://data.simkl.in/discover/trending/{category}/week_100.json"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "CineRadar/1.2"})
    with urlopen(request, timeout=24) as response:
        payload = json.load(response)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in (category, "shows", "anime", "movies"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise RuntimeError(f"simkl_{category}_bad_schema")


def safe_text(value, maximum):
    raw = TITLE_RE.sub(" ", str(value or ""))
    return " ".join(unescape(raw).split())[:maximum]


def normalize(kind, category, entry, rank):
    if not isinstance(entry, dict):
        return None
    item = entry.get("movie") or entry.get("show") or entry.get("anime") or entry
    if not isinstance(item, dict):
        return None
    path = str(item.get("url") or entry.get("url") or "")
    if path.startswith("https://simkl.com/"):
        path = path[len("https://simkl.com"):]
    matched = URL_RE.fullmatch(path)
    if not matched or matched.group(1).lower() != category:
        return None
    title = safe_text(item.get("title") or entry.get("title"), 130)
    poster_id = str(item.get("poster") or entry.get("poster") or "").strip()
    if poster_id.endswith("_m.jpg") and poster_id.startswith("https://simkl.in/posters/"):
        poster_id = poster_id[len("https://simkl.in/posters/"):-len("_m.jpg")]
    if not title or not POSTER_RE.fullmatch(poster_id):
        return None
    year_text = str(item.get("year") or entry.get("year") or "")
    year = int(year_text) if re.fullmatch(r"(19|20)[0-9]{2}", year_text) else None
    overview = safe_text(item.get("overview") or entry.get("overview"), 420)
    original = safe_text(item.get("original_title") or title, 130)
    aliases = item.get("alt_titles") or entry.get("alt_titles") or []
    if isinstance(aliases, list):
        aliases = "|".join(safe_text(x, 65) for x in aliases[:5] if isinstance(x, str))
    else:
        aliases = ""
    return (
        f"simkl-{kind}-{matched.group(2)}", kind, title, original, str(aliases)[:300],
        overview, year, "https://simkl.in/posters/" + poster_id + "_m.jpg",
        "https://simkl.com" + path, "simkl", rank
    )


def d1_batch(token, queries):
    api = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/d1/database/{DATABASE}/query"
    for index in range(0, len(queries), 20):
        chunk = queries[index:index + 20]
        req = Request(api, data=json.dumps({"batch": [
            {"sql": sql, "params": args} for sql, args in chunk
        ]}).encode(), headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }, method="POST")
        try:
            with urlopen(req, timeout=35) as response:
                payload = json.load(response)
        except HTTPError as error:
            raise RuntimeError(f"d1_status_{error.code}") from None
        if not payload.get("success") or len(payload.get("result", [])) != len(chunk) or not all(
            x.get("success") for x in payload["result"]
        ):
            raise RuntimeError("d1_batch_failed")


def main():
    token = (os.getenv("CLOUDFLARE_API_TOKEN") or os.getenv("CF_API_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("Cloudflare D1 credentials missing")
    for kind, category in KINDS:
        chart = fetch_chart(category)
        entries = []
        ids = set()
        for rank, item in enumerate(chart[:100], start=1):
            normalized = normalize(kind, category, item, rank)
            if normalized and normalized[0] not in ids:
                ids.add(normalized[0])
                entries.append(normalized)
            if len(entries) >= 20:
                break
        if not entries:
            raise RuntimeError(f"simkl_{kind}_no_valid_titles")
        d1_batch(token, [(SQL, list(row)) for row in entries])
        d1_batch(token, [(
            "INSERT INTO radar_runs(job_name,last_success_at,last_attempt_at,last_error,last_count)"
            " VALUES(?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'',?)"
            " ON CONFLICT(job_name) DO UPDATE SET last_success_at=CURRENT_TIMESTAMP,"
            "last_attempt_at=CURRENT_TIMESTAMP,last_error='',last_count=excluded.last_count",
            [f"trends_{kind}", len(entries)]
        )])
        print("CINE_RADAR_SIMKL_SYNC", json.dumps({"category": kind, "titles": len(entries)}))
        time.sleep(.3)


if __name__ == "__main__":
    main()
