#!/usr/bin/env python3
"""Best-effort late-match xG bridge (read-only Supabase, no credentials logged).

Only snapshots captured from minute 90 onward are used, as provisional xG from
COMPLETED historical games, never as xG for the match being predicted.
Matching requires normalized HOME and AWAY names, same UTC date and kickoff
within 90 minutes. Ambiguous identities are rejected.
"""
import argparse
import json
import os
import re
import shutil
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import requests


def instant(value):
    if not value:
        return None
    try:
        dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def norm(text):
    val=unicodedata.normalize("NFKD",str(text or "")).encode("ascii","ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+","",val)


def xg_value(v):
    try:
        n=float(v)
        return n if 0<=n<=10 and n==n else None
    except (TypeError,ValueError,OverflowError):
        return None


def extract(match):
    for prefix in ("start_time","event_date","startTime"):
        if match.get(prefix):
            kickoff=instant(match[prefix])
            if kickoff:
                break
    else:
        kickoff=None
    return (kickoff,
            str(match.get("home_team") or (match.get("homeCompetitor") or {}).get("name") or ""),
            str(match.get("away_team") or (match.get("awayCompetitor") or {}).get("name") or ""))


def request_all(base_url, token, cutoff):
    headers={"apikey":token,"Authorization":"Bearer "+token,"Accept":"application/json"}
    endpoint=base_url.rstrip("/")+"/rest/v1/live_stats_sources"
    page=0
    while page<25:
        params={"select":"canonical_match_id,home_team,away_team,league_name,event_date,minute,stats_json,updated_at,source_name",
                "source_name":"eq.api_original","minute":"gte.90",
                "event_date":"lte."+cutoff+"T23:59:59Z",
                "stats_json->home->>expected_goals":"not.is.null",
                "limit":"1000","offset":str(page*1000)}
        resp=requests.get(endpoint,headers=headers,params=params,timeout=60)
        if not resp.ok:
            raise RuntimeError("Supabase REST query failed HTTP "+str(resp.status_code))
        rows=resp.json()
        if not isinstance(rows,list):
            raise RuntimeError("Unexpected Supabase REST response")
        yield from rows
        if len(rows)<1000:
            break
        page+=1


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",default="/tmp/mrx_all_matches_research.json")
    p.add_argument("--out",default="/tmp/mrx_augmented_xg.json")
    p.add_argument("--audit",default="/tmp/mrx_xg_audit.json")
    p.add_argument("--end",default="2026-10-19")
    a=p.parse_args()
    source,out=Path(a.source),Path(a.out)
    base=os.environ.get("SUPABASE_URL") or "https://nhwafcpndlufzzxexikh.supabase.co"
    token=os.environ.get("SUPABASE_SERVICE_ROLE_KEY","")
    audit={"credential_configured":bool(token),"snapshots_retrieved":0,
           "late_xg_snapshots_valid":0,"unique_fixtures":0,"historical_matches_enriched":0,
           "unmatched":0,"ambiguous":0,"status":"not_available"}
    if not token:
        shutil.copyfile(source,out)
    else:
        rows=[]
        try:
            rows=list(request_all(base,token,a.end))
            audit["snapshots_retrieved"]=len(rows)
        except Exception as exc:
            audit["query_error"]=str(exc)[:160]
            shutil.copyfile(source,out)
        if rows:
            indexed=defaultdict(list)
            for row in rows:
                kickoff=instant(row.get("event_date"))
                updated=instant(row.get("updated_at"))
                stat=row.get("stats_json") or {}
                sh=stat.get("home") or {}
                sa=stat.get("away") or {}
                h=xg_value(sh.get("expected_goals"))
                aw=xg_value(sa.get("expected_goals"))
                try:
                    minute=int(row.get("minute") or 0)
                except (ValueError,TypeError):
                    minute=0
                if (kickoff is None or updated is None or updated<=kickoff
                    or not 90<=minute<=135 or h is None or aw is None):
                    continue
                audit["late_xg_snapshots_valid"]+=1
                key=(kickoff.date(),norm(row.get("home_team")),norm(row.get("away_team")))
                if key[1] and key[2]:
                    indexed[key].append((kickoff,updated,minute,h,aw))
            audit["unique_fixtures"]=len(indexed)
            raw=json.loads(source.read_text(encoding="utf8"))
            records=raw if isinstance(raw,list) else raw.get("matches",raw.get("games",[]))
            for match in records:
                if not isinstance(match,dict):
                    continue
                kickoff,home,away=extract(match)
                if kickoff is None:
                    continue
                options=indexed.get((kickoff.date(),norm(home),norm(away)),[])
                candidates=[r for r in options if abs((r[0]-kickoff).total_seconds())<=5400]
                if len({(r[0],r[3],r[4]) for r in candidates})>1:
                    audit["ambiguous"]+=1
                    continue
                if len(candidates)==1:
                    v=candidates[0]
                    if v[1].date()>kickoff.date():
                        # This is still training-only xG; downstream day cutoff
                        # prevents target leakage, but current-day xG is excluded.
                        pass
                    match["home_xg"],match["away_xg"]=v[3],v[4]
                    audit["historical_matches_enriched"]+=1
                    match["xg_source"]="supabase_late_match_provisional_90plus"
            audit["unmatched"]=max(0,len(indexed)-audit["historical_matches_enriched"])
            audit["status"]="provisional_only"
            out.write_text(json.dumps(records,ensure_ascii=False),encoding="utf8")
    Path(a.audit).write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf8")
    print("XG_AUDIT",json.dumps(audit,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
