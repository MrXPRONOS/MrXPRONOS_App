#!/usr/bin/env python3
"""Offline V3 simulator. No network, secrets, notifications, production writes.
Usage: python bsd/bsd_v3_40_runner.py --events fixtures.json --history history.json --output tmp/v3-shadow.json
"""
import argparse, json, sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).parent))
from bsd_v3_40_engine import generate_shadow

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--events",required=True)
    p.add_argument("--history",required=True)
    p.add_argument("--output",default="tmp/bsd_v3_40_shadow.json")
    p.add_argument("--rho",type=float,default=0.)
    args=p.parse_args()
    destination=Path(args.output)
    # Refuse to overwrite production artifacts even if pointed by the caller.
    blocked={"data.json","publication_ledger.json","all_matches_bsd.enc.json","all_matches_bsd.json"}
    if destination.name in blocked or "assets" in destination.parts:
        p.error("Refusing to write a production or protected artifact")
    events=json.loads(Path(args.events).read_text(encoding="utf-8"))
    history=json.loads(Path(args.history).read_text(encoding="utf-8"))
    if not isinstance(events,list) or not isinstance(history,list):
        p.error("Both inputs must be JSON lists")
    data=generate_shadow(events,history,now=datetime.now(timezone.utc),rho=args.rho)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"format":data["format"],"matches":len(data["matches"]),
                      "market_count":sum(len(m["markets"]) for m in data["matches"]),
                      "published":False,"path":str(destination)}))

if __name__=="__main__":
    main()
