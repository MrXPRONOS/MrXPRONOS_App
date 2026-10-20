"""Append-only encrypted pre-match ONE-score forecast archive.

Separate from grouped market and legacy Top3 archives.
Store exactly one suggested score (plus private evaluation ablations).
Snapshots are immutable; only result/settlement fields can change.
"""
from __future__ import annotations
import argparse,hashlib,json
from collections import Counter
from datetime import datetime,timedelta,timezone
from pathlib import Path

from bsd_api import BSDClient
from bsd_archive import MATCHES_FILE,cipher
from bsd_h2h import _team_id
from bsd_v2_core import V2History,fixture_datetime,outcome_scores
from exact_scores_prospective import fetch_fixture_window
from exact_scores_h2h import H2HIndex
from single_exact_score_engine import VERSION,PARAMETERS,forecast,train_dc
from single_exact_score_advanced import train_advanced
from single_exact_score_context import enrich_lineups,hydrate_history_xg

PATH=Path("bsd/single_exact_score_ledger.enc.json")
SCHEMA="mrx-single-exact-score-ledger-v1"
RESULT_FIELDS=frozenset(("status","settled_at","actual_score","actual_kickoff_utc",
                          "hit","alternatives_hit","forecast_sha256"))
def empty():
    return {"format":SCHEMA,"model":PARAMETERS,"records":{}}
def digest(row):
    source={k:v for k,v in row.items() if k not in RESULT_FIELDS}
    data=json.dumps(source,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()
def read(path=PATH,secret=None):
    if not path.exists():return empty()
    env=json.loads(path.read_text(encoding="utf-8"))
    if env.get("format")!=SCHEMA or not isinstance(env.get("encrypted"),str):
        raise ValueError("Encrypted ledger required")
    result=json.loads((secret or cipher()).decrypt(env["encrypted"].encode("ascii")))
    if result.get("format")!=SCHEMA or result.get("model")!=PARAMETERS:
        raise ValueError("Incompatible model: preserve original archive")
    for row in result["records"].values():
        if digest(row)!=row.get("forecast_sha256"):
            raise ValueError("The original single-score prediction was edited")
    return result
def save(data,path=PATH,secret=None):
    if data.get("format")!=SCHEMA or data.get("model")!=PARAMETERS:
        raise ValueError("Refusing to overwrite another model's archive")
    if any(digest(row)!=row.get("forecast_sha256") for row in data["records"].values()):
        raise ValueError("Cannot save modified pre-match forecast")
    contents=json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    token=(secret or cipher()).encrypt(contents.encode("utf-8")).decode("ascii")
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+".tmp")
    temp.write_text(json.dumps({"format":SCHEMA,"encrypted":token}),encoding="utf-8")
    temp.chmod(0o600)
    temp.replace(path)

def capture(archive,fixtures,index,model,now,*,limit=500,advanced_model=None):
    hindex=H2HIndex(index)
    counter=Counter()
    for event in sorted(fixtures,key=lambda x:(fixture_datetime(x),str(x["id"]))):
        key=str(event["id"])
        if key in archive["records"]:
            counter["already_seen"]+=1
            continue
        if counter["captured"]>=limit:
            counter["limit_reached"]+=1;continue
        output,reason=forecast(event,index,hindex,dc_model=model,now=now,
                               advanced_model=advanced_model)
        if output is None:
            counter[reason]+=1;continue
        row={"id":key,"model":VERSION,"captured_at":now.isoformat(),
             "kickoff":output["kickoff_utc"],"home_id":_team_id(event,"home"),
             "away_id":_team_id(event,"away"),"score":output["score"],
             "estimated_probability":output["estimated_score_probability"],
             "score_margin":output["score_margin"],
             "research_priority":output["research_priority"],
             "expected_goals":output["expected_goals"],
             "h2h_low_stable":output["h2h_low_stable"],
             "under25_probability":output["under25_probability"],
             "form_risk":output["form_risk"],
             "experimental_ablation":{
                 **{k:(v["score"] if v else None)
                    for k,v in output["ablation"].items()},
                 "advanced_2024":(output["advanced_research"]["choice"]["score"]
                                  if output.get("advanced_research") else None)},
             "advanced_research":output.get("advanced_research"),
             "status":"pending"}
        row["forecast_sha256"]=digest(row)
        archive["records"][key]=row
        counter["captured"]+=1
    return dict(counter)
