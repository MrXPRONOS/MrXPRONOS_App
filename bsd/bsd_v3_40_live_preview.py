#!/usr/bin/env python3
"""Populate the V3 test page from actual BSD fixtures, never from V2 output."""
from __future__ import annotations
import argparse,json
from datetime import datetime,timezone,timedelta
from pathlib import Path
from bsd_api import BSDClient
from bsd_archive import MATCHES_FILE,_read_json
from bsd_v2_core import V2History,fit_rho_2024
from bsd_v3_40_engine import generate_shadow
from bsd_v3_40_calibration import fit_goal_calibration

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="bsd/v3_preview_feed.json")
    p.add_argument("--max-requests",type=int,default=110)
    p.add_argument("--days",type=int,default=2)
    args=p.parse_args()
    if not 1<=args.days<=3 or not 1<=args.max_requests<=300:p.error("Unsupported bounds")
    out=Path(args.output)
    if out.name!="v3_preview_feed.json":p.error("Only the V3 preview feed is writable")
    history=_read_json(MATCHES_FILE,None)
    if not isinstance(history,list) or not history:raise RuntimeError("BSD encrypted history must be restored first")
    now=datetime.now(timezone.utc)
    idx=V2History(history)
    rho,_=fit_rho_2024(idx)
    goal_calibration,calibration_training=fit_goal_calibration(idx,max_training=700)
    client=BSDClient(max_requests=args.max_requests)
    fixtures=[]
    for k in range(args.days):
        day=(now+timedelta(days=k)).date()
        result=client.list_events(day,day,max_pages=10,ttl=0)
        if not result.complete:raise RuntimeError("Incomplete licensed fixture data; refusing a stale feed")
        fixtures.extend(result.events)
    data=generate_shadow(fixtures,history,now=now,rho=rho,goal_calibration=goal_calibration)
    data['diagnostics']['calibration_training']=calibration_training
    data["diagnostics"]["api_requests"]=client.requests_made
    data["diagnostics"]["real_fixture_source"]="BSD"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf8")
    print("V3_SHADOW_GENERATED",len(data["matches"]),"matches",len(data["matches"])*40,"market observations")

if __name__=="__main__":main()
