"""Mr XPRONOS — standalone ONE exact-score-per-match research engine.

Forked from the group-bet research concepts, not from 1xBet market templates.
Model inputs: BSD V2 point-in-time xgoals, 2024/2025-frozen Under2.5
specialist, 2024-trained Double Chance as OPTIONAL comparison, H2H,
and recent-form diagnostics. NO dependence on grouped market groups/odds.

Each eligible match yields exactly ONE proposed full-time score. A research
priority tag is separate from the forecast and never implies guaranteed odds.
No write to data.json, no Telegram, no published bets.
"""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
from single_exact_score_research import prematch_context, rank, RANK_VERSION
from single_exact_score_advanced import advanced_prediction
from math import fsum,log
from bsd_v2_core import estimate_goals, fixture_datetime
from exact_scores import matrix_for,top_scores
from exact_scores_h2h import h2h_signal
from exact_scores_under25 import Under25Model,reweight_scores
from bsd_v2_double_chance import fit_model as fit_double_chance
from bsd_form_shift import form_shift

VERSION="mrx-single-exact-score-shadow-2026-10-20-v2-debiased11"
PARAMETERS={
    "version":VERSION,
    "rho":0.0,"scale_home":1.10,"scale_away":1.0,
    "under_blend":1.0,"under_variance_scale":0.85,"under_threshold":0.62,
    # Explicit exact-score diversity objective: 2024 Oct-Dec validation cut 1-1
    # share from 63.96% to 28.33%, at an accuracy cost of 18/5744 (0.31pp).
    # No quotas, no retroactive rewrite. Apply only to NEW predictions.
    "one_one_factor":0.80,
    "minimum_lead_minutes":30,
    # Exploratory filter, fixed before new prospective validation.
    "priority_score_probability":0.16,
    "priority_top1_margin":0.015,
    "low_entropy_cut":3.90,
    "dc_blend":1.0,  # research-only scenario; never auto-enables the DC pick
}
OUTCOMES=("1","X","2")

def outcome(score):
    h,a=score
    return "1" if h>a else "2" if a>h else "X"

def result_probabilities(matrix):
    x={k:0.0 for k in OUTCOMES}
    for score,p in matrix.items():
        x[outcome(score)]+=p
    total=fsum(x.values())
    if total<=0:raise ValueError("Invalid 1X2 distribution")
    return {k:x[k]/total for k in OUTCOMES}

def direction_adjusted(matrix,desired,*,blend=1.0):
    """Preserve conditional exact-score probabilities inside 1/X/2.

    This is a backtestable experimental alternative, not necessarily superior.
    Never multiply score probabilities by 1X/2X: overlapping 2-way markets
    are NOT three mutually exclusive outcomes.
    """
    if len(desired)!=3:raise ValueError("Expected mutually exclusive 1/X/2 probabilities")
    desired=tuple(float(x) for x in desired)
    if any(x<0 or x>1 for x in desired) or abs(sum(desired)-1)>1e-5:
        raise ValueError("Invalid 1/X/2 vector")
    prior=result_probabilities(matrix)
    target={k:(1-blend)*prior[k]+blend*desired[i] for i,k in enumerate(OUTCOMES)}
    if any(prior[k]<=0 and target[k]>0 for k in OUTCOMES):
        raise ValueError("Cannot expand zero-probability outcome")
    adjusted={score:p*target[outcome(score)]/prior[outcome(score)]
              for score,p in matrix.items()}
    total=fsum(adjusted.values())
    if abs(total-1)>1e-5:raise ValueError("Reweighting is not normalized")
    return adjusted

def debias_one_one(matrix,*,factor=.80):
    """Penalize ONLY the 1-1 score cell, then renormalize all score probabilities.

    Does not force an arbitrary replacement: the most likely remaining score
    wins naturally. All matrices remain proper normalized distributions.
    """
    if not 0 < factor <= 1:
        raise ValueError("1-1 factor must be in (0,1]")
    total=fsum(p*(factor if score==(1,1) else 1.)
               for score,p in matrix.items())
    if not total>0:raise ValueError("Empty score matrix")
    return {score:p*(factor if score==(1,1) else 1.)/total
            for score,p in matrix.items()}

def score_choice(matrix):
    top=top_scores(matrix,count=2)
    if len(top)<2:raise ValueError("At least two possible scores required")
    (score,p),(runner,second)=top
    return {"score":list(score),"probability":round(p,7),
            "margin":round(p-second,7),
            "runner_up_probability":round(second,7)}

def entropy(matrix):
    return -fsum(p*log(p) for p in matrix.values() if p>0)

