#!/usr/bin/env python3
"""Règlement indépendant de snapshots V2 produits AVANT les matchs.

Télécharge les artefacts d'exécutions antérieures du workflow shadow,
vérifie empreintes, et confronte les sélections aux scores BSD actuels.
Ne fabrique jamais de résultat pour un match non terminé.
"""
from __future__ import annotations
import argparse, hashlib, io, json, os, zipfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
import requests
from bsd_api import BSDClient
from bsd_h2h import _utc, _valid_score
from bsd_markets import candidates_from_goals, realized
from bsd_backtest import wilson_interval


def verify_snapshot(s):
    if not isinstance(s,dict) or s.get("format")!="bsd-v2-shadow-v1" or not s.get("experimental") or s.get("published") is not False:
        raise ValueError("Snapshot BSD V2 non reconnu")
    digest=s.get("fingerprint_sha256")
    content={k:v for k,v in s.items() if k not in ("fingerprint_sha256","diagnostics")}
    # Le producteur ajoute diagnostics réseau après la signature; vérifier
    # exactement le contenu scellé à la génération, avant cet enrichissement.
    original={k:v for k,v in s.items() if k!="fingerprint_sha256"}
    if isinstance(original.get("diagnostics"),dict):
        original["diagnostics"]=dict(original["diagnostics"])
        for field in ("http_calls","rho","odds_bookmaker_requested","quality_validation"):
            original["diagnostics"].pop(field,None)
    recomputed=hashlib.sha256(json.dumps(original,sort_keys=True,ensure_ascii=False).encode("utf-8")).hexdigest()
    if digest!=recomputed:
        raise ValueError("Empreinte snapshot incorrecte")
    return _utc(s["generated_at_utc"])


def settle_snapshot(snapshot, results_by_id, *, now=None):
    created=verify_snapshot(snapshot)
    now=now or datetime.now(timezone.utc)
    report=Counter()
    markets=Counter()
    samples=[]
    for pred in snapshot["matches"]:
        report["total"]+=1
        match_id=str(pred.get("source_event_id"))
        event=results_by_id.get(match_id)
        if not isinstance(event,dict):
            report["missing_results"]+=1
            continue
        kickoff=_utc(str(pred.get("event_date") or ""))
        if not created<kickoff or not kickoff+timedelta(hours=4)<=now:
            report["not_safely_settleable"]+=1
            continue
        if str(event.get("status") or "").lower()!="finished":
            report["unfinished"]+=1
            continue
        hs,aw=_valid_score(event.get("home_score")),_valid_score(event.get("away_score"))
        if hs is None or aw is None:
            report["invalid_scores"]+=1
            continue
        if _utc(str(event.get("event_date") or ""))!=kickoff:
            report["kickoff_mismatch"]+=1
            continue
        market=pred["prediction"]
        key=market["key"]
        candidates={c.key:c for c in candidates_from_goals(1.3,1.1)}
        if key not in candidates:
            report["unrecognized_market"]+=1
            continue
        win=realized(candidates[key],hs,aw)
        report["settled"]+=1
        report["wins"]+=win
        markets[key]+=1
        samples.append({
            "event_id":match_id,"market":key,"won":bool(win),
            "probability":market["probability"],
            "bookmaker_odds":market.get("bookmaker_odds"),
            "generated_at":created.isoformat(),
        })
    n=report["settled"]
    return {
        "snapshot_created_at_utc":created.isoformat(),
        "total_predicted":report["total"],"settled":n,"wins":report["wins"],
        "hit_rate":round(report["wins"]/n,4) if n else None,
        "wilson_95":wilson_interval(report["wins"],n),
        "unsettled_reasons":{k:v for k,v in report.items() if k not in ("settled","wins","total")},
        "by_market_counts":dict(markets),"settled_predictions":samples,
        "warning":"Prospective hit-rate only; odds may be unavailable. No ROI claimed."
    }


def download_snapshots(owner_repo, token, *, min_age_hours=30,max_snapshots=8):
    if not token: raise ValueError("GITHUB_TOKEN requis")
    sess=requests.Session()
    sess.headers.update({"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
                         "X-GitHub-Api-Version":"2022-11-28"})
    root="https://api.github.com/repos/"+owner_repo
    runs=sess.get(root+"/actions/workflows/bsd-v2-shadow.yml/runs",params={"status":"success","per_page":50},timeout=30)
    runs.raise_for_status()
    found=[]
    cutoff=datetime.now(timezone.utc)-timedelta(hours=min_age_hours)
    for run in runs.json().get("workflow_runs",[]):
        try:
            stamp=_utc(run["created_at"])
        except (KeyError,TypeError,ValueError):
            continue
        if stamp>cutoff: continue
        aid=run["id"]
        listing=sess.get(root+"/actions/runs/%s/artifacts"%aid,timeout=30)
        listing.raise_for_status()
        artifact=next((a for a in listing.json().get("artifacts",[])
                       if a.get("name")=="bsd-v2-shadow-%s"%aid and not a.get("expired")),None)
        if artifact is None:continue
        blob=sess.get(artifact["archive_download_url"],timeout=45)
        blob.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(blob.content)) as z:
            if "v2_shadow_predictions.json" not in z.namelist():continue
            doc=json.loads(z.read("v2_shadow_predictions.json"))
            verify_snapshot(doc)
            found.append(doc)
        if len(found)>=max_snapshots:break
    return found


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",default="MrXPRONOS/MrXPRONOS_App")
    p.add_argument("--snapshot-file",default="")
    p.add_argument("--max-snapshots",type=int,default=8)
    p.add_argument("--output",default="bsd/v2_prospective_settlement.json")
    args=p.parse_args()
    if args.snapshot_file:
        snapshots=[json.loads(Path(args.snapshot_file).read_text(encoding="utf-8"))]
    else:
        snapshots=download_snapshots(args.repo,os.environ.get("GH_TOKEN",""),
                                     max_snapshots=args.max_snapshots)
    if not snapshots:
        print("BSD_V2_SETTLEMENT: no eligible past snapshots")
        return
    now=datetime.now(timezone.utc)
    days=sorted(set(_utc(p["event_date"]).date() for s in snapshots for p in s["matches"]
                    if _utc(p["event_date"])+timedelta(hours=4)<=now))
    client=BSDClient(max_requests=100)
    events={}
    for day in days:
        batch=client.list_events(day,day,max_pages=15,ttl=0)
        if not batch.complete:
            raise RuntimeError("Incomplete BSD results for "+str(day))
        for e in batch.events:
            if isinstance(e,dict) and e.get("id") is not None:
                events[str(e["id"])]=e
    reports=[settle_snapshot(s,events,now=now) for s in snapshots]
    total=sum(r["settled"] for r in reports)
    wins=sum(r["wins"] for r in reports)
    summary={"snapshots":len(reports),"settled":total,"wins":wins,
             "hit_rate":round(wins/total,4) if total else None,
             "wilson_95":wilson_interval(wins,total),"reports":reports,
             "source":"time-stamped prospective BSD V2 snapshots"}
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print("BSD_V2_SETTLEMENT:",json.dumps({k:v for k,v in summary.items() if k!="reports"}))


if __name__=="__main__":
    main()