def settle(archive,fixtures,now):
    by_id={}
    for event in fixtures:
        if not isinstance(event,dict) or event.get("id") is None:continue
        try:
            event_at=fixture_datetime(event)
        except (TypeError,ValueError):continue
        key=str(event["id"])
        if key not in by_id or outcome_scores(event) is not None:
            by_id[key]=event
    counter=Counter()
    for key,row in archive["records"].items():
        if row["status"]!="pending":continue
        found=by_id.get(key)
        if found is None:continue
        at=fixture_datetime(found)
        original=datetime.fromisoformat(row["kickoff"])
        if now<max(original,at)+timedelta(hours=4):continue
        score=outcome_scores(found)
        if score is None:continue
        if (_team_id(found,"home")!=row["home_id"] or
            _team_id(found,"away")!=row["away_id"]):
            counter["different_teams"]+=1;continue
        row["status"]="settled"
        row["settled_at"]=now.isoformat()
        row["actual_kickoff_utc"]=at.isoformat()
        row["actual_score"]=list(score)
        row["hit"]=int(tuple(row["score"])==score)
        row["alternatives_hit"]={k:(int(tuple(v)==score) if v else None)
                   for k,v in row["experimental_ablation"].items()}
        counter["settled"]+=1
    return dict(counter)
def summary(archive,now):
    values=list(archive["records"].values())
    done=[v for v in values if v["status"]=="settled"]
    def calculate(rows):
        n=len(rows);hits=sum(x["hit"] for x in rows)
        return {"n":n,"hits":hits,"top1_rate":round(hits/n,6) if n else None,
                "average_estimated_probability":round(sum(x["estimated_probability"] for x in rows)/n,6) if n else None}
    return {"format":"mrx-single-exact-score-summary-v1","generated_at":now.isoformat(),
            "experimental":True,"published":False,"model":VERSION,
            "captured":len(values),"pending":len(values)-len(done),
            "settled":len(done),"all":calculate(done),
            "priority":calculate([v for v in done if v["research_priority"]]),
            "h2h_under":calculate([v for v in done if v["h2h_low_stable"] and v["under25_probability"]>=.62]),
            "experimental_alternatives":{
               name:{"n":len(rows:=[r for r in done if r["alternatives_hit"].get(name) is not None]),
                     "hits":sum(r["alternatives_hit"][name] for r in rows)}
               for name in ("original","under25_fusion","optional_dc_fusion","advanced_2024")},
            "note":"Exact ONE score per fixture. No odds, ROI or guarantee."}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--history",default=str(MATCHES_FILE))
    parser.add_argument("--ledger",default=str(PATH))
    parser.add_argument("--report",default="tmp/single-exact-score/prospective-report.json")
    parser.add_argument("--max-requests",type=int,default=90)
    args=parser.parse_args()
    now=datetime.now(timezone.utc)
    matches=json.loads(Path(args.history).read_text(encoding="utf-8"))
    if not matches:raise RuntimeError("Historical BSD archive empty")
    index=V2History(matches)
    dc,training=train_dc(index)
    advanced=train_advanced(index)
    client=BSDClient(max_requests=args.max_requests)
    upcoming=fetch_fixture_window(client,now)
    archive=read(Path(args.ledger))
    pending_new=[e for e in upcoming if str(e.get("id")) not in archive["records"]]
    # Budgeted requests only for prematch candidates; missing data is explicit.
    xg_diag=hydrate_history_xg(index,pending_new,client,now,max_lookups=12)
    lineup_diag=enrich_lineups(pending_new,client,now,max_lookups=6)
    added=capture(archive,upcoming,index,dc,now,advanced_model=advanced)
    pending={key for key,r in archive["records"].items() if r["status"]=="pending"}
    completed=[event for _t,event in index.global_games if str(event["id"]) in pending]
    finished=settle(archive,completed+upcoming,now)
    if added.get("captured") or finished.get("settled"):
        save(archive,Path(args.ledger))
    result=summary(archive,now)
    dest=Path(args.report);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print("ONE_SCORE_PROSPECTIVE",json.dumps({"capture":added,"settlement":finished,
        "summary":result,"api_requests":client.requests_made,
        "historical_measured_xg":xg_diag,"lineups":lineup_diag,
        "advanced_training":advanced.info()},ensure_ascii=False))
if __name__=="__main__":main()
