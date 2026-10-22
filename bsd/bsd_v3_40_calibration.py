"""V3 coherent, leakage-free GLOBAL goal-rate recalibration.
Train only with 2025 finished games and features known before each kickoff.
2026 is never used to choose coefficients. Calibrate goal intensities rather
than forty markets independently: preserves 1X2/BTTS/handicap coherence.
"""
from __future__ import annotations
from datetime import datetime, timezone
from dataclasses import dataclass
from math import isfinite
from bsd_v2_core import fixture_datetime, estimate_goals, outcome_scores

START=datetime(2025,1,1,tzinfo=timezone.utc)
END=datetime(2026,1,1,tzinfo=timezone.utc)
PRIOR_MATCHES=100.
LOWER,UPPER=.88,1.12

@dataclass(frozen=True)
class GoalCalibration:
    home_scale:float=1.
    away_scale:float=1.
    trained:int=0
    train_period:str="2025-01-01/2025-12-31"
    method:str="global_poisson_goal_rate_shrink_v1"

    def apply(self, home, away):
        if not all(isfinite(float(x)) and float(x)>0 for x in (home,away)):
            raise ValueError("Invalid expected goals")
        return (max(.1,min(5.,home*self.home_scale)),
                max(.1,min(5.,away*self.away_scale)))

    @property
    def applied(self):
        return self.trained>=100

    def to_dict(self):
        return {"method":self.method,"home_scale":round(self.home_scale,7),
                "away_scale":round(self.away_scale,7),
                "training_period":self.train_period,"training_samples":self.trained,
                "applied":self.applied,
                "independent_holdout_validated":False}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data,dict) or data.get("method")!=cls.method:
            raise ValueError("Invalid calibration schema")
        if data.get("training_period")!="2025-01-01/2025-12-31":
            raise ValueError("Unexpected calibration training period")
        h,a=float(data["home_scale"]),float(data["away_scale"])
        n=int(data["training_samples"])
        if not (LOWER<=h<=UPPER and LOWER<=a<=UPPER and n>=0):
            raise ValueError("Invalid V3 calibration factors")
        return cls(h,a,n)

def from_sums(*, n, actual_home, actual_away, predicted_home,predicted_away):
    if n<100:
        return GoalCalibration()
    vals=(actual_home,actual_away,predicted_home,predicted_away)
    if any(not isfinite(v) or v<=0 for v in vals):
        return GoalCalibration()
    def shrink(actual,pred):
        # Prior of 100 matches with mean forecast goals. Prevents extreme
        # ratios from noisy samples, then limits correction magnitude.
        ratio=(actual+PRIOR_MATCHES*(pred/n))/(pred+PRIOR_MATCHES*(pred/n))
        return max(LOWER,min(UPPER,ratio))
    return GoalCalibration(shrink(actual_home,predicted_home),
                           shrink(actual_away,predicted_away),n)

def fit_goal_calibration(index, max_training=700):
    if max_training<100: raise ValueError("At least 100 samples required")
    matches=[]
    for _available,e in index.global_games:
        try:
            at=fixture_datetime(e)
            if START<=at<END and outcome_scores(e) is not None:
                matches.append((at,e))
        except (ValueError,TypeError,OverflowError):
            continue
    matches.sort(key=lambda item:(item[0],str(item[1].get("id"))))
    if len(matches)>max_training:
        matches=[matches[i*len(matches)//max_training] for i in range(max_training)]
    predicted_h=predicted_a=actual_h=actual_a=0.
    count=0
    for _,event in matches:
        expected,_=estimate_goals(event,index)
        if expected is None:continue
        outcome=outcome_scores(event)
        count+=1
        predicted_h+=expected["home"]
        predicted_a+=expected["away"]
        actual_h+=outcome[0]
        actual_a+=outcome[1]
    model=from_sums(n=count,actual_home=actual_h,actual_away=actual_a,
                    predicted_home=predicted_h,predicted_away=predicted_a)
    return model,{"eligible":len(matches),"trained":count,
                  "training_period":model.train_period,
                  "method":model.method,
                  "home_ratio_before_shrink":round(actual_h/predicted_h,6) if predicted_h else None,
                  "away_ratio_before_shrink":round(actual_a/predicted_a,6) if predicted_a else None}
