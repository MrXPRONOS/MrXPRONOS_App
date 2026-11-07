"""Specialized BTTS NO classifier for BSD V3.

The model predicts the event "at least one team fails to score" directly,
instead of taking 1 - BTTS YES. All inputs are point-in-time and available
before kickoff. Training is restricted to Jan-Aug 2024.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import exp, log
from .legacy import fixture_datetime,outcome_scores,estimate_goals,score_matrix,markets_from_matrix
from bsd_v2_btts import btts_features
from bsd_v2_btts_team import team_scoring_probabilities
from bsd_v2_btts_zero import fit_zero_goal_model

FEATURE_NAMES=(
    "intercept",
    "v3_no_centered",
    "zero_no_centered",
    "team_no_centered",
    "max_blank_centered",
    "min_side_score_centered",
    "min_lambda_centered",
    "total_lambda_centered",
    "league_btts_centered",
)

def _clip(p):
    return max(.02,min(.98,float(p)))

def _sigmoid(x):
    return 1/(1+exp(-max(-24.,min(24.,x))))

def _logit(p):
    p=_clip(p)
    return log(p/(1-p))

def _features(event,index,rho,team_model,zero_model,goal_model=None,cal=None):
    expected,reason=estimate_goals(event,index)
    if expected is None:return None
    if goal_model is not None and goal_model.alpha:
        expected=goal_model.apply(event,index,expected)
    matrix=score_matrix(expected["home"],expected["away"],rho)
    if cal is not None:
        matrix=cal.apply(matrix)
    v3_no=next(c.probability for c in markets_from_matrix(matrix) if c.key=="BTTS_NO")
    side=team_scoring_probabilities(event,index,model=team_model)
    zero=zero_model.predict(event,index,expected) if zero_model is not None else None
    feat=btts_features(event,index)
    if side is None or zero is None or feat is None:return None
    ph=float(zero["home_blank"]);pa=float(zero["away_blank"])
    zero_no=ph+pa-ph*pa
    team_no=1-float(side["home_scores"])*float(side["away_scores"])
    max_blank=max(ph,pa)
    min_side=min(float(side["home_scores"]),float(side["away_scores"]))
    min_lambda=min(float(expected["home"]),float(expected["away"]))
    total_lambda=float(expected["home"])+float(expected["away"])
    league_btts=float(feat[9]+.5)
    x=(
        1.,
        v3_no-.50,
        zero_no-.50,
        team_no-.50,
        max_blank-.30,
        min_side-.65,
        min_lambda-.90,
        total_lambda-2.50,
        league_btts-.52,
    )
    meta={
        "v3_no":v3_no,"zero_no":zero_no,"team_no":team_no,
        "max_blank":max_blank,"min_side_score":min_side,
        "min_lambda":min_lambda,"total_lambda":total_lambda,
        "league_btts":league_btts,
    }
    return x,meta

def _fit(rows,epochs=260):
    if not rows:return ()
    w=[_logit(.48)]+[0.]*(len(FEATURE_NAMES)-1)
    for epoch in range(epochs):
        grad=[0.]*len(w)
        for x,y in rows:
            p=_sigmoid(sum(a*b for a,b in zip(w,x)))
            d=p-y
            for j in range(len(w)):grad[j]+=d*x[j]
        rate=1.8/(1+epoch/180.)
        for j in range(len(w)):
            penalty=(.008*w[j] if j else .003*w[j])
            w[j]-=rate*(grad[j]/len(rows)+penalty)
            w[j]=max(-6.,min(6.,w[j]))
    return tuple(w)

@dataclass(frozen=True)
class BTTSNoModel:
    weights: tuple
    training_matches: int
    team_model: object
    zero_model: object

    def predict(self,event,index,rho,goal_model=None,cal=None):
        pair=_features(event,index,rho,self.team_model,self.zero_model,goal_model,cal)
        if pair is None:return None
        x,meta=pair
        p=_clip(_sigmoid(sum(a*b for a,b in zip(self.weights,x))))
        return {"probability":p,**meta}

    def metadata(self):
        return {"version":"btts-no-logit-v1","trained":self.training_matches,
                "training_period":"2024-01 through 2024-08",
                "features":list(FEATURE_NAMES),"weights":[round(x,6) for x in self.weights]}

def fit_btts_no_model(index,rho,team_model,*,goal_model=None,cal=None,max_training=4000):
    training=[]
    for _,event in index.global_games:
        dt=fixture_datetime(event)
        if dt.year==2024 and dt.month<=8 and outcome_scores(event) is not None:
            training.append(event)
    training.sort(key=lambda e:(fixture_datetime(e),str(e.get("id"))))
    if len(training)>max_training:
        training=[training[int(i*len(training)/max_training)] for i in range(max_training)]
    zero_model=fit_zero_goal_model(index,training,max_training=max_training)
    if zero_model is None:return None
    rows=[]
    for event in training:
        pair=_features(event,index,rho,team_model,zero_model,goal_model,cal)
        score=outcome_scores(event)
        if pair is None or score is None:continue
        x,_=pair
        rows.append((x,int(score[0]==0 or score[1]==0)))
    if len(rows)<300:return None
    return BTTSNoModel(_fit(rows),len(rows),team_model,zero_model)
