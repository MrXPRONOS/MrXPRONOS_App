#!/usr/bin/env python3
"""2024 researched football archive from BSD (complete pagination) + SportScore.

Internal use only. Files are AES-256-GCM, no API keys/data written in public Git.
OpenFootball CC0 archive remains untouched; deterministic identity dedup and
cross-provider disagreements are audited, NEVER converted to invented facts.

SportsScore daily fixture responses are capped at 200 and not documented as
paginated: never label them exhaustive at that cap.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from hashlib import sha256
from urllib.parse import urlencode
import calendar,json,os,re,time,unicodedata
import requests

from single_ml_v2_git import ROOT,seal,open_sealed,atomic_bytes,key_from_environment
from single_ml_v2_data import utc_dt

BSD="https://sports.bzzoiro.com/api/v2/events/"
SCORE="https://sportscore.com/api/v1/fixtures/"
SCHEMA="bsd_sportscore_2024_private_verified_v1"
BASE_DIR=ROOT/"bsd_sportscore"/"2024"
PER_PAGE=200
MAX_BSD_PAGES=100
SPORTSCORE_CAP=200
MAX_REQUESTS=1250
TIMEOUT=25

def norm(x):
    if not isinstance(x,str):return ""
    s=unicodedata.normalize("NFKD",x)
    return re.sub(r"[^a-z0-9]","",
        "".join(c for c in s if not unicodedata.combining(c)).casefold())

def goals(x):
    if x is None or isinstance(x,bool):return None
    try:
        v=int(x)
        return v if float(x)==v and 0<=v<=10 else None
    except (ValueError,TypeError,OverflowError):return None

def field_team(value):
    if isinstance(value,dict):
        return str(value.get("name") or value.get("short_name") or "").strip()
    return str(value or "").strip()

def ft_row(day,home,away,hs,aws,league,provider,identifier,*,kickoff=None):
    home,away,league=field_team(home),field_team(away),str(league or "").strip()
    hs,aws=goals(hs),goals(aws)
    if not home or not away or not league or norm(home)==norm(away) or hs is None or aws is None:
        return None
    if not identifier:return None
    item={"id":str(provider)+":"+str(identifier),"sportId":1,"date":str(day),
        "home_team":home,"away_team":away,"competition":league,
        "home_score":hs,"away_score":aws,"status_group":4,
        "is_finished":True,"source":provider,
        "source_date_precision":"calendar_date","source_year":day.year,
        "source_home_team_id":None,"source_away_team_id":None,
        "source_competition_id":None}
    if kickoff is not None:
        parsed=utc_dt(kickoff)
        if parsed is None or parsed.date()!=day:return None
        item["start_time"]=parsed.isoformat().replace("+00:00","Z")
        item["source_date_precision"]="utc_kickoff_verified"
    return item

def parse_bsd(event,day):
    if not isinstance(event,dict) or str(event.get("status","")).lower()!="finished":return None
    kickoff=event.get("event_date")
    parsed=utc_dt(kickoff)
    if parsed is None or parsed.date()!=day:return None
    home,away=event.get("home_team"),event.get("away_team")
    league=event.get("league_name") or event.get("competition_name") or event.get("league_id")
    m=ft_row(day,home,away,event.get("home_score"),event.get("away_score"),
             league,"bsd_v2_"+str(day.year),event.get("id"),kickoff=kickoff)
    if m:
        m["source_home_team_id"]=event.get("home_team_id")
        m["source_away_team_id"]=event.get("away_team_id")
        m["source_competition_id"]=event.get("league_id")
    return m

def parse_sportscore(event,day):
    if not isinstance(event,dict) or str(event.get("status","")).lower() not in ("finished","ft","ended"):
        return None
    when=event.get("time") or event.get("date")
    parsed=utc_dt(when)
    if parsed is None or parsed.date()!=day:return None
    home=event.get("home");away=event.get("away")
    league=event.get("competition") or event.get("league")
    # SportScore's reference does not promise numeric provider fixture ids.
    url=event.get("url") or event.get("slug")
    identity=url if isinstance(url,str) and url.startswith("/") else (
        url if isinstance(url,str) and "://" not in url else None)
    if not identity:
        identity=sha256((str(day)+"|"+str(home)+"|"+str(away)+"|"+str(league)).encode()).hexdigest()[:24]
    return ft_row(day,home,away,event.get("home_score"),event.get("away_score"),
                  league,"sportscore_"+str(day.year),sha256(str(identity).encode()).hexdigest()[:24],
                  kickoff=when)

def identity(row):
    return (str(row["date"]),norm(row["home_team"]),norm(row["away_team"]))

def http_json(session,url,headers,params,counter,*,sleep=.12):
    if counter["total"]>=MAX_REQUESTS:raise RuntimeError("Hard HTTP request cap reached")
    counter["total"]+=1
    response=session.get(url,params=params,headers=headers,timeout=TIMEOUT,allow_redirects=False)
    if response.status_code!=200:
        raise RuntimeError("Provider HTTP "+str(response.status_code))
    if len(response.content)>8*1024*1024:raise RuntimeError("Oversized provider response")
    result=response.json()
    time.sleep(sleep)
    return result

def bsd_month(session,month,token,counter,*,year=2024):
    start=date(year,month,1);end=date(year,month,calendar.monthrange(year,month)[1])
    rows={};total=None;pages=0
    while True:
        if pages>=MAX_BSD_PAGES:raise RuntimeError("BSD pagination incomplete")
        payload=http_json(session,BSD,{"Authorization":"Token "+token,
               "Accept":"application/json"},
               {"date_from":str(start),"date_to":str(end),"status":"finished",
                "limit":PER_PAGE,"offset":pages*PER_PAGE},counter)
        if not isinstance(payload,dict) or not isinstance(payload.get("results"),list) or type(payload.get("count")) is not int:
            raise RuntimeError("BSD unexpected pagination schema")
        if total is None:total=payload["count"]
        if payload["count"]!=total:raise RuntimeError("BSD count changed mid pagination")
        part=payload["results"]
        for raw in part:
            if not isinstance(raw,dict) or raw.get("id") is None:
                raise RuntimeError("BSD invalid fixture row")
            ident=str(raw["id"])
            if ident in rows and rows[ident]!=raw:raise RuntimeError("BSD provider ID changed within page group")
            rows[ident]=raw
        pages+=1
        if len(rows)>=total:break
        if not part or len(part)<PER_PAGE:
            raise RuntimeError("BSD pagination truncated (expected "+str(total)+")")
    accepted={}
    rejected=0
    for event in rows.values():
        dt=utc_dt(event.get("event_date"))
        if not dt or dt.year!=year or dt.month!=month:
            rejected+=1;continue
        m=parse_bsd(event,dt.date())
        if m is None:rejected+=1;continue
        accepted[m["id"]]=m
    return list(accepted.values()),{"reported":total,"pages":pages,"parsed":len(accepted),"rejected":rejected}

def score_month(session,month,counter,*,year=2024):
    validated={};days=[];truncated=0;failures=[]
    for daynum in range(1,calendar.monthrange(year,month)[1]+1):
        day=date(year,month,daynum)
        try:
            payload=http_json(session,SCORE,{"Accept":"application/json"},
                  {"sport":"football","date":str(day),"status":"finished",
                   "limit":SPORTSCORE_CAP},counter)
            if not isinstance(payload,dict) or not isinstance(payload.get("matches"),list):
                raise RuntimeError("SportScore unexpected match schema")
            raw=payload["matches"]
            if len(raw)>=SPORTSCORE_CAP or (type(payload.get("count")) is int and payload["count"]>=SPORTSCORE_CAP):
                truncated+=1
            days.append(str(day))
            for event in raw:
                m=parse_sportscore(event,day)
                if m is None:continue
                if m["id"] in validated and validated[m["id"]]!=m:
                    raise RuntimeError("SportScore duplicate source ID conflict")
                validated[m["id"]]=m
        except (requests.RequestException,ValueError,RuntimeError) as exc:
            failures.append({"date":str(day),"reason":type(exc).__name__})
            if isinstance(exc,RuntimeError) and "request cap" in str(exc):raise
    return list(validated.values()),{
        "days_queried":len(days),"days_failed":len(failures),
        "failed_dates":failures,"days_at_200_cap_incomplete":truncated,
        "parsed":len(validated),"not_complete_if_at_cap":True}

def merge_with_openfootball(bsd_rows,score_rows,of_rows):
    """Separate source identities, exact-date+team dedup, quarantine score conflicts."""
    index=defaultdict(list)
    for row in of_rows:
        if not isinstance(row,dict):continue
        key=identity(row)
        index[key].append(row)
    united={}
    duplicate_of=0
    score_conflicts=0
    for row in bsd_rows:
        key=identity(row)
        matches=index.get(key,[])
        if len(matches)==1:
            if (matches[0]["home_score"],matches[0]["away_score"])==(row["home_score"],row["away_score"]):
                duplicate_of+=1
            else:score_conflicts+=1
        elif len(matches)>1:score_conflicts+=1
        united[key]=row
    source_confirm=0
    score_new=0
    score_conflict=0
    within_bsd=0
    bykey=defaultdict(list)
    for row in score_rows:bykey[identity(row)].append(row)
    for key,rows in bykey.items():
        if len(rows)!=1:score_conflict+=len(rows);continue
        row=rows[0]
        present=united.get(key)
        if present:
            if (present["home_score"],present["away_score"])==(row["home_score"],row["away_score"]):
                source_confirm+=1
            else:score_conflict+=1
            continue
        original=index.get(key,[])
        if len(original)==1:
            if (original[0]["home_score"],original[0]["away_score"])==(row["home_score"],row["away_score"]):
                within_bsd+=1
            else:score_conflict+=1
            continue
        if len(original)>1:score_conflict+=1;continue
        united[key]=row
        score_new+=1
    return sorted(united.values(),key=lambda r:(r["date"],r["id"])),{
       "bsd_already_openfootball_exact":duplicate_of,
       "bsd_openfootball_score_conflicts":score_conflicts,
       "sportscore_confirmed_bsd":source_confirm,
       "sportscore_already_openfootball_exact":within_bsd,
       "sportscore_conflicts_or_ambiguous":score_conflict,
       "sportscore_new_vs_bsd_and_openfootball":score_new,
       "union_source_matches_not_equivalent_world_coverage":len(united)}

def month_file(month):return BASE_DIR/f"{month:02d}.enc"

def collect(*,root=ROOT,budget=MAX_REQUESTS,year=2024):
    if year not in (2024,2025):raise ValueError("Supported years are 2024 and 2025")
    if not os.getenv("BSD_API_KEY"):
        raise RuntimeError("BSD_API_KEY missing")
    key=key_from_environment()
    root=Path(root)
    with requests.Session() as session:
        of_by_month=defaultdict(list)
        if year==2024:
            original=open_sealed((root/"openfootball/2024.enc").read_bytes(),key,
                                 "openfootball-cc0-calendar-2024")
            if original.get("year")!=2024:
                raise RuntimeError("Original OpenFootball annual archive missing")
            for row in original["matches"]:
                of_by_month[int(row["date"][5:7])].append(row)
        else:
            original={"matches":[]}
        metrics=Counter()
        failures=[]
        print("OPENFOOTBALL_REFERENCE_YEAR",year,"COUNT",len(original["matches"]),flush=True)
        for month in range(1,13):
            path=root/"bsd_sportscore"/str(year)/f"{month:02d}.enc"
            if path.exists():
                cached=open_sealed(path.read_bytes(),key,
                                   "bsd-sportscore-"+str(year)+"-month:"+str(month))
                if cached.get("schema")!=f"bsd_sportscore_{year}_private_verified_v1" or cached.get("month")!=month or cached.get("year")!=year:
                    raise RuntimeError("Bad existing encrypted monthly snapshot")
                metrics["months_already_saved"]+=1
                continue
            try:
                bsd,ba=bsd_month(session,month,os.environ["BSD_API_KEY"],metrics,year=year)
                sc,sa=score_month(session,month,metrics,year=year)
                merged,comparison=merge_with_openfootball(bsd,sc,of_by_month[month])
                report={"bsd":ba,"sportscore":sa,"comparison":comparison,
                        "new_data_scope":"BSD finished + SportScore verified unique; NOT every world match",
                        "sportscore_not_exhaustive_if_200":True,
                        "source_license":"BSD internal R&D; SportScore API attribution required on public displays"}
                envelope={"schema":f"bsd_sportscore_{year}_private_verified_v1","month":month,"year":year,
                    "created_at":datetime.now(timezone.utc).isoformat(),
                    "audit":report,"matches":merged}
                payload=seal(envelope,key,"bsd-sportscore-2024-month:"+str(month))
                atomic_bytes(path,payload)
                verified=open_sealed(path.read_bytes(),key,
                        "bsd-sportscore-2024-month:"+str(month))
                if verified["audit"]!=report:raise RuntimeError("Encryption integrity mismatch")
                metrics["months_saved"]+=1
                metrics["bsd_new_matches"]+=len(bsd)
                metrics["sportscore_new_vs_bsd_and_openfootball"]+=comparison["sportscore_new_vs_bsd_and_openfootball"]
                print("ENCRYPTED_BSD_SPORTSCORE_MONTH",month,"BSD",len(bsd),
                      "SPORTSCORE",len(sc),"NEW_SPORTSCORE",comparison["sportscore_new_vs_bsd_and_openfootball"],
                      "AT_CAP",sa["days_at_200_cap_incomplete"],"HTTP",metrics["total"],flush=True)
                if sa["days_failed"]:
                    print("SPORTSCORE_MONTH_PARTIALLY_VERIFIED",month,sa["days_failed"],flush=True)
            except Exception as exc:
                failures.append({"month":month,"error":type(exc).__name__+":"+str(exc)[:90]})
                print("BSD_SPORTSCORE_MONTH_FAILED",month,type(exc).__name__,flush=True)
                break
    status={"year":year,"months_newly_saved":metrics["months_saved"],
        "months_already_saved":metrics["months_already_saved"],
        "months_remaining":12-metrics["months_saved"]-metrics["months_already_saved"],
        "bsd_matches_this_run":metrics["bsd_new_matches"],
        "sportscore_extra_this_run":metrics["sportscore_new_vs_bsd_and_openfootball"],
        "provider_http_requests":metrics["total"],"failures":failures}
    print("BSD_SPORTSCORE_YEAR_STATUS",json.dumps(status),flush=True)
    return status

if __name__=="__main__":
    import argparse
    cli=argparse.ArgumentParser()
    cli.add_argument("--year",type=int,default=2024,choices=(2024,2025))
    args=cli.parse_args()
    status=collect(year=args.year)
    if status["months_remaining"] or status["failures"]:
        raise SystemExit(2)