def forecast(fixture,index,hindex,*,now,dc_model=None,require_prematch=True,
             compute_form=True,advanced_model=None,context_model=None):
    kickoff=fixture_datetime(fixture)
    if require_prematch and kickoff<=now+timedelta(minutes=PARAMETERS["minimum_lead_minutes"]):
        return None,"too_close_or_started"
    if require_prematch and str(fixture.get("status","")).lower() in (
            "finished","cancelled","canceled","abandoned","postponed"):
        return None,"not_upcoming"
    expected,reason=estimate_goals(fixture,index)
    if expected is None:return None,reason

    base=matrix_for(expected["home"],expected["away"],rho=PARAMETERS["rho"],
                    scale_home=PARAMETERS["scale_home"],
                    scale_away=PARAMETERS["scale_away"])
    under=Under25Model(PARAMETERS["under_blend"],
                       PARAMETERS["under_variance_scale"],
                       PARAMETERS["under_threshold"]).predict(fixture,index,base)
    adjusted=reweight_scores(base,under["probability"])
    debiased=debias_one_one(adjusted,factor=PARAMETERS["one_one_factor"])
    baseline=score_choice(base)
    under_choice=score_choice(adjusted)
    selected=score_choice(debiased)

    prior=result_probabilities(base)
    p_dc=None
    dc_choice=None
    direction="unavailable"
    if dc_model is not None:
        p_dc=tuple(dc_model.predict(fixture,index,
                                   tuple(prior[k] for k in OUTCOMES)))
        trial=direction_adjusted(adjusted,p_dc,blend=PARAMETERS["dc_blend"])
        dc_choice=score_choice(trial)
        best=max(range(3),key=lambda i:p_dc[i])
        direction=OUTCOMES[best]

    signal=h2h_signal(hindex.past_scores(fixture))
    # Diagnostic only: never veto/force an exact score from a retrospective
    # form rule which failed to improve the grouped research.
    form=None
    if compute_form:
        form=form_shift(fixture,index,hindex,expected=expected,
                        under25=under["probability"],include_h2h=signal["prioritized"])
    can_prioritize=(selected["probability"]>=PARAMETERS["priority_score_probability"]
                    and selected["margin"]>=PARAMETERS["priority_top1_margin"])
    low_entropy=entropy(debiased)<=PARAMETERS["low_entropy_cut"]
    high_priority=bool(can_prioritize and low_entropy)
    # Advanced branch is a separate research score: immutable legacy scores stay identical.
    advanced=(advanced_prediction(fixture,index,advanced_model,now=now,
                                  expected=expected,context_model=context_model)
              if advanced_model is not None else None)
    # Rank the actual ONE-score pick only, without any result labels.
    selection_rank=rank({"variants":{**{"original":baseline,
                          "under25_fusion":under_choice,"debiased_11":selected,
                          "optional_dc_fusion":dc_choice},
                          "advanced_2024":advanced["choice"] if advanced else None},
                         "quality":{k:expected.get(k) for k in
                             ("home_recent_matches","away_recent_matches")}},
                        "debiased_11")
    # Does NOT claim confidence calibration; prioritization is a research filter.
    return {
        "format":"mrx-single-exact-score-v1",
        "model":VERSION,"experimental":True,"published":False,
        "match_id":str(fixture["id"]),
        "kickoff_utc":kickoff.isoformat(),"forecast_utc":now.isoformat(),
        "score":selected["score"],
        "primary_model":"under25_debiased_11_v2",
        "advanced_model_used_for_primary":False,
        "estimated_score_probability":selected["probability"],
        "one_one_factor":PARAMETERS["one_one_factor"],
        "score_margin":selected["margin"],
        "selection_rank":round(selection_rank,9),
        "rank_version":RANK_VERSION,
        "one_score_only":True,
        "research_priority":high_priority,
        "expected_goals":{"home":expected["home"],"away":expected["away"]},
        "total_expected_goals":round(expected["home"]+expected["away"],5),
        "data_quality":{k:expected.get(k) for k in ("home_recent_matches","away_recent_matches","home_venue_matches","away_venue_matches","league_samples","max_last_match_age_days")},
        "prematch_context":prematch_context(fixture,now,kickoff),
        "under25_probability":round(under["probability"],7),
        "h2h_low_stable":bool(signal["prioritized"]),
        "h2h_meetings":signal["meetings"],
        "form_risk":None if not form or not form.get("valid") else {
            "upward_scoring_risk":form["upward_scoring_risk"],
            "positive_drift_components":form["positive_drift_components"]},
        "one_x_two":{k:round(prior[k],7) for k in OUTCOMES},
        "double_chance_advisory":{
            "direction":direction,
            "one_x_two":None if p_dc is None else
                  {k:round(p_dc[i],7) for i,k in enumerate(OUTCOMES)},
            "applied_to_published_pick":False,
        },
        "advanced_research":advanced,
        "ablation":{
            "original":baseline,
            "under25_fusion":under_choice,
            "debiased_11":selected,
            "optional_dc_fusion":dc_choice,
        },
        "estimated_entropy":round(entropy(debiased),5),
        "disclaimer":"One proposed score, estimated chance; not a guaranteed outcome or a bookmaker quote.",
    },"ok"

def train_dc(index):
    return fit_double_chance(index,rho=PARAMETERS["rho"],
                             max_training=900,max_validation=250)
