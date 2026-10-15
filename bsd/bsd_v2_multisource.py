"""Production-safe independent CC0 calendar corroboration for BSD V2.

CC0 calendars have match DAY only, never kickoff hour or bookmaker odds.
This feature enriches provenance of already-produced BSD predictions. It
MUST NOT select new markets, manufacture external IDs/odds or overwrite BSD
selection/settlement fields. Failures degrade source confirmation ONLY.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from datetime import date,datetime,timezone
from unicodedata import normalize
import re

CALENDARS={
    "de.1":"Bundesliga",
    "en.1":"Premier League",
    "en.2":"Championship",
    "es.1":"La Liga",
    "fr.1":"Ligue 1",
    "it.1":"Serie A",
    "nl.1":"Eredivisie",
    "pt.1":"Primeira Liga",
}
HOST="https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/"
MAX_BYTES=2_000_000
DAY_ONLY_SOURCE="openfootball_cc0_calendar"
FETCH_TIMEOUT=(5,12)

def canonical(value):
    if not isinstance(value,str):return ""
    ascii_value="".join(c for c in normalize("NFKD",value) if not __import__("unicodedata").combining(c))
    return " ".join(re.findall(r"[a-z0-9]+",ascii_value.casefold()))

def safe_day(value):
    if not isinstance(value,str):return None
    try:return date.fromisoformat(value)
    except ValueError:return None

def download(session):
    """Strict bounded request source, no redirect to other domains, no huge body."""
    schedules=[]
    health=Counter()
    for basename,league in CALENDARS.items():
        health["attempted"]+=1
        url=HOST+basename+".json"
        try:
            response=session.get(url,timeout=FETCH_TIMEOUT,allow_redirects=False,
                                 headers={"Accept":"application/json"})
            if response.status_code!=200:
                raise ValueError("non_200_response")
            raw=response.content
            if len(raw)>MAX_BYTES:
                raise ValueError("oversize_document")
            doc=response.json()
            if not isinstance(doc,dict) or not isinstance(doc.get("matches"),list):
                raise ValueError("incorrect_calendar_schema")
            health["files_ok"]+=1
            for row in doc["matches"]:
                if not isinstance(row,dict):continue
                day=safe_day(row.get("date"))
                home=canonical(row.get("team1"))
                away=canonical(row.get("team2"))
                if day and home and away and home!=away:
                    schedules.append((day.isoformat(),home,away,canonical(league)))
        except Exception as exc:
            health["errors"]+=1
            health["error_"+type(exc).__name__]+=1
    return schedules,{
        "source":DAY_ONLY_SOURCE,
        "files_attempted":health["attempted"],
        "files_ok":health["files_ok"],
        "errors":health["errors"],
        "calendar_rows":len(schedules),
        "kickoff_time_supplied_by_cc0":False,
        "bookmaker_prices_supplied_by_cc0":False,
    }

def corroborate_existing_feed(data,calendar,*,now):
    if not isinstance(data,dict) or data.get("source")!="bsd" or not isinstance(data.get("matches"),list):
        raise ValueError("Only BSD-produced site feeds are eligible")
    if now.tzinfo is None:
        raise ValueError("Timezone-aware clock required")
    reference=now.astimezone(timezone.utc)
    index=defaultdict(set)
    for item in calendar:
        if not isinstance(item,tuple) or len(item)!=4:continue
        day,home,away,league=item
        if all(isinstance(x,str) and x for x in item):
            index[(day,home,away)].add(league)
    result=Counter()
    for row in data["matches"]:
        if not isinstance(row,dict) or row.get("source")!="bsd":
            continue
        # Drop stale validation copied from a previous site-feed revision.
        # Every generation must re-corroborate from today's source response.
        row.pop("multisource_verification",None)
        if row.get("status") not in ("upcoming","notstarted"):
            continue
        when=row.get("event_date")
        try:
            dt=datetime.fromisoformat(str(when).replace("Z","+00:00"))
            if dt.tzinfo is None:continue
            dt=dt.astimezone(timezone.utc)
        except (TypeError,ValueError):continue
        if dt<=reference:continue
        result["future_bsd_rows"]+=1
        key=(dt.date().isoformat(),canonical(row.get("home_team")),canonical(row.get("away_team")))
        leagues=index.get(key,set())
        expected=canonical(row.get("league"))
        if len(leagues)!=1 or not expected or expected not in leagues:
            result["not_confirmed"]+=1
            continue
        # The same match, same sides and same league on the same day appear
        # in two independent sources; time, price and selection remain BSD.
        row["multisource_verification"]={
            "cc0_calendar_corroborated":True,
            "calendar_source":DAY_ONLY_SOURCE,
            "scope":"match_day_teams_league_only",
            "actual_kickoff_source":"bsd",
            "market_price_source":"bsd_or_existing_quoted_provider",
        }
        result["confirmed"]+=1
    return {
        "enabled":True,
        "mode":"corroborate_existing_bsd_picks",
        "future_bsd_rows":result["future_bsd_rows"],
        "calendar_confirmed":result["confirmed"],
        "not_confirmed":result["not_confirmed"],
        "never_adds_external_picks":True,
        "changes_prediction_or_quoted_prices":False,
        "changes_pub_policy_or_event_identity":False,
        "no_telegram_messages_sent":True,
    }

def annotate(output,*,session,now):
    """Run only after original BSD V2 generation, never before its market gates."""
    schedules,health=download(session)
    results=corroborate_existing_feed(output,schedules,now=now)
    return {**health,**results,"status":"ok" if health["files_ok"]==len(CALENDARS) else "degraded"}
