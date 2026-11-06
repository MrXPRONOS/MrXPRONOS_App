"""BSD V3 free-data CLI. No website, Telegram or BSD V2 publication writer."""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from .engine import run_shadow
from .evaluation import retrospective
from .policy import V3Policy,utc_datetime

ARTIFACT_ROOT=Path("bsd_v3/artifacts")

def allowed_artifact(path):
    path=Path(path)
    root=(Path.cwd()/ARTIFACT_ROOT).resolve()
    if root not in path.resolve().parents:
        raise ValueError("BSD V3 writes only within bsd_v3/artifacts/")
    return path

def atomic_json(path,payload):
    path=allowed_artifact(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+".tmp")
    try:
        tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()

def settle_existing_registry(history, *, now, client, registry_path, max_days=7):
    """Find final events in existing BSD history, then query recent missing days."""
    from .registry import verify_registry
    from .settlement import settle_registry,performance_report
    registry=allowed_artifact(registry_path)
    entries=verify_registry(registry)
    if not entries:
        return {"new_settlements":0,"status":"no_prior_records","report":{}}
    completed={row["id"] for row in entries if row["type"]=="settlement"}
    pending=[r for r in entries if r["type"]=="forecast" and r["id"] not in completed]
    by_id={str(item["id"]):item for item in history
           if isinstance(item,dict) and item.get("id") is not None and
           str(item.get("status") or "").lower()=="finished"}
    missing_days=set()
    for entry in pending:
        event_id=entry["payload"]["event_id"]
        if event_id in by_id:
            continue
        kickoff=utc_datetime(entry["payload"]["kickoff_utc"])
        if kickoff+timedelta(hours=4)>now:
            continue
        if (now-kickoff).days<=max_days:
            missing_days.add(kickoff.date())
    api_days=0
    for day in sorted(missing_days)[:max_days]:
        page=client.list_events(day,day,max_pages=10,ttl=0)
        if not page.complete:
            raise RuntimeError("Incomplete BSD final scores; settlement aborted")
        api_days+=1
        for item in page.events:
            if (isinstance(item,dict) and item.get("id") is not None and
                    str(item.get("status") or "").lower()=="finished"):
                by_id[str(item["id"])]=item
    new=settle_registry(registry,by_id.values(),now=now)
    return {**new,"status":"settlement_complete",
            "pending_forecasts":len(pending),"api_days":api_days,
            "report":performance_report(registry)}

def main(argv=None):
    ap=argparse.ArgumentParser(description="BSD V3 FREE isolated experimental engine")
    ap.add_argument("--mode",choices=["shadow","evaluate","settle"],default="shadow")
    ap.add_argument("--history",default="bsd/all_matches_bsd.json")
    ap.add_argument("--days",type=int,default=1)
    ap.add_argument("--max-odds-events",type=int,default=15)
    ap.add_argument("--max-requests",type=int,default=90)
    ap.add_argument("--bookmaker",default="consensus")
    ap.add_argument("--free-public-board",action="store_true",
                    help="Optional one-call free sportsbook quote board (no key)")
    ap.add_argument("--challengers",action="store_true",
                    help="Train and gate existing 2024-trained specialists in 2025")
    ap.add_argument("--registry",default="bsd_v3/artifacts/prediction_log.jsonl")
    ap.add_argument("--output",default="bsd_v3/artifacts/latest_shadow.json")
    args=ap.parse_args(argv)
    if not 1<=args.days<=3 or not 0<=args.max_odds_events<=100 or not 1<=args.max_requests<=300:
        ap.error("Invalid free-request bounds")
    allowed_artifact(args.output)
    allowed_artifact(args.registry)
    from bsd_archive import _read_json
    history=_read_json(Path(args.history),None)
    if not isinstance(history,list) or not history:
        ap.error("Existing encrypted BSD history must be restored first")
    now=datetime.now(timezone.utc)
    if args.mode=="evaluate":
        report=retrospective(history)
        atomic_json(args.output,report)
        print("BSD_V3_EVALUATION",json.dumps({"analyzed":report["analyzed"],
                                              "calibration":report["v3_calibration"]}))
        return 0
    from bsd_api import BSDClient
    policy=V3Policy(max_api_requests=args.max_requests,
                    max_odds_events=args.max_odds_events)
    client=BSDClient(max_requests=policy.max_api_requests)
    if args.mode=="settle":
        result=settle_existing_registry(history,now=now,client=client,
                                        registry_path=args.registry)
        result["bsd_http_requests"]=client.requests_made
        atomic_json(args.output,result)
        print("BSD_V3_SETTLEMENT",json.dumps({"new":result["new_settlements"],
                                              "http_calls":client.requests_made}))
        return 0
    from .free_odds import FreeMultiMarketOdds
    fixtures=[]
    for offset in range(args.days):
        day=(now+timedelta(days=offset)).date()
        page=client.list_events(day,day,max_pages=10,ttl=0)
        if not page.complete:
            raise RuntimeError("Incomplete free BSD fixtures: "+str(day))
        fixtures.extend(page.events)
    quote_router=FreeMultiMarketOdds(client,bookmaker_slug=args.bookmaker,
                                     enable_public_board=args.free_public_board,
                                     policy=policy)
    result=run_shadow(fixtures,history,now=now,
                      quote_fetcher=quote_router if policy.max_odds_events else None,
                      policy=policy,enable_challengers=args.challengers)
    result["diagnostics"]["bsd_api_http_calls"]=client.requests_made
    result["diagnostics"]["bsd_api_cache_hits"]=client.cache_hits
    result["diagnostics"]["quote_router"]=quote_router.stats
    fingerprint_body={key:value for key,value in result.items()
                      if key!="fingerprint_sha256"}
    result["fingerprint_sha256"]=hashlib.sha256(
        json.dumps(fingerprint_body,sort_keys=True,separators=(",",":"),
                   ensure_ascii=False).encode("utf-8")).hexdigest()
    atomic_json(args.output,result)
    from .registry import record_snapshot
    records_created=record_snapshot(result,path=args.registry)
    print("BSD_V3_SHADOW",json.dumps({"fixtures_received":len(fixtures),
                                     "analyzed":result["diagnostics"]["analyzed"],
                                     "http_calls":client.requests_made,
                                     "no_publication":True,
                                     "records_created":records_created,
                                     "fingerprint":result["fingerprint_sha256"]}))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
