"""One-date shadow audit for 1xBet Correct Score Group Bet, no publication.
For a historical date: report immutable PRE-match captures separately from
point-in-time REPLAYs, and never mislabel replay as prospective success.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter,defaultdict
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from bsd_v2_core import V2History,fixture_datetime,outcome_scores,league_key
from exact_scores_h2h import H2HIndex
from grouped_correct_score_engine import analyze,fit_direction,selection_summary,VERSION
from grouped_correct_score import group_hit
from grouped_correct_score_prospective import read

STRATEGIES=("baseline","with_double_chance","with_h2h_under",
            "ceiling_under_25","ceiling_under_35","ceiling_under_45")
ALL_GIDS=tuple("G"+str(i) for i in range(1,10))

def utc(s):
    d=datetime.fromisoformat(str(s).replace("Z","+00:00"))
    if d.tzinfo is None: raise ValueError("UTC timezone required")
    return d.astimezone(timezone.utc)

def team(event,side):
    val=event.get(side+"_team")
    if isinstance(val,dict): return str(val.get("name") or "")
    return str(val or "")

def league(event):
    name=event.get("league_name")
    if name: return str(name)
    v=event.get("league")
    return str(v.get("name") if isinstance(v,dict) else v or "")

def metric(entries,eligible):
    n=len(entries);wins=sum(x["hit"] for x in entries)
    meanp=sum(x["p"] for x in entries)/n if n else None
    return {"n":n,"wins":wins,
            "success_rate":round(wins/n,5) if n else None,
            "coverage":round(n/eligible,5) if eligible else None,
            "mean_forecast_probability":round(meanp,5) if meanp is not None else None,
            "calibration_gap":round(wins/n-meanp,5) if n else None,
            "theoretical_break_even_odds":round(n/wins,3) if wins else None}

def run(events,day,ledger):
    index=V2History(events)
    hindex=H2HIndex(index)
    dc,dc_diagnostics=fit_direction(index)
    candidates=[]
    statuses=Counter()
    ids=set()
    for raw in events:
        if not isinstance(raw,dict) or raw.get("id") is None:continue
        try: kickoff=fixture_datetime(raw)
        except (KeyError,ValueError,TypeError):continue
        if kickoff.date()!=day:continue
        ident=str(raw["id"])
        if ident in ids:continue
        ids.add(ident)
        statuses[str(raw.get("status") or "unknown").lower()]+=1
        if outcome_scores(raw) is not None:
            candidates.append(raw)
    candidates.sort(key=lambda e:(fixture_datetime(e),str(e["id"])))
    results_by_id={str(e["id"]):e for e in candidates}
    selection_rows={p:[] for p in STRATEGIES}
    group_rows={g:[] for g in ALL_GIDS}
    by_league=defaultdict(lambda:defaultdict(list))
    stage=Counter();replayed=[];example_rows=[];errors=[]
    for e in candidates:
        when=fixture_datetime(e);score=outcome_scores(e)
        try:
            pred,reason=analyze(e,index,hindex,dc,now=when,
                                require_prematch=False,evaluate_form_shift=False)
        except Exception as ex:
            stage["exception_"+type(ex).__name__]+=1
            if len(errors)<15:errors.append({"match_id":str(e["id"]),"reason":type(ex).__name__})
            continue
        if pred is None:
            stage["skip_"+str(reason)]+=1;continue
        stage["eligible"]+=1
        h2h=bool(pred["h2h_priority"]);u25=bool(pred["under25_priority"])
        stage["h2h_yes" if h2h else "h2h_no"]+=1
        stage["under25_yes" if u25 else "under25_no"]+=1
        if h2h and u25:stage["h2h_under25_both"]+=1
        side=league_key(e) or "unknown";l=league(e)
        choices=selection_summary(pred)
        all_choices={g["group_id"]:g for g in pred["groups"]}
        dateitem={"match_id":str(e["id"]),"kickoff_utc":when.isoformat(),
                  "home":team(e,"home"),"away":team(e,"away"),
                  "league_key":side,"league":l,"final":str(score[0])+"-"+str(score[1]),
                  "under25_p":round(pred["under25_probability"],3),
                  "h2h_priority":h2h,"under25_priority":u25,
                  "selected":{}}
        for p in STRATEGIES:
            chosen=choices.get(p)
            if not chosen:continue
            won=int(group_hit(chosen["scores"],score))
            row={"p":float(chosen["probability"]),"hit":won,"group":chosen["group_id"]}
            selection_rows[p].append(row);by_league[(side,l)][p].append(row)
            dateitem["selected"][p]={"group":chosen["group_id"],
                                     "hit":won,
                                     "probability":round(chosen["probability"],4)}
        for gid,g in all_choices.items():
            hit=int(group_hit(g["scores"],score))
            group_rows[gid].append({"p":float(g["probability"]),"hit":hit})
        if choices.get("with_h2h_under"):stage["h2h_under25_direction"]+=1
        replayed.append(dateitem)
    eligible=stage["eligible"]
    groups={gid:metric(group_rows[gid],eligible) for gid in ALL_GIDS}
    selected={policy:metric(selection_rows[policy],eligible) for policy in STRATEGIES}
    ligas=[]
    for (key,name),policies in by_league.items():
        ligas.append({"league_key":key,"name":name,
                      "base":metric(policies.get("baseline",[]),len(policies.get("baseline",[]))),
                      "under25":metric(policies.get("ceiling_under_25",[]),len(policies.get("baseline",[]))),
                      "strict_h2h":metric(policies.get("with_h2h_under",[]),len(policies.get("baseline",[])))})
    ligas.sort(key=lambda x:(-x["base"]["n"],x["name"]))
    for sample_policy in ("with_h2h_under","ceiling_under_25"):
        examples=[x for x in replayed if sample_policy in x["selected"]]
        example_rows += [{"policy":sample_policy,**x} for x in examples[:30]]
    # Read existing encrypted prospective forecasts; NEVER create retrospective
    # forecasts or change the stored ledger.
    recorded=[r for r in ledger["predictions"].values()
              if utc(r["kickoff_utc"]).date()==day]
    captured=[]
    archived_status=Counter();archived_rows={p:[] for p in STRATEGIES}
    for r in recorded:
        kicked=utc(r["kickoff_utc"]);seen=utc(r["captured_utc"])
        valid_capture=(seen+timedelta(minutes=30)<=kicked)
        settled=results_by_id.get(str(r["match_id"]))
        correct_identity=bool(settled and
                          str(r.get("home_team") or "")==team(settled,"home") and
                          str(r.get("away_team") or "")==team(settled,"away"))
        score=outcome_scores(settled) if settled else None
        if valid_capture:archived_status["valid_before_kickoff"]+=1
        else:archived_status["invalid_capture_time"]+=1
        if score:archived_status["match_found_finished"]+=1
        else:archived_status["final_missing_from_archive"]+=1
        if not correct_identity:archived_status["identity_mismatch"]+=1
        picks={}
        if valid_capture and score and correct_identity:
            choice_map={v["group_id"]:v for v in r.get("groups",[])}
            for policy in STRATEGIES:
                group=choice_map.get(r.get("rules",{}).get(policy))
                if not group:continue
                y=int(group_hit(group["scores"],score))
                p=float(group["probability"])
                archived_rows[policy].append({"p":p,"hit":y})
                picks[policy]={"group":group["group_id"],"hit":y,
                               "probability":round(p,4)}
        captured.append({"match_id":str(r["match_id"]),"home":r.get("home_team"),
                         "away":r.get("away_team"),"kickoff_utc":kicked.isoformat(),
                         "captured_utc":seen.isoformat(),
                         "valid_pre_match_capture":valid_capture,
                         "final":str(score[0])+"-"+str(score[1]) if score else None,
                         "matched_teams":correct_identity,"selections":picks})
    return {
      "format":"mrx-grouped-1xbet-one-day-audit-v1",
      "target_utc_date":day.isoformat(),
      "model_version":VERSION,
      "classification":"historical_replay_vs_existing_frozen_prematch_ledger",
      "experimental":True,"published":False,
      "no_live_1xbet_quotes":True,"real_roi_available":False,
      "evaluation_notes":[
         "UTC kickoff date; some matches started that day may finish the following day.",
         "Replay uses a historical archive but all dynamic match statistics are time-restricted to prior results + 4h.",
         "Replay generated after final results is not a pre-match published prediction or an independent holdout.",
         "Research G1-G9 templates do not establish bookmaker availability; odds never fabricated.",
         "Prospective ledger only counts original timestamped rows verified by archived SHA256 and exact team identity."
      ],
      "archived_matches_with_kickoff_on_date":len(ids),
      "archived_statuses_on_date":dict(statuses),
      "finished_with_score":len(candidates),
      "replay_filter_funnel":dict(stage),
      "replay_eligible":eligible,
      "replay_policy_metrics":selected,
      "replay_all_nine_groups_on_same_matches":groups,
      "replay_leagues":ligas,
      "replay_sample_matches":example_rows[:50],
      "replay_all_matches":replayed,
      "replay_errors":errors,
      "prematch_archive":{
        "recorded_for_date":len(recorded),
        "status":dict(archived_status),
        "metrics":{p:metric(archived_rows[p],archived_status["match_found_finished"]) for p in STRATEGIES},
        "matched_forecasts":captured[:60],
      },
      "double_chance_training_info":dc_diagnostics
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True)
    p.add_argument("--history",default="bsd/all_matches_bsd.json")
    p.add_argument("--out",default="tmp/grouped-correct-score/day-2026-10-19.json")
    args=p.parse_args()
    day=date.fromisoformat(args.date)
    events=json.loads(Path(args.history).read_text(encoding="utf-8"))
    ledger=read()
    result=run(events,day,ledger)
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("GROUPED_DAY_RESULTS",json.dumps({k:result[k] for k in (
       "target_utc_date","finished_with_score","archived_matches_with_kickoff_on_date",
       "replay_eligible","replay_filter_funnel","replay_policy_metrics",
       "prematch_archive") if k!="prematch_archive"},ensure_ascii=False))
    print("GROUPED_DAY_FROZEN_LEDGER",json.dumps({
         "recorded_for_date":result["prematch_archive"]["recorded_for_date"],
         "status":result["prematch_archive"]["status"],
         "metrics":result["prematch_archive"]["metrics"]},ensure_ascii=False))
    print("GROUPED_DAY_EXAMPLES",json.dumps(result["replay_sample_matches"][:15],ensure_ascii=False))
    print("GROUPED_DAY_LEAGUES",json.dumps(result["replay_leagues"][:20],ensure_ascii=False))
if __name__=="__main__":main()
