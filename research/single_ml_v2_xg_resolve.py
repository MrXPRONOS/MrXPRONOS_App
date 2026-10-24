"""Conservative V1-to-V2 football fixture reconciliation.

V1 and V2 identifiers are unrelated unless independently verified. Search
V2 scheduled events by UTC date, match both club names, kickoff and (when
available) fulltime score. Never pick a best guess if the match is ambiguous.

A date index permits one request for many fixtures and is encrypted at rest.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import timedelta
from dataclasses import dataclass
import unicodedata, re
from single_ml_v2_data import utc_dt

def normalise(text):
    text=unicodedata.normalize("NFKD",str(text or ""))
    return re.sub(r"[^a-z0-9]","",
                  "".join(c for c in text if not unicodedata.combining(c)).casefold())

def scheduled_events(response):
    """Parse documented V2 scheduled/date response shapes; reject unknown."""
    if isinstance(response,list):
        return response
    if not isinstance(response,dict):
        raise ValueError("Invalid V2 schedule response")
    for key in ("events","matches","fixtures"):
        value=response.get(key)
        if isinstance(value,list):
            return value
    data=response.get("data")
    if isinstance(data,list):
        return data
    if isinstance(data,dict):
        return scheduled_events(data)
    raise ValueError("No recognized V2 scheduled-events array")

def name_for(event,side):
    value=event.get(side+"Team") or event.get(side+"Competitor") or event.get(side)
    return str((value.get("name") or value.get("displayName") or "") if isinstance(value,dict)
               else (value or "")).strip()

def kickoff_for(event):
    return utc_dt(event.get("startTimestamp") or event.get("startTime")
                  or event.get("start_time") or event.get("event_date"))

def provider_match_id(event):
    value=event.get("id",event.get("matchId",event.get("eventId")))
    identifier=str(value or "")
    return identifier if identifier.isdecimal() and len(identifier)<=18 else None

def score_for(event,side):
    score=event.get(side+"Score")
    if isinstance(score,dict):
        score=score.get("current",score.get("display"))
    if score is None:score=event.get(side+"_score")
    try:
        if score is None:return None
        if isinstance(score,bool):return None
        i=int(score)
        if float(score)!=i or not 0<=i<=10:return None
        return i
    except (TypeError,ValueError,OverflowError):
        return None

def match_candidates(v1,event,tolerance_seconds=5400):
    if not isinstance(event,dict):return False
    if normalise(name_for(event,"home"))!=normalise(v1.get("home_team")):
        return False
    if normalise(name_for(event,"away"))!=normalise(v1.get("away_team")):
        return False
    actual,kickoff=kickoff_for(event),utc_dt(v1.get("start_time"))
    if not actual or not kickoff or abs((actual-kickoff).total_seconds())>tolerance_seconds:
        return False
    # If the V2 schedule knows FT scores, require them to agree with V1.
    for side,field in (("home","home_score"),("away","away_score")):
        score=score_for(event,side)
        if score is not None and score!=int(v1[field]):
            return False
    return provider_match_id(event) is not None

def reconcile(v1,events):
    """Unique verified match ID or reason; never infer score-based IDs."""
    good=[event for event in events if match_candidates(v1,event)]
    ids={provider_match_id(event) for event in good}
    if not ids:return None,"fixture_not_matched"
    if len(ids)!=1 or len(good)!=1:
        return None,"ambiguous_fixture"
    return next(iter(ids)),None

def daily_schedule(client,day,*,schedule_by_date=None):
    key=str(day)
    if schedule_by_date is not None and key in schedule_by_date:
        return schedule_by_date[key]
    # Documented V2 /api/scheduled?date=YYYY-MM-DD endpoint.
    response=client.get("/scheduled?date="+key)
    if response is None:
        raise ValueError("No V2 schedule for "+key)
    events=scheduled_events(response)
    if not all(isinstance(event,dict) for event in events):
        raise ValueError("Malformed scheduled-events list")
    if schedule_by_date is not None:schedule_by_date[key]=events
    return events
