"""Phase 2: historical Under 2.5 classifier with clean-sheet and BTTS features.

Train on 2024, calibrate/blend on early 2025, confirm on late 2025,
evaluate unchanged on 2026. Every feature uses settled pre-match events.
"""
from dataclasses import dataclass
from math import exp,log
from bsd_h2h import _team_id
from bsd_v2_core import fixture_datetime,outcome_scores,estimate_goals,league_key
from bsd_v2_over_under import features as totals_features
from exact_scores import matrix_for
from exact_scores_under25 import probability_under25,Under25Model

def sigmoid(v):
    return 1/(1+exp(-max(-30,min(30,v))))

def features(event,index,base_probability):
    at=fixture_datetime(event)
    home=_team_id(event,"home");away=_team_id(event,"away")
    if not home or not away:return None
    h=index.team(home,at,limit=12);a=index.team(away,at,limit=12)
    if min(len(h),len(a))<5:return None
    hv=index.team(home,at,limit=8,venue="home")
    av=index.team(away,at,limit=8,venue="away")
    lg=index.league(league_key(event),at,limit=200)
    def rate(rows,team,mode,prior):
        vals=[]
        for e in rows:
            s=outcome_scores(e)
            if s is None:continue
            scoring=s[0] if _team_id(e,"home")==team else s[1]
            against=s[1] if _team_id(e,"home")==team else s[0]
            vals.append(int(scoring==0) if mode=="failed" else
                        int(against==0) if mode=="clean" else
                        int(sum(s)<=2) if mode=="under" else
                        int(s[0]>0 and s[1]>0))
        return (sum(vals)+5*prior)/(len(vals)+5)
    h_failed=rate(h,home,"failed",.30);a_failed=rate(a,away,"failed",.30)
    h_clean=rate(h,home,"clean",.28);a_clean=rate(a,away,"clean",.28)
    h_venue=rate(hv,home,"under",.50);a_venue=rate(av,away,"under",.50)
    h_btts=rate(h,home,"btts",.50);a_btts=rate(a,away,"btts",.50)
    league_under=(sum(int(sum(outcome_scores(x))<=2) for x in lg)+20*.5)/(len(lg)+20)
    total=totals_features(event,index)
    if total is None:return None
    # Dimension 11 including intercept; centered input and probability prior.
    return (1.,base_probability-.5,h_failed-.3,a_failed-.3,
            h_clean-.28,a_clean-.28,h_venue-.5,a_venue-.5,
            (h_btts+a_btts)/2-.5,league_under-.5,
            min(6.,total["mean"])-2.6)

def fit_logistic(rows,epochs=280,step=.20,penalty=2.5):
    if not rows:return (0.,)*11
    n=len(rows[0][0])
    if n!=11:raise ValueError("Feature count changed")
    w=[0.]*n
    for _ in range(epochs):
        grad=[0.]*n
        for x,y,_ in rows:
            p=sigmoid(sum(v*xi for v,xi in zip(w,x)))
            delta=p-y
            for j in range(n):grad[j]+=delta*x[j]
        for j in range(n):
            grad[j]=grad[j]/len(rows)+(0 if j==0 else penalty*w[j]/len(rows))
            w[j]-=step*grad[j]
    return tuple(w)

def brier(rows,predictor):
    return sum((predictor(x,base)-y)**2 for x,y,base in rows)/len(rows) if rows else None

@dataclass(frozen=True)
class Under25V2:
    weights:tuple
    blend:float=0.
    calibration_a:float=1.
    calibration_b:float=0.
    def predict(self,x,base):
        if x is None or not self.blend:return base
        raw=sigmoid(sum(w*v for w,v in zip(self.weights,x)))
        calibrated=sigmoid(self.calibration_a*log(max(.001,raw)/max(.001,1-raw))+self.calibration_b)
        return min(.999,max(.001,(1-self.blend)*base+self.blend*calibrated))

def training_rows(index,year,base_model,params,max_rows=1600):
    from exact_scores import year_sample
    data=[]
    for e in year_sample(index,year,max_rows):
        est,_=estimate_goals(e,index)
        if est is None:continue
        score=matrix_for(est["home"]*params["scale_home"],
                         est["away"]*params["scale_away"],rho=params["rho"])
        base=base_model.predict(e,index,score)["probability"]
        x=features(e,index,base)
        if x is None:continue
        data.append((x,int(sum(outcome_scores(e))<=2),base))
    return data

def train(index,base_model,params):
    rows24=training_rows(index,2024,base_model,params,1600)
    rows25=training_rows(index,2025,base_model,params,2000)
    cut=int(len(rows25)*.5)
    calib,valid=rows25[:cut],rows25[cut:]
    if len(rows24)<150 or len(calib)<70 or len(valid)<70:
        return Under25V2((0.,)*11),{"reason":"insufficient_training",
            "train":len(rows24),"calibration":len(calib),"validation":len(valid)}
    weights=fit_logistic(rows24)
    # Calibrate logistic prediction with preselected slope/offset candidates
    # using first half of 2025, then choose blend using separate second half.
    raw=lambda x:sigmoid(sum(w*v for w,v in zip(weights,x)))
    def corrected(x,a,b):
        p=raw(x)
        return sigmoid(a*log(max(.001,p)/max(.001,1-p))+b)
    candidates=((1.,0.),(.75,0.),(1.25,0.),(1.,-.20),(1.,.20),(.75,-.20),(.75,.20))
    best_a,best_b=min(candidates,key=lambda ab:sum((corrected(x,*ab)-y)**2 for x,y,_ in calib))
    trained=Under25V2(weights,0.,best_a,best_b)
    blends=(0.,.25,.5,.75,1.)
    def pred(x,base,w):
        return Under25V2(weights,w,best_a,best_b).predict(x,base)
    scores={str(w):round(sum((pred(x,b,w)-y)**2 for x,y,b in valid)/len(valid),6)
            for w in blends}
    best=min(blends,key=lambda w:(scores[str(w)],w))
    # Guardrail: deploy blended model only if improvement is clearly measurable.
    selected=best if scores["0.0"]-scores[str(best)]>=.0005 else 0.
    trained=Under25V2(weights,selected,best_a,best_b)
    return trained,{"train_2024":len(rows24),"calibration_2025":len(calib),
                    "validation_2025":len(valid),"blend":selected,
                    "calibration_a":best_a,"calibration_b":best_b,
                    "validation_brier_by_blend":scores,
                    "note":"V2 tuned only with 2024 and 2025, never 2026"}

