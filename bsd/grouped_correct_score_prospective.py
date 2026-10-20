"""Private frozen prospective grouped-correct-score forecasts, 1xBet research.

Same immutable-first-seen principle as the existing exact-score monitoring,
but a SEPARATE encrypted ledger to preserve the former archive's schema.
"""
from __future__ import annotations
import argparse,hashlib,json
from collections import Counter
from datetime import datetime,timedelta,timezone
from pathlib import Path
from bsd_archive import MATCHES_FILE,cipher
from bsd_api import BSDClient
from bsd_h2h import _team_id
from bsd_v2_core import V2History,fixture_datetime,outcome_scores
from exact_scores_h2h import H2HIndex
from exact_scores_prospective import fetch_fixture_window
from grouped_correct_score_engine import analyze,fit_direction,selection_summary,VERSION
from grouped_correct_score import group_hit

PATH=Path("bsd/grouped_1xbet_shadow_ledger.enc.json")
SCHEMA="mrx-1xbet-grouped-prospective-ledger-v1"
SETTLED_KEYS=frozenset(("status","actual_score","actual_kickoff_utc","settled_utc","results","forecast_sha256"))

def empty():
    return {"format":SCHEMA,"model":VERSION,"predictions":{}}

def digest(row):
    message=json.dumps({k:v for k,v in row.items() if k not in SETTLED_KEYS},
                       ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return hashlib.sha256(message.encode("utf-8")).hexdigest()

def read(path=PATH,secret=None):
    if not path.exists():return empty()
    data=json.loads(path.read_text(encoding="utf-8"))
    if data.get("format")!=SCHEMA:raise ValueError("Encrypted group ledger format changed")
    decoded=json.loads((secret or cipher()).decrypt(data["encrypted"].encode("ascii")))
    if decoded.get("format")!=SCHEMA or decoded.get("model")!=VERSION:
        raise ValueError("Model or schema mismatch")
    for row in decoded["predictions"].values():
        if digest(row)!=row.get("forecast_sha256"):
            raise ValueError("Immutable grouped forecast modified")
    return decoded

def save(ledger,path=PATH,secret=None):
    if ledger.get("format")!=SCHEMA or ledger.get("model")!=VERSION:
        raise ValueError("Refusing wrong grouped forecast model")
    for row in ledger["predictions"].values():
        if digest(row)!=row.get("forecast_sha256"):
            raise ValueError("Refusing to seal edited grouped forecast")
    payload=json.dumps(ledger,ensure_ascii=False,separators=(",",":"),sort_keys=True)
    token=(secret or cipher()).encrypt(payload.encode("utf-8")).decode("ascii")
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+".tmp")
    tmp.write_text(json.dumps({"format":SCHEMA,"encrypted":token}),encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(path)

def _team_name(event,side):
    value=event.get(side+"_team")
    if isinstance(value,dict):return str(value.get("name") or "")
    if isinstance(value,str):return value.strip()
    return ""

def capture(ledger,fixtures,index,dc,*,now,quotes=None,max_new=500):
    hindex=H2HIndex(index);known={r["match_id"] for r in ledger["predictions"].values()}
    counts=Counter();new=0
    for e in sorted(fixtures,key=lambda x:(fixture_datetime(x),str(x["id"]))):
        eid=str(e["id"])
        if eid in known:
            counts["already_captured"]+=1;continue
        if new>=max_new:counts["max_new_reached"]+=1;continue
        kick=fixture_datetime(e)
        if kick<=now+timedelta(minutes=30) or str(e.get("status","")).lower() in (
              "finished","cancelled","canceled","abandoned","postponed"):
            counts["not_future"]+=1;continue
        quotation=(quotes or {}).get(eid)
        result,reason=analyze(e,index,hindex,dc,now=now,quote_snapshot=quotation,
                              evaluate_form_shift=True)
        if result is None:counts[reason]+=1;continue
        selected=selection_summary(result)
        row={"match_id":eid,"kickoff_utc":kick.isoformat(),
             "captured_utc":now.isoformat(),
             "home_id":_team_id(e,"home"),"away_id":_team_id(e,"away"),
             "model":VERSION,
             "home_team":_team_name(e,"home"),
             "away_team":_team_name(e,"away"),
             "league":str(e.get("league_name") or ""),
             "h2h_priority":result["h2h_priority"],
             "under25_priority":result["under25_priority"],
             "double_chance":json.loads(json.dumps(result["double_chance"])),
             "under25_probability":round(result["under25_probability"],7),
             "goals_profile":result["goals_profile"],
             "groups":result["groups"],
             "market_status":result["market_status"],
             "form_shift":({
                 "version":result["form_shift"]["version"],
                 "flags":result["form_shift"]["flags"],
                 "variant_pass":result["form_shift"]["variant_pass"]}
                 if result.get("form_shift") else None),
             "rules":{k:v["group_id"] if v else None for k,v in selected.items()},
             "status":"pending"}
        row["forecast_sha256"]=digest(row)
        ledger["predictions"][eid]=row;known.add(eid)
        new+=1
    return {"captured":new,"skipped":dict(counts)}

def settle(ledger,fixtures,now):
    by_id={}
    for f in fixtures:
        if not isinstance(f,dict) or f.get("id") is None:continue
        try:kick=fixture_datetime(f)
        except (ValueError,KeyError,TypeError):continue
        k=str(f["id"])
        if k not in by_id or (outcome_scores(f) is not None):
            by_id[k]=f
    result=Counter()
    for eid,row in ledger["predictions"].items():
        if row["status"]!="pending":continue
        actual=by_id.get(eid)
        if not actual:continue
        kickoff=fixture_datetime(actual)
        if now<max(datetime.fromisoformat(row["kickoff_utc"]),kickoff)+timedelta(hours=4):
            continue
        score=outcome_scores(actual)
        if score is None:continue
        if _team_id(actual,"home")!=row["home_id"] or _team_id(actual,"away")!=row["away_id"]:
            result["identity_mismatch"]+=1;continue
        row["status"]="settled";row["settled_utc"]=now.isoformat()
        row["actual_kickoff_utc"]=kickoff.isoformat();row["actual_score"]=list(score)
        score_by_group={r["group_id"]:int(group_hit(r["scores"],score)) for r in row["groups"]}
        row["results"]={name:(score_by_group.get(selected) if selected else None)
                        for name,selected in row["rules"].items()}
        result["settled"]+=1
    return dict(result)

def report(ledger,now):
    all_rows=list(ledger["predictions"].values())
    past=[r for r in all_rows if r["status"]=="settled"]
    policies=("baseline","with_double_chance","with_h2h_under",
              "with_verified_price",
              "ceiling_under_25","ceiling_under_35","ceiling_under_45",
              "ceiling_under_55","ceiling_under_65","ceiling_under_75",
              "form_recent_attack","form_recent_defence",
              "form_historical_h2h_context","form_venue_shift",
              "form_model_agreement","form_combined","form_strict")
    policies_out={}
    for policy in policies:
        values=[r["results"].get(policy) for r in past if r["results"].get(policy) is not None]
        group_ids={r["rules"].get(policy) for r in past if r["rules"].get(policy)}
        policies_out[policy]={"n":len(values),"wins":sum(values),
                              "hit_rate":round(sum(values)/len(values),5) if values else None,
                              "distinct_groups":len(group_ids)}
    ceiling_metrics={}
    for cap in (2,3,4,5,6,7):
        key=f"under_{cap}5"
        available=[(float(r["goals_profile"]["under_probabilities"][key]),
                    int(sum(r["actual_score"])<=cap))
                   for r in past if isinstance(r.get("goals_profile"),dict)
                   and r["goals_profile"].get("under_probabilities",{}).get(key) is not None]
        n=len(available)
        ceiling_metrics[key]={
            "n":n,"hits":sum(hit for _,hit in available),
            "observed_under":round(sum(hit for _,hit in available)/n,5) if n else None,
            "mean_estimated":round(sum(p for p,_ in available)/n,5) if n else None,
            "brier":round(sum((p-hit)**2 for p,hit in available)/n,6) if n else None}
    cutoff=now-timedelta(days=4)
    return {"format":"mrx-grouped-prospective-metrics-v1",
            "generated_utc":now.isoformat(),"experimental":True,"published":False,
            "bookmaker":"1xbet","total_captured":len(all_rows),
            "pending":sum(r["status"]=="pending" for r in all_rows),
            "settled":len(past),
            "overdue_missing_results":sum(r["status"]=="pending" and
               datetime.fromisoformat(r["kickoff_utc"])<cutoff for r in all_rows),
            "priced_captured":sum(r["market_status"]=="fixture_quote_snapshot" for r in all_rows),
            "goals_profile_captured":sum("goals_profile" in r for r in all_rows),
            "goals_profile_note":"Older archived forecasts remain immutable and have no new ceiling predictions.",
            "policies":policies_out,
            "goal_ceiling_calibration":ceiling_metrics,
            "warning":"No bookmaker actual market, no real-odds EV or betting return without observed 1xBet prematch quotes."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ledger",default=str(PATH))
    p.add_argument("--quotes-json",default="")
    p.add_argument("--max-requests",type=int,default=90)
    p.add_argument("--report",default="tmp/grouped-correct-score/prospective-report.json")
    args=p.parse_args()
    now=datetime.now(timezone.utc)
    history=json.loads(MATCHES_FILE.read_text(encoding="utf-8"))
    if not history:raise RuntimeError("Missing encrypted BSD history restore")
    index=V2History(history)
    dc,diagnostics=fit_direction(index)
    client=BSDClient(max_requests=args.max_requests)
    fixtures=fetch_fixture_window(client,now)
    quote_docs={}
    if args.quotes_json:
        docs=json.loads(Path(args.quotes_json).read_text(encoding="utf-8"))
        if not isinstance(docs,list):raise ValueError("Expected list of per-match 1xBet captures")
        for d in docs:
            event_id=str(d["bsd_event_id"])
            if event_id in quote_docs:raise ValueError("Duplicate bookmaker quote for fixture")
            quote_docs[event_id]=d
    ledger=read(Path(args.ledger))
    new=capture(ledger,fixtures,index,dc,now=now,quotes=quote_docs)
    pending={id for id,row in ledger["predictions"].items() if row["status"]=="pending"}
    completed=[e for _ts,e in index.global_games if str(e["id"]) in pending]
    reconciled=settle(ledger,completed+fixtures,now)
    if new["captured"] or reconciled.get("settled"):
        save(ledger,Path(args.ledger))
    metrics=report(ledger,now)
    out=Path(args.report);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
    print("GROUPED_PROSPECTIVE",json.dumps({"capture":new,"settlement":reconciled,
         "metrics":metrics,"dc_training":diagnostics,"api_calls":client.requests_made},
        ensure_ascii=False))

if __name__=="__main__":main()
