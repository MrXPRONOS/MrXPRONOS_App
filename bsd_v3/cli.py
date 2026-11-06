"""BSD V3 free-data CLI. Only writes within its own artifacts directory."""
from __future__ import annotations
import argparse
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from .engine import run_shadow
from .evaluation import retrospective
from .policy import V3Policy,utc_datetime


def atomic_json(path,payload):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    root=(Path.cwd()/"bsd_v3"/"artifacts").resolve()
    if root not in path.resolve().parents:
        raise ValueError("BSD V3 may write only within bsd_v3/artifacts/")
    tmp=path.with_name(path.name+".tmp")
    try:
        tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.exists(): tmp.unlink()

def main(argv=None):
    ap=argparse.ArgumentParser(description="BSD V3 isolated experimental engine")
    ap.add_argument("--mode",choices=["shadow","evaluate"],default="shadow")
    ap.add_argument("--history",default="bsd/all_matches_bsd.json")
    ap.add_argument("--days",type=int,default=1)
    ap.add_argument("--max-odds-events",type=int,default=15)
    ap.add_argument("--max-requests",type=int,default=90)
    ap.add_argument("--bookmaker",default="consensus")
    ap.add_argument("--challengers",action="store_true")
    ap.add_argument("--output",default="bsd_v3/artifacts/latest_shadow.json")
    args=ap.parse_args(argv)
    if not 1<=args.days<=3 or not 0<=args.max_odds_events<=100 or not 1<=args.max_requests<=300:
        ap.error("Invalid bounds")
    from bsd_archive import _read_json
    history=_read_json(Path(args.history),None)
    if not isinstance(history,list) or not history:
        ap.error("Missing restored BSD historical matches")
    if args.mode=="evaluate":
        report=retrospective(history)
        atomic_json(args.output,report)
        print("BSD_V3_EVALUATION",json.dumps({"analyzed":report["analyzed"],
                                               "calibration":report["v3_calibration"]}))
        return 0
    from bsd_api import BSDClient
    from bsd_v2_odds import fetch_event_odds
    now=datetime.now(timezone.utc)
    policy=V3Policy(max_api_requests=args.max_requests,max_odds_events=args.max_odds_events)
    client=BSDClient(max_requests=policy.max_api_requests)
    fixtures=[]
    for offset in range(args.days):
        day=(now+timedelta(days=offset)).date()
        page=client.list_events(day,day,max_pages=10,ttl=0)
        if not page.complete: raise RuntimeError("Incomplete free BSD fixtures: "+str(day))
        fixtures.extend(page.events)
    def fetcher(event,captured):
        return fetch_event_odds(client,int(event["id"]),
                                kickoff=utc_datetime(event["event_date"]),
                                captured_at=captured,bookmaker_slug=args.bookmaker,max_age_hours=2)
    result=run_shadow(fixtures,history,now=now,
                      quote_fetcher=fetcher if policy.max_odds_events else None,
                      policy=policy,enable_challengers=args.challengers)
    result["diagnostics"]["bsd_api_http_calls"]=client.requests_made
    result["diagnostics"]["bsd_api_cache_hits"]=client.cache_hits
    atomic_json(args.output,result)
    from .registry import record_snapshot
    result["diagnostics"]["immutable_records_created"]=record_snapshot(result)
    print("BSD_V3_SHADOW",json.dumps({"fixtures":len(fixtures),
                                     "analyzed":result["diagnostics"]["analyzed"],
                                     "http_calls":client.requests_made,
                                     "no_publication":True,
                                     "fingerprint":result["fingerprint_sha256"]}))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
