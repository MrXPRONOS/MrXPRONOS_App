"""V3-specific goal-strength challenger using strictly past Elo snapshots.

2025 Jan-Aug: hyperparameter fit. 2025 Sep-Dec: acceptance gate.
A challenger with no measured improvement stays inactive (alpha = 0).
"""
from __future__ import annotations
from dataclasses import dataclass
from math import exp,fsum
from .legacy import (estimate_goals,fixture_datetime,outcome_scores,
                     score_matrix,markets_from_matrix,realized)
from bsd_h2h import _team_id

ALPHAS=(0.,.06,.12,.18,.24)
FAMILIES=("result","goals","btts","double_chance")

def _bounded(value,low,high):
    return max(low,min(high,value))

def goal_strength(event,index,expected,alpha):
    if not alpha:
        return dict(expected)
    from bsd_v2_double_chance import _rating
    home=_team_id(event,"home")
    away=_team_id(event,"away")
    if home is None or away is None:
        return dict(expected)
    now=fixture_datetime(event)
    elo_delta=(_rating(index,home,now)-_rating(index,away,now))/400.
    elo_delta=_bounded(elo_delta,-2.,2.)
    multiplier=exp(alpha*elo_delta)
    features=dict(expected)
    features["home"]=_bounded(float(expected["home"])*multiplier,.35,3.50)
    features["away"]=_bounded(float(expected["away"])/multiplier,.35,3.50)
    features["goal_strength_applied"]=True
    features["elo_delta_scaled"]=round(elo_delta,5)
    return features

@dataclass(frozen=True)
class GoalStrengthModel:
    alpha: float
    trained: int
    validated: int
    base_validation_brier: float | None
    selected_validation_brier: float | None
    validation_by_family: dict
    reason: str

    def apply(self,event,index,expected):
        return goal_strength(event,index,expected,self.alpha)

    def metadata(self):
        return {"alpha":self.alpha,"trained":self.trained,
                "validated":self.validated,
                "base_validation_brier":self.base_validation_brier,
                "selected_validation_brier":self.selected_validation_brier,
                "validation_by_family":self.validation_by_family,
                "reason":self.reason,
                "fit_period":"2025-01 to 2025-08",
                "gate_period":"2025-09 to 2025-12",
                "activation_requires_prospective_confirmation":True}

def fit_goal_strength(index,rho,*,calibration=None,max_train=800,
                      max_validation=500,min_train=80,min_validation=50,
                      min_improvement=.0001,max_family_regression=.004):
    matches=[e for _,e in index.global_games if fixture_datetime(e).year==2025]
    matches.sort(key=lambda e:(fixture_datetime(e),str(e.get("id"))))
    train=[e for e in matches if fixture_datetime(e).month<=8][:max_train]
    validation=[e for e in matches if fixture_datetime(e).month>=9][:max_validation]
    snapshots={}
    for split_name,events in (("train",train),("validation",validation)):
        total={alpha:0. for alpha in ALPHAS}
        groups={alpha:{family:0. for family in FAMILIES} for alpha in ALPHAS}
        count=0
        for event in events:
            features,_=estimate_goals(event,index)
            if features is None:continue
            scores=outcome_scores(event)
            try:
                snapshots_for_event={}
                for alpha in ALPHAS:
                    adjusted=goal_strength(event,index,features,alpha)
                    matrix=score_matrix(adjusted["home"],adjusted["away"],rho)
                    if calibration is not None:
                        matrix=calibration.apply(matrix)
                    candidates=markets_from_matrix(matrix)
                    family_loss={}
                    for family in FAMILIES:
                        family_rows=[c for c in candidates if c.family==family]
                        family_loss[family]=fsum(
                            (c.probability-realized(c,*scores))**2 for c in family_rows)/len(family_rows)
                    snapshots_for_event[alpha]=family_loss
                for alpha,by_family in snapshots_for_event.items():
                    for family,error in by_family.items():
                        groups[alpha][family]+=error
                    total[alpha]+=fsum(by_family.values())/len(FAMILIES)
                count+=1
            except (ValueError,TypeError,ArithmeticError):
                continue
        snapshots[split_name]={"count":count,"losses":{
            alpha:total[alpha]/count if count else None for alpha in ALPHAS},
            "family":{alpha:{family:groups[alpha][family]/count if count else None
                             for family in FAMILIES} for alpha in ALPHAS}}
    trained=snapshots["train"]["count"]
    validated=snapshots["validation"]["count"]
    tr=snapshots["train"];va=snapshots["validation"]
    if trained<min_train or validated<min_validation:
        return GoalStrengthModel(0.,trained,validated,va["losses"][0.],None,{},
                                 "insufficient_train_or_validation")
    best=min(ALPHAS,key=lambda a:tr["losses"][a])
    family_comparison={}
    for family in FAMILIES:
        base=va["family"][0.][family]
        challenged=va["family"][best][family]
        family_comparison[family]={
            "baseline":round(base,6),"challenger":round(challenged,6),
            "degradation":round(challenged-base,6)}
    accepted=(best>0 and tr["losses"][best]+min_improvement<tr["losses"][0.]
              and va["losses"][best]+min_improvement<va["losses"][0.]
              and all(row["degradation"]<=max_family_regression
                      for row in family_comparison.values()))
    return GoalStrengthModel(
        best if accepted else 0.,trained,validated,
        round(va["losses"][0.],7),round(va["losses"][best],7),
        family_comparison,
        "validated" if accepted else "no_robust_holdout_gain")
