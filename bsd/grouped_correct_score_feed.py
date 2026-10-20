"""Safely stage grouped-score display feed from a PRIVATE encrypted shadow ledger.

Produces a review artifact, NEVER data.json or any public-site update. UI
only displays grouped markets when a fixture-specific book quote is recorded.
"""
from __future__ import annotations
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from grouped_correct_score_prospective import read
from grouped_correct_score import group_hit

FORMAT="mrx-1xbet-grouped-preview-v1"

def group_feed(ledger,*,now):
    rows=[]
    for r in ledger["predictions"].values():
        if r["market_status"]!="fixture_quote_snapshot":
            continue
        if r["status"]=="pending" and datetime.fromisoformat(r["kickoff_utc"])<=now:
            # Started but unverified score: keep in private ledger, not in
            # public-style upcoming or completed results.
            continue
        out=[]
        for g in r["groups"]:
            if not g["quote_documented"]:continue
            item={"group_id":g["group_id"],"scores":g["scores"],
                  "probability":g["probability"],
                  "direction_eligible":g["direction_eligible"],
                  "odds":g["odds"],"quote_documented":True,
                  "expected_value":g["expected_value"],
                  "quote_captured_utc":g["odds_captured_utc"]}
            if r["status"]=="settled":
                item["hit"]=int(group_hit(g["scores"],r["actual_score"]))
            out.append(item)
        if not out:continue
        rows.append({"id":r["match_id"],"home_team":r.get("home_team"),
            "away_team":r.get("away_team"),"league":r.get("league"),
            "kickoff_utc":r["kickoff_utc"],"status":r["status"],
            "direction":r["double_chance"]["direction"],
            "h2h_priority":r["h2h_priority"],
            "under25_priority":r["under25_priority"],
            "groups":out})
    rows.sort(key=lambda x:(x["kickoff_utc"],x["id"]))
    return {"format":FORMAT,"generated_utc":now.isoformat(),"bookmaker":"1xbet",
            "market":"Correct Score - Group Bet",
            "published":False,"experimental":True,
            "odds_origin":"documented 1xBet match-specific user/provider snapshots; live source not independently connected",
            "matches":rows}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ledger",default="bsd/grouped_1xbet_shadow_ledger.enc.json")
    ap.add_argument("--out",default="tmp/grouped-correct-score/scores-groupes-review.json")
    opts=ap.parse_args()
    data=group_feed(read(Path(opts.ledger)),now=datetime.now(timezone.utc))
    dest=Path(opts.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
    print("GROUPED_SITE_REVIEW",json.dumps({"rows":len(data["matches"]),
          "public":data["published"]},ensure_ascii=False))
if __name__=="__main__":main()
