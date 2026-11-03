"""Historique BTTS Oui / Non, indépendamment du marché vainqueur de BSD V2.

2024: modèles spécialisés et rho ; 2025 Jan-Aug: calibration ;
2025 Sep-Dec: contrôle qualité. 2026: TEST STRICTEMENT HORS ÉCHANTILLON.

Les données des matchs 2026 sont utilisées UNIQUEMENT pour scorer les
prévisions chronologiques calculées avec les données connues avant le match.
Ne jamais appeler une cote indicative un prix bookmaker vérifié.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import timedelta, datetime, timezone
from math import log, sqrt
from pathlib import Path
from statistics import mean,median

from bsd_archive import MATCHES_FILE,_read_json
from bsd_v2_core import (
    V2History,fixture_datetime,outcome_scores,estimate_goals,score_matrix,
    markets_from_matrix,choose_market,classify_quality_category,predict_v2,fit_rho_2024,
)
from bsd_v2_btts import fit_btts_model,btts_candidates
from bsd_v2_over_under import fit_total_model
from bsd_v2_double_chance import fit_model as fit_double_chance_model
from bsd_v2_policies import fit_policy
from bsd_v2_new_market_model import fit_extra_market_model
from bsd_v2_guardrails import MIN_CONSERVATIVE_BY_FAMILY,V21_MIN_OVER15_CONSERVATIVE
from bsd_v2_publication_policy import eligible_model_choice
from bsd_v2_estimated_odds import DEFAULT_OVERROUND

KEYS=("BTTS_YES","BTTS_NO")
THRESHOLDS=(.50,.55,.60,.65,.70,.75,.79,.80,.85,.90)
BINS=((.0,.50),(.50,.55),(.55,.60),(.60,.65),(.65,.70),(.70,.75),
      (.75,.79),(.79,.80),(.80,.85),(.85,.90),(.90,1.01))

def wilson(successes,n,z=1.96):
    if not n:return None
    p=successes/n
    denom=1+z*z/n
    centre=(p+z*z/(2*n))/denom
    diff=z*sqrt((p*(1-p)+z*z/(4*n))/n)/denom
    return [round(max(0,centre-diff),4),round(min(1,centre+diff),4)]

def summarize(rows):
    n=len(rows)
    if not n:
        return {"n":0,"wins":0,"losses":0,"hit_rate":None,"wilson95":None,
                "mean_forecast":None,"calibration_gap_pp":None,
                "brier":None,"mean_absolute_error":None,"mean_no_floor_model_odds":None,
                "pct_fair_margin6_odds_at_least_120":None}
    wins=sum(row["won"] for row in rows)
    p=[row["probability"] for row in rows]
    obs=[row["won"] for row in rows]
    errors=[x-y for x,y in zip(p,obs)]
    return {"n":n,"wins":wins,"losses":n-wins,
            "hit_rate":round(wins/n,4),
            "wilson95":wilson(wins,n),
            "mean_forecast":round(mean(p),4),
            "calibration_gap_pp":round(100*mean(errors),2),
            "brier":round(mean(e*e for e in errors),5),
            "mean_absolute_error":round(mean(abs(e) for e in errors),5),
            "mean_no_floor_model_odds":round(mean(row["honest_indicative_odds"] for row in rows),3),
            "pct_fair_margin6_odds_at_least_120":round(
                100*sum(row["honest_indicative_odds"]>=1.20 for row in rows)/n,2)}

def run(history, *, start="2026-01-01",end="2026-11-03",max_matches=0):
    index=V2History(history)
    rho,rho_details=fit_rho_2024(index)
    btts_model,btts_details=fit_btts_model(index,rho=rho)
    totals_model,total_details=fit_total_model(index,rho=rho)
    dc_model,dc_details=fit_double_chance_model(index,rho=rho)
    cal,policy,quality_details=fit_policy(
        index,rho=rho,btts_model=btts_model,total_model=totals_model,dc_model=dc_model)
    extra_model=fit_extra_market_model(index,rho=rho)
    dates=[]
    for _,fixture in index.global_games:
        dt=fixture_datetime(fixture)
        if start<=dt.date().isoformat()<=end:
            dates.append(fixture)
    dates.sort(key=lambda x:(x.get("event_date") or "",str(x.get("id"))))
    full_count=len(dates)
    if max_matches:
        dates=dates[:max_matches]
    diag=Counter()
    per_match=[]
    family_adj=policy.family_uncertainty_adjustments().get("btts",0.)
    for e in dates:
        diag["finished_2026_considered"]+=1
        feat,reason=estimate_goals(e,index)
        if feat is None:
            diag["no_prematch_model_"+str(reason)]+=1
            continue
        actual=outcome_scores(e)
        if actual is None:
            diag["final_score_unavailable"]+=1
            continue
        fixture_policy_reason=policy.check_fixture(feat)
        matrix=score_matrix(feat["home"],feat["away"],rho)
        candidates=btts_candidates(e,index,markets_from_matrix(matrix),btts_model)
        chosen_btts=[c for c in candidates if c.key in KEYS]
        if len(chosen_btts)!=2:
            diag["missing_btts_candidates"]+=1
            continue
        # Ask the actual production ranking/calibration for uncertainty
        # while bypassing its universal 70% *preselection* cutoff for audit.
        top,btts_rank=choose_market(
            chosen_btts,calibration=cal,min_probability=0.0,
            league_samples=feat["league_samples"],
            form_samples=min(feat["home_recent_matches"],feat["away_recent_matches"]),
            family_adjustments={"btts":family_adj},
            family_minimums=MIN_CONSERVATIVE_BY_FAMILY,
        )
        lookup={row["candidate"].key:row for row in btts_rank}
        if len(lookup)!=2:
            diag["ranked_btts_incomplete"]+=1
            continue
        fixture_only={k:v for k,v in e.items() if k not in (
            "home_score","away_score","ht_home_score","ht_away_score",
            "home_ht_score","away_ht_score","half_time_home_score","half_time_away_score")}
        fixture_only["status"]="notstarted"
        production,prod_reason=predict_v2(
            fixture_only,index,calibration=cal,rho=rho,
            clock=fixture_datetime(e)-timedelta(seconds=1),
            quality_policy=policy,btts_model=btts_model,
            total_model=totals_model,dc_model=dc_model,
            excluded_keys={"12","UNDER_45"},
            selection_conservative_minimums={"OVER_15":V21_MIN_OVER15_CONSERVATIVE},
            extra_market_model=extra_model,
        )
        if production is None:
            diag["production_no_choice_"+str(prod_reason)]+=1
            ranked_keys=[]
            winner_key=None
        else:
            ranked_keys=[r["key"] for r in production["ranked_candidates"]
                         if r.get("passes_quality_policy") is True]
            winner_key=(production.get("prediction") or {}).get("key")
            diag["production_has_primary"]+=1
        quality_pass=fixture_policy_reason is None
        if quality_pass:
            diag["fixture_quality_passed"]+=1
        else:
            diag["fixture_quality_"+str(fixture_policy_reason)]+=1
        for code in KEYS:
            row=lookup[code]
            p=row["calibrated_probability"]
            conservative=row["ranking_confidence"]
            market_good=policy.check_market(row) is None
            category=classify_quality_category(conservative,feat)
            model_eligible=eligible_model_choice({"category":category,"prediction":{"probability":p}})
            # This is the actual model pricing math without the 1.20 uplift
            # that was identified in the production price-floor investigation.
            honest=round(1/(p*(1+DEFAULT_OVERROUND)),3)
            record={
                "id":str(e["id"]),"date":fixture_datetime(e).date().isoformat(),
                "home_team":e.get("home_team"),"away_team":e.get("away_team"),
                "league":e.get("league_name") or e.get("league"),
                "market":code,"won":int((actual[0]>0 and actual[1]>0) == (code=="BTTS_YES")),
                "score_home":actual[0],"score_away":actual[1],
                "probability":round(p,6),"conservative_probability":round(conservative,6),
                "category":category,"model_quality_fixture":quality_pass,
                "market_quality_pass":market_good,
                "football_eligible_79":bool(quality_pass and market_good and model_eligible),
                "honest_indicative_odds":honest,
                "indicator_reaches_min120":honest>=1.20,
                "production_primary":winner_key==code,
                "production_rank":ranked_keys.index(code)+1 if code in ranked_keys else None,
                "in_production_ranked_quality_options":code in ranked_keys,
                "btts_specialist_blend":btts_model.blend,
                "market_status":"qualified" if quality_pass and market_good else "quality_rejected",
            }
            per_match.append(record)
    diag["total_rows"]=len(per_match)
    report={
       "schema":"btts-independent-2026-out-of-sample-1",
       "period":{"start":start,"end":end,"finished_fixtures_in_archive":full_count,
                 "analyzed_fixtures":len({x["id"] for x in per_match}),
                 "truncated":len(dates)<full_count},
       "training":{"rho_2024":rho_details,"btts_2024":btts_details,
                   "total_2024":total_details,"double_chance_2024":dc_details,
                   "market_calibration_and_validation_2025":quality_details,
                   "new_family_2025":extra_model.to_dict()},
       "scope":"Each BTTS side on every verified 2026 finished fixture, independent of production winner",
       "metrics":{
         "by_side":{},
         "rank_competition":{},
         "counts":dict(diag),
       },
       "limitations":[
          "2026 final scores are never used to train any model, only to grade predictions.",
          "Point-in-time features use only matches available at least 4 hours before kickoff.",
          "Historical bookmaker quotes are unavailable; no real-bet ROI can be inferred.",
          "Thresholds below 79% are diagnostic sensitivity tests and are not production authorization.",
          "Model-indicative prices use fixed 6% WITHOUT artificial uplift to 1.20.",
          "Production pre-price rank is reproduced with 2025-trained models, but live circuit breaker / actual historical price snapshots are not reconstructible.",
          "Outcomes are a historical sample, not a guarantee of future accuracy.",
       ],
    }
    for side in KEYS:
        rows=[x for x in per_match if x["market"]==side]
        quality=[x for x in rows if x["model_quality_fixture"] and x["market_quality_pass"]]
        eligible=[x for x in quality if x["football_eligible_79"]]
        report["metrics"]["by_side"][side]={
            "all_with_model":summarize(rows),
            "quality_passed":summarize(quality),
            "football_eligible_79":summarize(eligible),
            "football_eligible_79_and_model_price_above_120":summarize(
                [x for x in eligible if x["indicator_reaches_min120"]]),
            "threshold_sensitivity":{
                str(int(100*threshold))+"pct":{
                    "all":summarize([x for x in rows if x["probability"]>=threshold]),
                    "quality_passed":summarize([x for x in quality if x["probability"]>=threshold]),
                } for threshold in THRESHOLDS
            },
            "probability_buckets":{
                f"{int(100*low)}-{int(100*high)}%":
                    summarize([x for x in quality if low<=x["probability"]<high])
                for low,high in BINS
            },
        }
    eligible=[x for x in per_match if x["football_eligible_79"]]
    report["metrics"]["rank_competition"]={
        "eligible_btts_match_market_pairs":len(eligible),
        "eligible_btts_distinct_fixtures":len({x["id"] for x in eligible}),
        "eligible_btts_also_primary_before_pricing":sum(x["production_primary"] for x in eligible),
        "eligible_btts_in_top3_preprice":sum(
            x["production_rank"] is not None and x["production_rank"]<=3 for x in eligible),
        "eligible_btts_not_top_primary":sum(not x["production_primary"] for x in eligible),
        "eligible_btts_not_in_qualified_ranked":sum(
            not x["in_production_ranked_quality_options"] for x in eligible),
        "all_btts_primary_count":sum(x["production_primary"] for x in per_match),
        "all_btts_in_top3":sum(
            x["production_rank"] is not None and x["production_rank"]<=3 for x in per_match),
    }
    return report,per_match

def markdown(report):
    stats=report["metrics"]["by_side"]
    period=report["period"]
    out=["# Backtest indépendant BTTS Oui / Non — BSD V2",
         "","**Période hors échantillon :** "+period["start"]+" au "+period["end"]+
         " (scores finaux vérifiés, 2026).",
         "","**Entraînement :** 2024 ; calibration et qualité : 2025 ;",
         "**évaluation uniquement :** 2026.","",
         "## Résultats principaux","",
         "| Marché | Matches avec modèle | Succès observés | Après qualité | Éligibles ≥79% Pro/VIP | Gagnés / Éligibles |",
         "|---|---:|---:|---:|---:|---:|"]
    for key in KEYS:
        d=stats[key];a=d["all_with_model"];q=d["quality_passed"];e=d["football_eligible_79"]
        out.append(f"| {key} | {a['n']} | {a['wins']}/{a['n']} ({round(100*a['hit_rate'],2) if a['hit_rate'] is not None else '—'} %) | {q['n']} | {e['n']} | {e['wins']}/{e['n']} |")
    out += ["","## Sensibilité du seuil, après filtres de qualité","","| Seuil de confiance calibrée | BTTS Oui : nombre | Oui : réussite | BTTS Non : nombre | Non : réussite |",
            "|---|---:|---:|---:|---:|"]
    for t in THRESHOLDS:
        a=stats["BTTS_YES"]["threshold_sensitivity"][str(int(t*100))+"pct"]["quality_passed"]
        b=stats["BTTS_NO"]["threshold_sensitivity"][str(int(t*100))+"pct"]["quality_passed"]
        ar="—" if a["hit_rate"] is None else str(round(100*a["hit_rate"],2))+" %"
        br="—" if b["hit_rate"] is None else str(round(100*b["hit_rate"],2))+" %"
        out.append(f"| {int(t*100)} % | {a['n']} | {ar} | {b['n']} | {br} |")
    comp=report["metrics"]["rank_competition"]
    out += ["","## Pourquoi sont-ils rares parmi les pronostics publiés ?","",
       "- BTTS remplissant indépendamment les règles 79 % et qualité : **"+str(comp["eligible_btts_match_market_pairs"])+"**.",
       "- Matchs distincts contenant au moins un BTTS admissible : **"+str(comp["eligible_btts_distinct_fixtures"])+"**.",
       "- BTTS admissibles classés numéro 1 par tous les marchés : **"+str(comp["eligible_btts_also_primary_before_pricing"])+"**.",
       "- BTTS admissibles écartés du premier rang : **"+str(comp["eligible_btts_not_top_primary"])+"**.",
       "",
       "## Limites",
       "",
       "Les tests à 60–75 % mesurent la discrimination du modèle, **pas** une",
       "permission de publier sous le seuil de 79 %. Aucun prix historique",
       "bookmaker n'est reconstruit. Un taux de réussite n'est pas un rendement.",
       "La qualité statistique se juge aussi par l'écart de calibration,",
       "le score de Brier, la taille de l'échantillon et l'incertitude.",
       "","Les cotes indicatives citées sont des calculs du modèle à marge 6 %,",
       "sans relèvement artificiel à 1,20. Elles ne sont pas exécutables.",
       ""]
    return "\n".join(out)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--start",default="2026-01-01")
    ap.add_argument("--end",default="2026-11-03")
    ap.add_argument("--max-matches",type=int,default=0)
    ap.add_argument("--prefix",default="bsd/btts_independent_2026")
    args=ap.parse_args()
    hist=_read_json(MATCHES_FILE,None)
    if not isinstance(hist,list) or not hist:
        ap.error("Historical encrypted BSD archive must be restored first")
    report,rows=run(hist,start=args.start,end=args.end,max_matches=args.max_matches)
    p=Path(args.prefix)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.with_suffix(".json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    p.with_suffix(".md").write_text(markdown(report),encoding="utf8")
    # Publish ONLY aggregate threshold summaries. Historical score archives
    # remain private: individual completed games never leave the CI runner.
    keys=("market","threshold","scope","n","wins","losses","hit_rate",
          "mean_forecast","calibration_gap_pp","brier","wilson95",
          "mean_no_floor_model_odds")
    with p.with_suffix(".csv").open("w",newline="",encoding="utf8") as f:
        w=csv.DictWriter(f,fieldnames=keys)
        w.writeheader()
        for market in KEYS:
            info=report["metrics"]["by_side"][market]
            for label,rollup in (("all","all_with_model"),("quality","quality_passed"),
                                 ("production_79","football_eligible_79")):
                val=info[rollup]
                w.writerow({**{k:val.get(k) for k in keys if k in val},
                            "market":market,"threshold":("79%" if label=="production_79" else "none"),
                            "scope":label})
            for threshold,scopes in info["threshold_sensitivity"].items():
                for scope,metric in scopes.items():
                    w.writerow({**{k:metric.get(k) for k in keys if k in metric},
                                "market":market,"threshold":threshold,"scope":scope})
    print("BSD_BTTS_INDEPENDENT_SUMMARY",json.dumps({
       "period":report["period"],
       "by_side":{key:{
            "all":val["all_with_model"],
            "qualified_79":val["football_eligible_79"],
            "at_model_odds_120":val["football_eligible_79_and_model_price_above_120"]
        } for key,val in report["metrics"]["by_side"].items()},
       "market_competition":report["metrics"]["rank_competition"],
       "model":report["training"]["btts_2024"],
    },ensure_ascii=False))
if __name__=="__main__":main()
