#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single-day RETROSPECTIVE evaluation: 20 October 2026, Mr XPRONOS.

Historical features and model training are constructed only from matches on
calendar days <= 2026-10-19.  2026-10-20 results are fetched independently
as OUTCOME LABELS and never passed into the predictor's training history.
Because this test is executed after the event, it is a retrospective, cutoff-
safe test; it is NOT a contemporaneously timestamped pre-match forecast.
"""
from __future__ import annotations
import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from allmatches import extract_game_info
from sportdata_api import fetch_games
from exact_scores_2026 import Match, load_matches, utc_day
from predict_consensus import SIX, consensus, predict

TARGET = date(2026, 10, 20)
HISTORY_MAX = TARGET - timedelta(days=1)
NAME = "Mr XPRONOS - Six-model consensus - 2026-10-20"


def clean_score(s):
    parts = str(s).strip().replace("-", ":").split(":")
    if len(parts) != 2 or not all(x.isdigit() for x in parts):
        return None
    h, a = [int(x) for x in parts]
    if h > 10 or a > 10:
        return None
    return h, a


def supplement_training(cache_path, predictions_csv, allowed_competitions):
    """Historical results stored in previous FULL-backfill GitHub Actions output.

    Archive contains pre-generated predictions and final labels on 2026 dates.
    Target day scores cannot appear. Do not use any predictions/probabilities
    from archive as a feature or target for learning.
    """
    original = load_matches(str(cache_path), HISTORY_MAX)
    def allowed(league):
        return league in allowed_competitions
    history = [m for m in original if allowed(m.league)]
    cache = {m.key: m for m in history}
    audit = Counter({
        "cache_matches_before_cutoff": len(history),
        "raw_cache_matches_before_sport_filter": len(original),
        "football_competition_labels_allowed": len(allowed_competitions),
        "csv_rows_checked": 0,
        "csv_training_matches_added": 0,
        "overlap_same_outcome": 0,
        "overlap_conflicts": 0,
        "excluded_target_or_future_rows": 0,
    })
    observed_keys=set()
    with open(predictions_csv,newline="",encoding="utf8") as fh:
        for r in csv.DictReader(fh):
            if r.get("model") != "poisson":
                continue  # One final label per archived fixture
            audit["csv_rows_checked"] += 1
            d = utc_day(r.get("date"))
            if d is None or d >= TARGET:
                audit["excluded_target_or_future_rows"] += 1
                continue
            ident = str(r.get("id") or "").strip()
            score = clean_score(r.get("actual_score"))
            league = str(r.get("league") or "").strip()
            home = str(r.get("home") or "").strip()
            away = str(r.get("away") or "").strip()
            if not (ident and score and league and home and away):
                audit["invalid_archive_record"] += 1
                continue
            if not allowed(league):
                audit["historical_matches_excluded_as_unverified_football"] += 1
                continue
            if not (ident and score and league and home and away):
                audit["invalid_archive_record"] += 1
                continue
            if ident in observed_keys:
                raise ValueError("Duplicate frozen historical fixture: " + ident)
            observed_keys.add(ident)
            old = cache.get(ident)
            if old is not None:
                if (old.hg,old.ag) == score and old.day == d:
                    audit["overlap_same_outcome"] += 1
                else:
                    audit["overlap_conflicts"] += 1
                    # Do not use conflicting labels from duplicate source.
                continue
            cache[ident]=Match(ident,d,league,home,away,score[0],score[1])
            audit["csv_training_matches_added"] += 1
    history=sorted(cache.values(),key=lambda m:(m.day,m.key))
    assert all(m.day<TARGET for m in history), "FUTURE LEAKAGE DETECTED"
    audit["final_historical_training_matches"]=len(history)
    return history,dict(audit)


def final_results_from_sportdata(day):
    fetched=fetch_games(day,day,timeout=45,show_odds=False)
    # allscores is MULTI-SPORT despite its URL. sportId=1 is Football,
    # sportId=3 tennis, sportId=8 volleyball; never infer sport from score.
    recognized_football=set()
    recognized_other=set()
    competition_metadata=(fetched.payload.get("competitions") or []) if isinstance(fetched.payload,dict) else []
    for g in fetched.games:
        name=str(g.get("competitionDisplayName") or "").strip()
        if name:
            if g.get("sportId")==1:
                recognized_football.add(name)
            else:
                recognized_other.add(name)
    for league in competition_metadata:
        if not isinstance(league,dict):
            continue
        name=str(league.get("name") or "").strip()
        if name:
            if league.get("sportId")==1:
                recognized_football.add(name)
            else:
                recognized_other.add(name)
    # A league name that identifies several sports cannot certify history.
    leagues=recognized_football-recognized_other
    audit={
        "source":"SportsAPI Pro /v1/football/games/allscores",
        "requested_day":str(day),"api_ok":fetched.ok,
        "failure_reason":(fetched.reason or "")[:220] if not fetched.ok else None,
        "returned_raw_games":len(fetched.games),
        "raw_football_games":sum(g.get("sportId")==1 for g in fetched.games),
        "raw_other_sports_excluded":sum(g.get("sportId")!=1 for g in fetched.games),
        "certified_soccer_competition_names_for_training":len(leagues),
        "endpoint":fetched.endpoint,
        "filter":"is_finished == True, statusGroup == 4, kickoff UTC date == requested day, valid final score",
    }
    if not fetched.ok:
        return [],audit,[]
    by_id={}
    bad=Counter()
    for raw in fetched.games:
        if not isinstance(raw,dict):
            bad["non_object"]+=1
            continue
        if raw.get("sportId")!=1:
            bad["not_football_sportId"]+=1
            continue
        rec=extract_game_info(raw)
        d=utc_day(rec.get("start_time"))
        if d!=day:
            bad["outside_target_date"]+=1
            continue
        if rec.get("is_finished") is not True or str(rec.get("status_group"))!="4":
            bad["not_finished"]+=1
            continue
        score=clean_score(f'{rec["home_score"]}:{rec["away_score"]}')
        if score is None:
            bad["invalid_or_large_score"]+=1
            continue
        ident=str(rec.get("id") or "").strip()
        if not (ident and rec.get("home_team") and rec.get("away_team") and rec.get("competition")):
            bad["missing_teams_or_league"]+=1
            continue
        by_id[ident]={
            "id":ident,"date":str(day),"league":str(rec["competition"]).strip(),
            "home_team":str(rec["home_team"]).strip(),
            "away_team":str(rec["away_team"]).strip(),
            "actual_home":score[0],"actual_away":score[1],
            "actual_score":f"{score[0]}:{score[1]}",
            "finish_status":4,
        }
    audit["total_accepted_finished_matches"]=len(by_id)
    audit["discarded"]=dict(bad)
    return sorted(by_id.values(),key=lambda x:(x["league"],x["home_team"],x["away_team"])),audit,sorted(leagues)


def create_report(targets,predictions,history_audit,source_audit,out):
    lookup={r["id"]:r for r in targets}
    out.mkdir(parents=True,exist_ok=True)
    individual={m:{"n":0,"hits":0} for m in SIX}
    voting={str(v):{"n":0,"hits":0} for v in (3,4,5,6)}
    agreement=Counter()
    details=[]
    for pred in predictions:
        actual=lookup[pred["id"]]
        six=pred.get("models")
        if not isinstance(six,dict) or set(six)!=set(SIX):
            raise RuntimeError("A fixture did not receive all six model votes: "+pred["id"])
        assert pred["date"]==str(TARGET)
        assert pred["previous_completed_match_count"]==history_audit["final_historical_training_matches"]
        highest=max(Counter(six.values()).values())
        agreement[str(highest)] += 1
        for m in SIX:
            individual[m]["n"]+=1
            individual[m]["hits"]+=int(six[m]==actual["actual_score"])
        decisions={}
        for threshold in (3,4,5,6):
            decision=consensus(six,threshold)
            decisions[str(threshold)]=decision
            if decision["status"]=="SELECTED":
                voting[str(threshold)]["n"]+=1
                voting[str(threshold)]["hits"]+=int(decision["score"]==actual["actual_score"])
        details.append({
            "date":str(TARGET),"match_id":pred["id"],"league":pred["league"],
            "home":pred["home_team"],"away":pred["away_team"],
            "actual_score":actual["actual_score"],"highest_votes":highest,
            "top_score":decisions["3"]["top_score_without_threshold"] or "ABSTAIN",
            "tied_for_first":decisions["3"]["tied_first"],
            "six_picks":six,"vote_thresholds":decisions,
            "result_3":decisions["3"]["score"]==actual["actual_score"] if decisions["3"]["status"]=="SELECTED" else None,
            "result_4":decisions["4"]["score"]==actual["actual_score"] if decisions["4"]["status"]=="SELECTED" else None,
            "result_5":decisions["5"]["score"]==actual["actual_score"] if decisions["5"]["status"]=="SELECTED" else None,
            "result_6":decisions["6"]["score"]==actual["actual_score"] if decisions["6"]["status"]=="SELECTED" else None,
        })
    n=len(targets)
    for m,entry in individual.items():
        entry["hit_rate_pct"]=round(100*entry["hits"]/n,3) if n else None
    for k,entry in voting.items():
        selected=entry["n"]
        entry["hit_rate_pct"]=round(100*entry["hits"]/selected,3) if selected else None
        entry["coverage_pct"]=round(100*selected/n,3) if n else 0
        entry["abstained"]=n-selected
        entry["misses"]=selected-entry["hits"]
    examples=sorted(details,key=lambda d:(-d["highest_votes"],d["league"],d["home"]))[:35]
    report={
        "title":NAME,
        "type":"retrospective cutoff-safe backtest; generated after match day",
        "date_tested":str(TARGET),
        "features_cannot_include_target_match_result":True,
        "previous_game_cutoff_inclusive":str(HISTORY_MAX),
        "history_audit":history_audit,"match_source_audit":source_audit,
        "n_completed_evaluable_matches":n,
        "individual_models":individual,"voting_thresholds":voting,
        "highest_agreement_distribution":dict(agreement),
        "examples_top_voted":examples[:18],
        "limitations":[
            "This is a retroactive model run, not a contemporaneous prediction saved before kickoff",
            "The training archive contains known 2026 score results but may have gaps and different source labels",
            "Only SportData statusGroup=4 completed matches are evaluated",
            "Consensus hit rate is not betting ROI; no timestamped bookmaker exact-score odds",
            "Model votes share features, hence model agreement is not independent confidence",
        ],
    }
    (out/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    (out/"all_match_results.json").write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding="utf8")
    with (out/"all_match_results.csv").open("w",newline="",encoding="utf8") as fh:
        fieldnames=["date","match_id","league","home","away","actual_score","highest_votes",
                    "consensus_score","selected_3","selected_4","selected_5","selected_6",
                    "correct_3","correct_4","correct_5","correct_6"]+["pred_"+m for m in SIX]
        writer=csv.DictWriter(fh,fieldnames=fieldnames)
        writer.writeheader()
        for d in details:
            row={k:d[k] for k in ("date","match_id","league","home","away","actual_score","highest_votes")}
            row["consensus_score"]=d["top_score"]
            for k in (3,4,5,6):
                dec=d["vote_thresholds"][str(k)]
                row[f"selected_{k}"]=int(dec["status"]=="SELECTED")
                row[f"correct_{k}"]=int(dec["score"]==d["actual_score"]) if dec["status"]=="SELECTED" else ""
            row.update({"pred_"+m:d["six_picks"][m] for m in SIX})
            writer.writerow(row)
    print("YESTERDAY_FINAL_REPORT",json.dumps({
        "day":report["date_tested"],"n_finished":n,
        "source":source_audit,"history":history_audit,
        "individual_models":individual,"voting_thresholds":voting,
        "highest_agreement_distribution":dict(agreement),
        "examples":examples[:15]
    },ensure_ascii=False),flush=True)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--prior-predictions",required=True)
    p.add_argument("--history",default="cache/all_matches.json")
    p.add_argument("--outcomes-file",help="Reuse previously verified final-score snapshot; no repeat SportData request")
    p.add_argument("--outcomes-audit-file",help="Original SportData audit JSON")
    p.add_argument("--football-leagues-file",help="Verified SportData football competition names for training filter")
    p.add_argument("--output",default="research/results/yesterday_2026_10_20")
    args=p.parse_args()
    output=Path(args.output)
    output.mkdir(parents=True,exist_ok=True)
    if args.outcomes_file:
        targets=json.loads(Path(args.outcomes_file).read_text(encoding="utf8"))
        if args.outcomes_audit_file:
            audit=json.loads(Path(args.outcomes_audit_file).read_text(encoding="utf8"))
        else:
            audit={"source":"archived verified SportsAPI Pro Oct-20 snapshot",
                   "api_ok":True,"total_accepted_finished_matches":len(targets),
                   "requested_day":str(TARGET)}
        for row in targets:
            if row["date"]!=str(TARGET) or row["finish_status"]!=4 or not clean_score(row["actual_score"]):
                raise ValueError("Invalid archived final score record, aborting")
        if len({r["id"] for r in targets}) != len(targets):
            raise ValueError("Duplicated fixtures in archived actual-score snapshot")
        if not args.football_leagues_file:
            raise ValueError("A verified football competition whitelist is mandatory for archived target data")
        leagues=json.loads(Path(args.football_leagues_file).read_text(encoding="utf8"))
        audit["reused_snapshot_from_previous_run"]=True
    else:
        targets,audit,leagues=final_results_from_sportdata(TARGET)
    (output/"sportdata_fetch_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf8")
    (output/"verified_football_competitions.json").write_text(json.dumps(leagues,ensure_ascii=False,indent=2),encoding="utf8")
    print("YESTERDAY_SOURCE_AUDIT",json.dumps(audit,ensure_ascii=False),flush=True)
    if not audit["api_ok"] or len(targets)==0:
        raise RuntimeError("No verified finished fixtures were recovered for 2026-10-20. Never invent results.")
    # The final scores are isolated from prediction generation.
    (output/"verified_finished_fixtures_2026_10_20.json").write_text(
        json.dumps(targets,ensure_ascii=False,indent=2),encoding="utf8")
    # Filter historical training by provably football-only competition labels
    # because older normalized all_matches.json did not store sportId.
    hist,histaudit=supplement_training(args.history,args.prior_predictions,set(leagues))
    print("YESTERDAY_TRAINING_CUTOFF",json.dumps(histaudit,ensure_ascii=False),flush=True)
    features=[{"date":TARGET, **{k:row[k] for k in ("id","league","home_team","away_team")}} for row in targets]
    predicted=predict(features,hist,minimum=5)
    create_report(targets,predicted,histaudit,audit,output)


if __name__=="__main__":
    main()
