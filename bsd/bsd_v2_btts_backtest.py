"""Audit BTTS 2026 hors echantillon : meme methode que la qualite V2,
avec exclusion du repli Poisson et statistiques de seuils sur les memes matchs.

Les cotes contemporaines ne sont pas présentes dans l'archive historique:
ne pas inférer la rentabilité d'un backtest sans prix pré-match.
"""
from __future__ import annotations
import argparse,json
from math import exp
from dataclasses import replace
from datetime import date
from collections import Counter,defaultdict
from pathlib import Path
from bsd_archive import MATCHES_FILE,_read_json
from bsd_backtest import wilson_interval
from bsd_v2_core import V2History,fit_rho_2024,estimate_goals,score_matrix,markets_from_matrix,fixture_datetime,outcome_scores,league_key
from bsd_v2_btts import fit_btts_model,btts_candidates,btts_features,btts_quality_rejection
from bsd_v2_btts_h2h import btts_h2h_decision
from bsd_v2_policies import fit_policy
from bsd_v2_evaluate import get_sample


def _statistics(rows):
    count=len(rows)
    if not count:return {"n":0,"wins":0,"hit_rate":None,"brier":None}
    successes=sum(row[1] for row in rows)
    return {
        "n":count,"wins":successes,
        "hit_rate":round(successes/count,4),
        "average_predicted":round(sum(row[0] for row in rows)/count,4),
        "brier":round(sum((row[0]-row[1])**2 for row in rows)/count,5),
        "wilson_95":wilson_interval(successes,count),
    }


