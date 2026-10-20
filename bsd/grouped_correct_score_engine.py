"""Shadow evaluation of 1xBet observed grouped scores with dedicated Double Chance.

No production publishing; never infer bookmaker odds from a model or from
ordinary correct scores. The 2026 archive is exploratory, not genuinely blind.
"""
from __future__ import annotations
import json
from datetime import datetime,timezone
from bsd_v2_core import V2History,estimate_goals,fixture_datetime,outcome_scores
from exact_scores import matrix_for
from exact_scores_under25 import Under25Model,reweight_scores
from exact_scores_h2h import H2HIndex,h2h_signal
from bsd_v2_double_chance import fit_model
from grouped_correct_score import (template_groups,validate_1xbet_snapshot,
                                    evaluate_groups,direction_probabilities,
                                    double_chance_direction,group_hit)

FROZEN={"rho":0.,"scale_home":1.10,"scale_away":1.,
        "under_blend":1.,"under_variance_scale":.85,"under_threshold":.62}
VERSION="mrx-grouped-score-dc-shadow-2026-10-20-v1"

def fit_direction(index):
    # Dedicated BSD double-chance model; 2024-only fitting.
    model,metadata=fit_model(index,rho=FROZEN["rho"],max_training=900,
                              max_validation=250)
    return model,metadata

def analyze(fixture,index,hindex,dc_model,*,now,quote_snapshot=None,
            require_prematch=True):
    kickoff=fixture_datetime(fixture)
    if require_prematch and not now<kickoff:
        return None,"already_started"
    estimate,reason=estimate_goals(fixture,index)
    if estimate is None:
        return None,reason
    base=matrix_for(estimate["home"],estimate["away"],rho=FROZEN["rho"],
                    scale_home=FROZEN["scale_home"],
                    scale_away=FROZEN["scale_away"])
    under=Under25Model(FROZEN["under_blend"],FROZEN["under_variance_scale"],
                       FROZEN["under_threshold"]).predict(fixture,index,base)
    adjusted=reweight_scores(base,under["probability"])
    prior=direction_probabilities(base)
    dc_triple=dc_model.predict(fixture,index,(prior["1"],prior["X"],prior["2"]))
    direction=double_chance_direction(dict(zip(("1","X","2"),dc_triple)))
    h2h=h2h_signal(hindex.past_scores(fixture))
    offered=(validate_1xbet_snapshot(quote_snapshot,event_id=fixture["id"],
             kickoff=kickoff,now=now) if quote_snapshot is not None
             else template_groups())
    scored=evaluate_groups(adjusted,offered,direction=direction)
    has_verified_quotes=quote_snapshot is not None
    for entry in scored:
        confident=bool(h2h["prioritized"] and under["priority"])
        if has_verified_quotes and entry["direction_eligible"] and confident:
            entry["tier"]="recherche_prioritaire"
        elif entry["direction_eligible"] and under["priority"]:
            entry["tier"]="observation"
        else:
            entry["tier"]="non_retenu"
        # A numerical edge is not proof of bookmaker value without calibration.
        entry["research_candidate"]=(entry["direction_eligible"] and
                       entry["probability"]>=.12)
        entry["bet_recommendation"]=False
        entry["quote_required"]=not entry["available_verified"]
        entry["group_is_bookmaker_confirmed"]=has_verified_quotes
    return {"format":"mrx-1xbet-grouped-research-v1",
        "match_id":str(fixture["id"]),"kickoff_utc":kickoff.isoformat(),
        "evaluated_utc":now.isoformat(),"model":VERSION,
        "bookmaker":"1xbet","market":"Correct Score - Group Bet",
        "market_status":"fixture_quote_snapshot" if has_verified_quotes else
                         "nine_observed_groups_research_only",
        "league_key":estimate.get("league_key"),
        "goals_expected":{"home":estimate["home"],"away":estimate["away"]},
        "double_chance":direction,"under25_probability":under["probability"],
        "under25_priority":under["priority"],
        "h2h_priority":h2h["prioritized"],"h2h_meetings":h2h["meetings"],
        "groups":scored,"published":False,"experimental":True,
        "note":"No wager recommendation; all 1xBet selection availability and decimal odds must be observed pre-match."},"ok"

def settle_group_prediction(record,score):
    if not isinstance(record,dict) or record.get("published") is not False:
        raise ValueError("Research record required")
    result=tuple(int(x) for x in score)
    rows=[{"group_id":g["group_id"],"hit":int(group_hit(g["scores"],result)),
           "group_probability":g["probability"]} for g in record["groups"]]
    return {"match_id":record["match_id"],"actual_score":list(result),"groups":rows}

def selection_summary(record):
    """One selection per match by each rule; compare paired on SAME fixtures."""
    rows=record["groups"]
    benchmark=max(rows,key=lambda x:x["probability"]) if rows else None
    compliant=[x for x in rows if x["direction_eligible"]]
    directed=max(compliant,key=lambda x:x["probability"]) if compliant else None
    high_conf=[x for x in compliant if x["tier"]=="recherche_prioritaire"]
    priority=max(high_conf,key=lambda x:x["probability"]) if high_conf else None
    priceable=[x for x in high_conf if x["odds"] is not None and
               x["expected_value"] is not None and x["expected_value"]>=.03]
    value=max(priceable,key=lambda x:x["expected_value"]) if priceable else None
    return {"baseline":benchmark,"with_double_chance":directed,
            "with_h2h_under":priority,"with_verified_price":value}
