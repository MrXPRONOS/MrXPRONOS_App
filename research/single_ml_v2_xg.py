#!/usr/bin/env python3
"""Source-verified real historical xG, encrypted in public GitHub.

No Supabase or Neon. SportsAPIPro V2 match statistics are accepted only for
a football fixture whose independent provider match detail matches the
certified V1 football archive by ID, both team names and kickoff UTC.
Unknown schemas, missing values, ambiguous periods, unsupported competition
or API errors are NOT replaced by fabricated values.

CRITICAL: Historical xG fetched today is available to our model from the
actual first-observed timestamp TODAY, not retroactively from kickoff.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import re
import sys
import time
import unicodedata
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from single_ml_v2_data import utc_dt
from single_ml_v2_git import (ROOT, atomic_bytes, key_from_environment, load_days,
                              open_sealed, seal)
from sportdata_api import get_api_keys
from single_ml_v2_xg_resolve import daily_schedule, reconcile, provider_match_id, match_candidates

PROVIDER = "sportsapipro_v2_match_statistics"
QUALITY = "measured_postmatch_provider"
BASE_URL = "https://api.sportsapipro.com/v2/football/api"
SAFE_ID = re.compile(r"^[0-9]{1,18}$")
SUPPORTED_LABELS = frozenset(("expectedgoals","xg","expectedgoal"))
TIMEOUT = 24


def utc_now():
    return datetime.now(timezone.utc)


def normalized_name(s):
    text=unicodedata.normalize("NFKD",str(s or ""))
    text="".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+","",text.casefold())


def xg_number(value):
    if isinstance(value,bool) or value is None:
        return None
    try:
        n=float(value)
    except (ValueError,TypeError,OverflowError):
        return None
    return n if math.isfinite(n) and 0.0<=n<=10.0 else None


def one_event(obj):
    if not isinstance(obj,dict):
        return None
    for candidate in (obj.get("event"),obj.get("match"),obj.get("game"),obj.get("data")):
        if isinstance(candidate,dict):
            if "homeTeam" in candidate or "homeCompetitor" in candidate:
                return candidate
            nested=one_event(candidate)
            if nested is not None:return nested
    if "homeTeam" in obj or "homeCompetitor" in obj:
        return obj
    return None


def get_team_name(event, side):
    obj=event.get(side+"Team") or event.get(side+"Competitor")
    if isinstance(obj,dict):
        return str(obj.get("name") or "").strip()
    return str(obj or "").strip()


def require_matching_identity(event, match):
    """Never assume V1 and V2 numeric identifiers share their namespace."""
    if not isinstance(event,dict):
        raise ValueError("Provider response has no verifiable match identity")
    provider_id=event.get("id",event.get("matchId",event.get("eventId")))
    if str(provider_id or "") != str(match["id"]):
        raise ValueError("V1/V2 match ID mismatch")
    if normalized_name(get_team_name(event,"home"))!=normalized_name(match["home_team"]):
        raise ValueError("Home club mismatch")
    if normalized_name(get_team_name(event,"away"))!=normalized_name(match["away_team"]):
        raise ValueError("Away club mismatch")
    start=(event.get("startTimestamp") or event.get("startTime")
           or event.get("start_time") or event.get("event_date"))
    actual=utc_dt(start)
    expected=utc_dt(match["start_time"])
    if not actual or not expected or abs((actual-expected).total_seconds())>5400:
        raise ValueError("Kickoff difference >90 minutes or timezone unverified")
    if str(match.get("sportId"))!="1" or match.get("is_finished") is not True:
        raise ValueError("Not certified historical football")
    return True


def as_pair(group):
    if not isinstance(group,dict):
        return None
    home=xg_number(group.get("home"))
    away=xg_number(group.get("away"))
    return (home,away) if home is not None and away is not None else None


def _direct_candidates(obj):
    """Accept explicit match totals only; generic stats and shot counts are NOT xG."""
    if not isinstance(obj,dict):return []
    pairs=[]
    for name in ("expectedGoals","expected_goals","xG","xg"):
        x=obj.get(name)
        pair=as_pair(x)
        if pair is not None:pairs.append(pair)
    for home_key,away_key in (
        ("homeExpectedGoals","awayExpectedGoals"),
        ("home_xg","away_xg"),
        ("expectedGoalsHome","expectedGoalsAway"),
    ):
        if home_key in obj and away_key in obj:
            pair=(xg_number(obj[home_key]),xg_number(obj[away_key]))
            if pair[0] is not None and pair[1] is not None:pairs.append(pair)
    return pairs


def _stat_items(container):
    if isinstance(container,list):
        yield from container
    elif isinstance(container,dict):
        for key in ("statisticsItems","statistics","items","groups"):
            if isinstance(container.get(key),list):
                yield from container[key]


def _is_full_period(text):
    t=normalized_name(text)
    return t in ("all","overall","fulltime","fullmatch","ft","total","match")


def extract_xg(stats):
    """Return (xg_home,xg_away) or None: no 1H/live/shotmaps assumed to be totals.

    Supported schemas: object-level paired expectedGoals, explicit ALL/FT
    group with expected goals items. Contradictory values -> reject.
    """
    if not isinstance(stats,dict):return None
    block=stats.get("data") if isinstance(stats.get("data"),dict) else stats
    candidates=_direct_candidates(block)
    if block is not stats:
        candidates.extend(_direct_candidates(stats))
    for section in ("statistics","periods"):
        container=block.get(section) if isinstance(block,dict) else None
        if not isinstance(container,(dict,list)):continue
        # Some providers return {"statistics": {"expectedGoals": {"home": ...}}}
        candidates.extend(_direct_candidates(container))
        nodes=container if isinstance(container,list) else [container]
        for node in nodes:
            if not isinstance(node,dict):continue
            period=node.get("period",node.get("periodName",node.get("name")))
            if not _is_full_period(period):continue
            candidates.extend(_direct_candidates(node))
            for item in _stat_items(node):
                if not isinstance(item,dict):continue
                group_name=str(item.get("name") or item.get("key") or item.get("title") or "")
                if normalized_name(group_name) in SUPPORTED_LABELS:
                    pair=as_pair(item)
                    if pair is not None:candidates.append(pair)
                for child in _stat_items(item):
                    if not isinstance(child,dict):continue
                    label=child.get("name") or child.get("key") or ""
                    if normalized_name(label) in SUPPORTED_LABELS:
                        pair=as_pair(child)
                        if pair is not None:candidates.append(pair)
    if not candidates:return None
    baseline=candidates[0]
    # Fail closed if the source has inconsistent xG totals.
    if any(max(abs(a-baseline[0]),abs(b-baseline[1]))>.02 for a,b in candidates):
        raise ValueError("Conflicting expected-goals values")
    return baseline


class QuotaExceeded(RuntimeError):
    pass


class MatchStatsClient:
    def __init__(self, keys, *,request_limit,session=None,base_url=BASE_URL):
        self.keys=list(dict.fromkeys(k.strip() for k in keys if k and k.strip()))
        if not self.keys:
            raise RuntimeError("No configured SportData API keys")
        if request_limit<1:
            raise ValueError("Request limit must be positive")
        self.limit=request_limit
        self.used=0
        self.session=session or requests.Session()
        self.base_url=base_url.rstrip("/")
        self.skipped_keys=set()

    def get(self, endpoint):
        if not (endpoint.startswith("/match/") or endpoint.startswith("/schedule/")):
            raise ValueError("Endpoint not allowlisted")
        last=None
        for i,key in enumerate(self.keys):
            if i in self.skipped_keys:continue
            if self.used>=self.limit:
                raise QuotaExceeded("Configured API request ceiling reached")
            self.used+=1
            try:
                resp=self.session.get(self.base_url+endpoint,
                    headers={"x-api-key":key,"Accept":"application/json"},timeout=TIMEOUT)
            except requests.RequestException:
                last="network_unavailable"
                continue
            if resp.status_code in (401,403,429):
                self.skipped_keys.add(i)
                last="api_key_restricted"
                continue
            if resp.status_code==404:
                return None
            if resp.status_code!=200:
                last="provider_http_"+str(resp.status_code)
                continue
            try:
                body=resp.json()
            except ValueError:
                last="invalid_json"
                continue
            if not isinstance(body,dict) or body.get("success") is False or body.get("error"):
                last="provider_error"
                continue
            return body
        raise QuotaExceeded("No provider request capacity remaining: "+str(last))


def record_path(match_id,key,root=ROOT):
    token=hmac.new(key,("xg:match:"+str(match_id)).encode("utf8"),hashlib.sha256).hexdigest()
    return Path(root)/"xg"/"matches"/token[:2]/(token+".enc")


def record_name(match_id):
    return "xg:match:"+str(match_id)


def record_from_file(match_id,key,root=ROOT):
    path=record_path(match_id,key,root)
    if not path.is_file():return None
    record=open_sealed(path.read_bytes(),key,record_name(match_id))
    if str(record.get("match_id"))!=str(match_id):
        raise ValueError("Encrypted xG record is for another match")
    return record


def write_record(record,key,root=ROOT):
    match_id=record["match_id"]
    path=record_path(match_id,key,root)
    old=record_from_file(match_id,key,root)
    if old is not None and old.get("status")=="measured":
        # A measured observation is immutable and its first-observed time
        # can never be rewritten or retroactively moved.
        return False
    ciphertext=seal(record,key,record_name(match_id))
    if old is None:
        atomic_bytes(path,ciphertext)
    else:
        # Recheck of an earlier negative/provider-unavailable observation.
        # This is an encrypted replacement; Git retains prior ciphertext.
        temporary=path.with_name(path.name+".tmp")
        try:
            with temporary.open("xb") as output:
                output.write(ciphertext)
            temporary.replace(path)
        finally:
            if temporary.exists():temporary.unlink()
    return True


def fetch_observation(client,match,*,now,schedule_cache=None):
    """Maximum 2 provider calls per match. Never infer missing identity."""
    ident=str(match.get("id") or "")
    # V1 ID is NOT reused as V2 ID. Resolve from independent V2 schedule.
    try:
        events=daily_schedule(client,match["start_time"][:10],schedule_by_date=schedule_cache)
    except (ValueError,QuotaExceeded):
        raise
    resolved,reason=reconcile(match,events)
    if resolved is None:
        return {"status":"identity_unverified","reason":reason}
    if not SAFE_ID.fullmatch(resolved):
        return {"status":"unsupported_match_id","reason":"invalid_v2_id"}
    statistics=client.get("/match/"+resolved+"/statistics")
    if statistics is None:
        return {"status":"not_available","reason":"stats_404"}
    measured=extract_xg(statistics)
    if measured is None:
        return {"status":"not_available","reason":"no_explicit_fulltime_xg"}
    event=one_event(statistics)
    if event is None:
        detail=client.get("/match/"+resolved)
        event=one_event(detail)
    if event is None:
        return {"status":"identity_unverified","reason":"match_detail_unavailable"}
    try:
        # Require V2 ID to agree with independently matched schedule.
        if str(event.get("id",event.get("matchId",event.get("eventId"))))!=resolved or not match_candidates(match,event):
            raise ValueError("V2 detail differs from independently matched schedule")
    except ValueError:
        return {"status":"identity_unverified","reason":"id_team_or_kickoff_mismatch"}
    return {
        "status":"measured","home_xg":measured[0],"away_xg":measured[1],
        "xg_source":PROVIDER,"xg_quality":QUALITY,
        # This is the time OUR model first knows this value. Never backdate.
        "xg_observed_at":now.isoformat(),
        "xg_usable_after":now.isoformat(),
        "provider_match_id":resolved,
    }


def collect(start,end,*,key,root=ROOT,limit=24,request_limit=35,client=None):
    if start>end or end>=utc_now().date():
        raise ValueError("End must be strictly before the current UTC day")
    matches,missing,_=load_days(start,end,key=key,root=root,allow_missing=True)
    stats=Counter()
    stats["certified_football_matches_seen"]=len(matches)
    stats["football_days_missing"]=len(missing)
    cli=client or MatchStatsClient(get_api_keys(),request_limit=request_limit)
    # Newest matches first for fresher ML coverage. Negative checkpoints
    # are retried only after their explicit cooldown has passed.
    schedule_cache={}
    for match in reversed(matches):
        mid=str(match["id"])
        old=record_from_file(mid,key,root)
        if old is not None and old.get("status")=="measured":
            stats["previously_measured"]+=1
            continue
        if old is not None:
            deadline=utc_dt(old.get("retry_after"))
            if deadline is not None and utc_now()<deadline:
                stats["cooldown_skipped"]+=1
                continue
        if stats["newly_checked"]>=limit:break
        try:
            value=fetch_observation(cli,match,now=utc_now(),schedule_cache=schedule_cache)
        except QuotaExceeded:
            stats["stopped_due_to_api_limit"]+=1
            break
        except (ValueError,requests.RequestException):
            stats["temporary_source_error"]+=1
            continue
        now=utc_now()
        record={
            "match_id":mid,"kickoff":match["start_time"],"home_team":match["home_team"],
            "away_team":match["away_team"],
            "checked_at":now.isoformat(),**value,
        }
        # Negative results are encrypted as temporary retryable checkpoints.
        # A missing xG is NEVER converted into synthetic measurements.
        if value["status"]!="measured":
            record["retry_after"]=(now+timedelta(days=14)).isoformat()
        stats["newly_checked"]+=1
        stats["outcome_"+value["status"]]+=1
        if write_record(record,key,root):
            stats["encrypted_checkpoint_written"]+=1
            if value["status"]=="measured":
                stats["persisted_measured"]+=1
    stats["requests_used"]=cli.used
    stats["request_limit"]=cli.limit
    return dict(stats)


def enrich_from_encrypted(matches,key,*,root=ROOT):
    """The verified historical football archive is the ONLY match source."""
    report=Counter()
    result=[]
    for source in matches:
        match=dict(source)
        # Strip unsigned xG fields from any input.
        for field in ("home_xg","away_xg","xg_source","xg_quality",
                      "xg_observed_at","xg_usable_after"):
            match.pop(field,None)
        if match.get("sportId")!=1 or match.get("is_finished") is not True:
            raise ValueError("xG enrichment received uncertified football source")
        record=record_from_file(match["id"],key,root)
        if record is not None and record.get("status")=="measured":
            if (record.get("xg_source")!=PROVIDER or record.get("xg_quality")!=QUALITY
                or record.get("kickoff")!=match.get("start_time")
                or normalized_name(record.get("home_team"))!=normalized_name(match["home_team"])
                or normalized_name(record.get("away_team"))!=normalized_name(match["away_team"])):
                raise ValueError("xG overlay does not match certified football match")
            h,a=xg_number(record.get("home_xg")),xg_number(record.get("away_xg"))
            recorded=utc_dt(record.get("xg_usable_after"))
            kickoff=utc_dt(match.get("start_time"))
            if h is None or a is None or recorded is None or kickoff is None or recorded<=kickoff:
                raise ValueError("xG record has invalid measured values or availability")
            match.update({
                "home_xg":h,"away_xg":a,"xg_source":PROVIDER,
                "xg_quality":QUALITY,"xg_usable_after":recorded.isoformat(),
                "xg_observed_at":recorded.isoformat(),
            })
            report["measured"]+=1
        else:
            report["missing"]+=1
        result.append(match)
    return result,dict(report)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("collect","audit"))
    p.add_argument("--start",default="2024-01-01")
    p.add_argument("--end",default=None)
    p.add_argument("--root",default=str(ROOT))
    p.add_argument("--limit",type=int,default=24)
    p.add_argument("--request-limit",type=int,default=35)
    a=p.parse_args()
    key=key_from_environment()
    end=date.fromisoformat(a.end) if a.end else utc_now().date()-timedelta(days=1)
    start=date.fromisoformat(a.start)
    if a.action=="collect":
        result=collect(start,end,key=key,root=a.root,
                       limit=a.limit,request_limit=a.request_limit)
        print("ENCRYPTED_GITHUB_REAL_XG",json.dumps(result,ensure_ascii=False))
        return 0
    matches,missing,_=load_days(start,end,key=key,root=a.root,allow_missing=True)
    enriched,status=enrich_from_encrypted(matches,key,root=a.root)
    print("ENCRYPTED_GITHUB_REAL_XG_AUDIT",json.dumps({
        **status,"football_days_missing":len(missing),
        "certified_matches":len(enriched)},ensure_ascii=False))
    return 0


if __name__=="__main__":
    sys.exit(main())
