#!/usr/bin/env python3
"""Shadow BSD V2 : prévisions pré-match seules, jamais publiées.

Utilise les marchés buts/résultats et les cotes BSD disponibles *au moment*
de l'exécution; archive le signal horodaté comme artefact GitHub Actions.
Aucune réécriture de data.json, aucun Telegram, aucune prétention à un ROI historique.
"""
from __future__ import annotations
import argparse, json, hashlib
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bsd_archive import MATCHES_FILE, _read_json
from bsd_api import BSDClient
from bsd_v2_core import V2History, fit_rho_2024, predict_v2, fixture_datetime
from bsd_v2_policies import fit_policy
from bsd_v2_odds import fetch_event_odds


def generate_shadow(events, history, calibration, policy, rho, *, now, mode="reliability",
                    quote_fetcher=None, max_odds_events=20):
    index=V2History(history)
    output=[]
    skips=Counter()
    odds_queried=0
    for fixture in events:
        try:
            kickoff=fixture_datetime(fixture)
        except (TypeError, ValueError):
            skips["invalid_date"]+=1
            continue
        if not now < kickoff:
            skips["already_started"]+=1
            continue
        odds=None
        quote_metadata=None
        if quote_fetcher and odds_queried<max_odds_events and str(fixture.get("status","")).lower() in ("notstarted","upcoming"):
            try:
                quotes, quote_metadata=quote_fetcher(fixture,now)
                odds={code: row["odds"] for code,row in quotes.items()}
            except (ValueError,RuntimeError,KeyError) as exc:
                skips["odds_unavailable"]+=1
                quote_metadata={"error":type(exc).__name__}
            odds_queried+=1
        pred,reason=predict_v2(fixture,index,calibration=calibration,
                               quality_policy=policy,rho=rho,clock=now,
                               mode=mode,odds_by_market=odds)
        if pred is None:
            skips[reason]+=1
            continue
        if quote_metadata is not None:
            pred["odds_diagnostics"]=quote_metadata
        pred["prediction_generated_at"]=now.isoformat()
        output.append(pred)
    result={
        "format":"bsd-v2-shadow-v1","generated_at_utc":now.isoformat(),
        "mode":mode,"experimental":True,"published":False,
        "model":"bsd-v2-isolated","matches":output,
        "diagnostics":{"events_received":len(events),"selected":len(output),
                       "excluded":dict(skips),"odds_events_queried":odds_queried},
    }
    result["fingerprint_sha256"]=hashlib.sha256(
        json.dumps(result,sort_keys=True,ensure_ascii=False).encode("utf-8")).hexdigest()
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=("reliability","value"),default="reliability")
    parser.add_argument("--days",type=int,default=1)
    parser.add_argument("--max-odds-events",type=int,default=15)
    parser.add_argument("--max-requests",type=int,default=90)
    parser.add_argument("--bookmaker",default="consensus")
    parser.add_argument("--output",default="bsd/v2_shadow_predictions.json")
    args=parser.parse_args()
    if not 1<=args.days<=3 or not 0<=args.max_odds_events<=100: parser.error("Invalid bounds")
    now=datetime.now(timezone.utc)
    history=_read_json(MATCHES_FILE,None)
    if not isinstance(history,list) or not history: parser.error("Restore BSD archive first")
    index=V2History(history)
    rho,_=fit_rho_2024(index)
    cal,policy,info=fit_policy(index,rho=rho)
    client=BSDClient(max_requests=args.max_requests)
    events=[]
    for day in range(args.days):
        d=(now+timedelta(days=day)).date()
        page=client.list_events(d,d,max_pages=10,ttl=0)
        if not page.complete: raise RuntimeError("Incomplete fixtures for "+str(d))
        events+=page.events
    def fetcher(fixture,when):
        return fetch_event_odds(client,int(fixture["id"]),kickoff=fixture_datetime(fixture),
                                captured_at=when,bookmaker_slug=args.bookmaker)
    result=generate_shadow(events,history,cal,policy,rho,now=now,mode=args.mode,
                           quote_fetcher=fetcher if args.max_odds_events else None,
                           max_odds_events=args.max_odds_events)
    result["diagnostics"].update({"http_calls":client.requests_made,"rho":rho,
                                   "odds_bookmaker_requested":args.bookmaker,
                                   "quality_validation":info})
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    tmp=dest.with_suffix(".tmp")
    tmp.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    tmp.replace(dest)
    print("BSD_V2_SHADOW:",json.dumps({"selected":len(result["matches"]),
           "events":len(events),"http_calls":client.requests_made,
           "mode":args.mode,"fingerprint_sha256":result["fingerprint_sha256"]}))


if __name__=="__main__":
    main()