def audit(index,model,calibration,rho,*,year=2026,max_matches=2000,
          baseline_calibration=None,quality_policy=None,start_date=None,end_date=None,
          prior_model=None,prior_calibration=None):
    by_group=defaultdict(list)
    by_league=defaultdict(list)
    baseline=defaultdict(list)
    baseline_calibrated=defaultdict(list)
    probability_buckets=defaultdict(list)
    prior_probabilities=[]
    zero_home,zero_away=[],[]
    poisson_zero_home,poisson_zero_away=[],[]
    zero_joint=[]
    four_models=defaultdict(list)
    counters=Counter()
    selected=[]
    for _stamp, match in index.global_games:
        kickoff=fixture_datetime(match).date()
        if kickoff.year!=year or (start_date and kickoff<start_date) or (end_date and kickoff>end_date):
            continue
        selected.append(match)
    selected.sort(key=lambda e:(e['event_date'],str(e['id'])))
    counters['period_finished']=len(selected)
    if len(selected)>max_matches:
        selected=[selected[int(i*len(selected)/max_matches)] for i in range(max_matches)]
    for match in selected:
        counters["checked"]+=1
        expected,reason=estimate_goals(match,index)
        if expected is None:
            counters["skipped_"+reason]+=1
            continue
        if quality_policy is not None:
            reject=quality_policy.check_fixture(expected)
            if reject:
                counters['skipped_'+reject]+=1
                continue
        # Ne pas attribuer au classifieur specialise un repli Poisson faute de donnees.
        if (not any((model.blend>0,model.team_blend>0,model.league_blend>0,model.zero_blend>0,
                     model.ensemble_model is not None and model.ensemble_model.weights[0]<1.))
                or btts_features(match,index) is None):
            counters['skipped_no_active_btts_specialist']+=1
            continue
        original={c.key:c for c in markets_from_matrix(score_matrix(expected["home"],expected["away"],rho))}
        updated={c.key:c for c in btts_candidates(match,index,list(original.values()),model)}
        if quality_policy is not None:
            veto=btts_quality_rejection(expected,model,original['BTTS_YES'].probability,
                                         updated['BTTS_YES'].probability)
            if veto:
                counters['skipped_'+veto]+=1
                continue
        scores=outcome_scores(match)
        win_yes=int(scores[0]>0 and scores[1]>0)
        # Record the unchanged pre-H2H reference on precisely the same
        # quality-eligible cohort. Apply the new gate only after this record.
        pre_yes=calibration.score(updated["BTTS_YES"])[1]
        pre_no=calibration.score(updated["BTTS_NO"])[1]
        preferred="BTTS_YES" if pre_yes>=pre_no else "BTTS_NO"
        pre_confidence=max(pre_yes,pre_no)
        pre_hit=win_yes if preferred=="BTTS_YES" else 1-win_yes
        counters["before_h2h_n"]+=1
        counters["before_h2h_wins"]+=pre_hit
        for threshold in (50,55,60,65,70,75,79,80):
            if pre_confidence>=threshold/100:
                counters["pre_h2h_"+str(threshold)+"_n"]+=1
                counters["pre_h2h_"+str(threshold)+"_wins"]+=pre_hit
        passed,h2h_reason,_meeting=btts_h2h_decision(match,index,preferred)
        if not passed:
            counters["skipped_"+h2h_reason]+=1
            continue
        ensemble=getattr(model,"ensemble_model",None)
        if ensemble is not None:
            candidates=ensemble.candidate_probs(match,index,expected)
            if candidates:
                for family,prob in candidates.items():
                    if prob is not None:
                        four_models[family].append((prob,win_yes))
        if getattr(model,"zero_model",None) is not None:
            zero=model.zero_model.predict(match,index,expected)
            if zero is not None:
                zero_home.append((zero["home_blank"],int(scores[0]==0)))
                zero_away.append((zero["away_blank"],int(scores[1]==0)))
                poisson_zero_home.append((exp(-expected["home"]),int(scores[0]==0)))
                poisson_zero_away.append((exp(-expected["away"]),int(scores[1]==0)))
                zero_joint.append((zero["btts_yes"],win_yes))
        if prior_model is not None and prior_calibration is not None:
            prior={c.key:c for c in btts_candidates(match,index,list(original.values()),prior_model)}
            prior_probabilities.append((prior_calibration.score(prior['BTTS_YES'])[1],win_yes))
        syes=calibration.score(updated['BTTS_YES'])[1]
        sno=calibration.score(updated['BTTS_NO'])[1]
        winner='BTTS_YES' if syes>=sno else 'BTTS_NO'
        confidence=max(syes,sno)
        selected_hit=win_yes if winner=='BTTS_YES' else 1-win_yes
        counters['direction_wins']+=selected_hit
        counters['direction_checked']+=1
        for threshold in (0.50,0.55,0.60,0.65,0.70,0.75,0.79,0.80):
            if confidence>=threshold:
                label='confidence_'+str(int(threshold*100))
                counters[label+'_n']+=1
                counters[label+'_wins']+=selected_hit
        for key,win in (("BTTS_YES",win_yes),("BTTS_NO",1-win_yes)):
            _,p,n=calibration.score(updated[key])
            by_group[key].append((p,win))
            baseline[key].append((original[key].probability,win))
            if baseline_calibration is not None:
                _lo,reference_p,_n=baseline_calibration.score(original[key])
                baseline_calibrated[key].append((reference_p,win))
            probability_buckets[(key,int(p*10))].append((p,win))
            by_league[(league_key(match),key)].append((p,win))
        counters["evaluated"]+=1
    results={
        "year":year,"start_date":str(start_date) if start_date else None,
        "end_date":str(end_date) if end_date else None,
        "population_finished":counters['period_finished'],
        "checked":counters["checked"],"eligible":counters["evaluated"],
        "strict_quality_enabled":quality_policy is not None,
        "specialist_only":True,
        "classification_accuracy":(round(counters['direction_wins']/counters['direction_checked'],4)
                                  if counters['direction_checked'] else None),
        "by_minimum_confidence":{
            str(k):{'n':counters['confidence_'+str(k)+'_n'],
                    'wins':counters['confidence_'+str(k)+'_wins'],
                    'hit_rate':(round(counters['confidence_'+str(k)+'_wins']/counters['confidence_'+str(k)+'_n'],4)
                                if counters['confidence_'+str(k)+'_n'] else None)}
            for k in (50,55,60,65,70,75,79,80)},
        "preprice_only":True,
        "last_h2h_strict_filter_enabled":True,
        "pre_last_h2h_selection":{
            "eligible":counters["before_h2h_n"],
            "wins":counters["before_h2h_wins"],
            "hit_rate":(round(counters["before_h2h_wins"]/counters["before_h2h_n"],4)
                        if counters["before_h2h_n"] else None),
            "thresholds":{
                str(threshold):{
                    "n":counters["pre_h2h_"+str(threshold)+"_n"],
                    "wins":counters["pre_h2h_"+str(threshold)+"_wins"],
                    "hit_rate":(
                        round(counters["pre_h2h_"+str(threshold)+"_wins"]/
                              counters["pre_h2h_"+str(threshold)+"_n"],4)
                        if counters["pre_h2h_"+str(threshold)+"_n"] else None)
                } for threshold in (50,55,60,65,70,75,79,80)
            },
        },
        "same_btts_eligibility_as_production":quality_policy is not None,
        "does_not_simulate_competing_markets_or_odds":True,
        "h2h_side": "highest_calibrated_btts_yes_or_no",
        "ablation_without_team_league_zero":_statistics(prior_probabilities) if prior_probabilities else None,
        "four_model_shadow":{k:_statistics(v) for k,v in four_models.items()},
        "four_ensemble_weights":model.ensemble_model.to_dict()["weights"] if model.ensemble_model else None,
        "zero_model_shadow":{
            "home_blank":_statistics(zero_home),
            "away_blank":_statistics(zero_away),
            "home_blank_poisson":_statistics(poisson_zero_home),
            "away_blank_poisson":_statistics(poisson_zero_away),
            "btts_yes_uncalibrated":_statistics(zero_joint),
        },
        "skips":{k:v for k,v in counters.items() if k.startswith("skipped_")},
        "specialized_calibrated":{k:_statistics(v) for k,v in by_group.items()},
        "poisson_dixon_coles_baseline":{k:_statistics(v) for k,v in baseline.items()},
        "baseline_calibrated":{k:_statistics(v) for k,v in baseline_calibrated.items()},
        "by_probability_bucket":{k+"|"+str(bucket):_statistics(rows)
                                 for (k,bucket),rows in probability_buckets.items()
                                 if len(rows)>=20},
        "by_league":{k+"|"+side:_statistics(rows) for (k,side),rows in by_league.items()
                     if len(rows)>=20},
        "limitations":"Historical holdout, not a real-odds backtest. No inferred ROI. "
                      "BTTS calibration and classifier were trained only on previous years.",
    }
    return results


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--max-test",type=int,default=2000)
    parser.add_argument('--start-date',default='2026-01-01')
    parser.add_argument('--end-date',default='2026-11-02')
    parser.add_argument('--legacy-no-quality-filter',action='store_true',
                        help='Only for comparison, still excludes Poisson fallback')
    parser.add_argument("--output",default="bsd/v2_btts_backtest.json")
    args=parser.parse_args()
    if not 1<=args.max_test<=50000:parser.error("Invalid match limit")
    start_date=date.fromisoformat(args.start_date)
    end_date=date.fromisoformat(args.end_date)
    if not (date(2026,1,1)<=start_date<=end_date<=date(2026,11,2)):
        parser.error('Only completed 2026 dates through 2026-11-02 are supported')
    matches=_read_json(MATCHES_FILE,None)
    if not isinstance(matches,list) or not matches:parser.error("BSD archive not restored")
    index=V2History(matches)
    rho,_=fit_rho_2024(index)
    model,training=fit_btts_model(index,rho=rho)
    cal,policy,periods=fit_policy(index,rho=rho,btts_model=model)
    baseline_cal,_,_=fit_policy(index,rho=rho,btts_model=None)
    prior_model=prior_cal=None
    ensemble_active=(model.ensemble_model is not None and model.ensemble_model.weights[0]<1.)
    if model.team_blend>0 or model.league_blend>0 or model.zero_blend>0 or ensemble_active:
        prior_model=replace(model,team_blend=0.,league_blend=0.,zero_blend=0.,ensemble_model=None)
        prior_cal,_,_=fit_policy(index,rho=rho,btts_model=prior_model)
    result={"model":"btts-specialized-v1","fit":training,"calibration":periods,
            "test":audit(index,model,cal,rho,max_matches=args.max_test,
                         prior_model=prior_model,prior_calibration=prior_cal,
                         quality_policy=None if args.legacy_no_quality_filter else policy,
                         start_date=start_date,end_date=end_date,
                         baseline_calibration=baseline_cal)}
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("BSD_BTTS_BACKTEST:",json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    main()
