"""2024-frozen, isolated ONE-score research model: goal rates, score bias and reliability.

All learned labels are from fixtures occurring in 2024. The pre-existing
home scale 1.10 and Under2.5 parameters come from earlier exploratory
research; therefore 2025 is NOT a genuinely untouched blind test. Goal-rate training:
Jan-Apr; validation May-Jun. Score-mass calibration: Jan-Jun; validation
Jul-Aug. Independent hit-probability learner: Sep-Oct; validation Nov-Dec.
Neither 2025 nor 2026 results enter fit or hyperparameter selection.

Uses only settled matches before a fixture as features. Always experimental.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from math import exp, log, isfinite
from collections import defaultdict
from bsd_h2h import _team_id
from bsd_v2_core import estimate_goals, fixture_datetime, outcome_scores
from exact_scores import year_sample, matrix_for
from exact_scores_under25 import Under25Model, reweight_scores
from single_exact_score_research import prematch_context

SCORES=((0,0),(1,0),(0,1),(1,1),(2,0),(0,2),(2,1),(1,2))
FEATURES=5
UNDER=Under25Model(1.0,.85,.62)


def clip(x,lo,hi):
    return min(hi,max(lo,x))


def historic_measured_xg(event):
    """Historical match ONLY. Never read xG of the match being predicted."""
    if event.get("xg_estimated") is not False:
        return None
    a=event.get("home_xg_live")
    b=event.get("away_xg_live")
    if type(a) not in (int,float) or type(b) not in (int,float):
        return None
    if not (isfinite(a) and isfinite(b) and 0<=a<=8 and 0<=b<=8):
        return None
    return float(a),float(b)


def features(event,index,base):
    """Strict chronology enforced by V2History.team() 4h settlement delay."""
    at=fixture_datetime(event)
    hid=_team_id(event,"home");aid=_team_id(event,"away")
    home=index.team(hid,at,limit=8)
    away=index.team(aid,at,limit=8)
    def days(g):
        return clip((at-fixture_datetime(g[0])).total_seconds()/86400,0,35) if g else 7.
    rest_h,rest_a=days(home),days(away)
    # Past matches only, measured not provider-estimated xG.
    def mean_xg(games,team):
        vals=[]
        for g in games:
            x=historic_measured_xg(g)
            if x:
                vals.append(x[0] if _team_id(g,"home")==team else x[1])
        return sum(vals)/len(vals) if len(vals)>=3 else None
    xh=mean_xg(home,hid);xa=mean_xg(away,aid)
    expected_diff=(xh-xa) if xh is not None and xa is not None else 0.
    feat=(1.,clip(log(max(.1,base["home"])/max(.1,base["away"])),-2,2)/2,
          clip((base.get("home_venue_matches",0)-base.get("away_venue_matches",0))/8,-1,1),
          clip((rest_h-rest_a)/14,-1,1),
          clip(expected_diff/3,-1,1))
    return feat,{"home_rest_days":round(rest_h,2),"away_rest_days":round(rest_a,2),
                 "measured_xg_available":bool(xh is not None and xa is not None),
                 "home_past_measured_xg":round(xh,4) if xh is not None else None,
                 "away_past_measured_xg":round(xa,4) if xa is not None else None}


def dot(a,b):
    return sum(x*y for x,y in zip(a,b))


def adjusted(base,feat,goal_weights,strength=1.):
    home=clip(base["home"]*1.10*exp(strength*dot(goal_weights[0],feat)),.35,3.5)
    away=clip(base["away"]*exp(strength*dot(goal_weights[1],feat)),.35,3.5)
    return home,away


def goal_fit(rows,epochs=230):
    weights=[[0.]*FEATURES for _ in range(2)]
    if len(rows)<80:return (tuple(weights[0]),tuple(weights[1]))
    for iteration in range(epochs):
        grad=[[0.]*FEATURES for _ in range(2)]
        for row in rows:
            feat=row["feat"];base=row["base"];actual=row["truth"]
            for side in range(2):
                base_mu=base["home" if side==0 else "away"]*(1.10 if side==0 else 1.)
                mu=clip(base_mu*exp(clip(dot(weights[side],feat),-.7,.7)),.35,3.5)
                for j,v in enumerate(feat):
                    grad[side][j]+=(mu-actual[side])*v
        learning=.14/(1+iteration/125)
        for side in range(2):
            for j in range(FEATURES):
                reg=0. if j==0 else .04*weights[side][j]
                weights[side][j]=clip(weights[side][j]-learning*
                     (grad[side][j]/len(rows)+reg),-.42,.42)
    return tuple(tuple(w) for w in weights)


def goal_loss(rows,weights,strength):
    if not rows:return None
    loss=0.
    for row in rows:
        h,a=adjusted(row["base"],row["feat"],weights,strength)
        y=row["truth"]
        loss+=h-y[0]*log(h)+a-y[1]*log(a)
    return loss/len(rows)


def matrix(event,index,base,weights,goal_strength):
    feat,meta=features(event,index,base)
    h,a=adjusted(base,feat,weights,goal_strength)
    raw=matrix_for(h,a,rho=0.,scale_home=1.,scale_away=1.)
    under=UNDER.predict(event,index,raw)
    return reweight_scores(raw,under["probability"]),feat,meta,(h,a)


def bias_fit(rows,weights,goal_strength):
    expected=defaultdict(float);actual=defaultdict(int)
    for row in rows:
        mat,_,_,_=matrix(row["event"],row["index"],row["base"],weights,goal_strength)
        for score in SCORES:expected[score]+=mat.get(score,0.)
        if row["truth"] in SCORES:actual[row["truth"]]+=1
    values=[]
    for score in SCORES:
        # shrink low-frequency score correction towards ratio 1.
        ratio=(actual[score]+65)/(expected[score]+65)
        values.append(clip(ratio,.72,1.28))
    return tuple(values)


def bias_matrix(mat,weights,blend):
    if blend<=0:return mat
    lookup={s:w for s,w in zip(SCORES,weights)}
    changed={s:p*(1+blend*(lookup.get(s,1.)-1)) for s,p in mat.items()}
    total=sum(changed.values())
    return {s:p/total for s,p in changed.items()}


def distribution_loss(rows,goal_weights,goal_strength,bias_weights,blend):
    if not rows:return None
    loss=0.
    for r in rows:
        mat,_,_,_=matrix(r["event"],r["index"],r["base"],goal_weights,goal_strength)
        calibrated=bias_matrix(mat,bias_weights,blend)
        loss-=log(max(calibrated.get(r["truth"],0.),1e-12))
    return loss/len(rows)


def pick(mat):
    ordered=sorted(mat.items(),key=lambda x:(-x[1],x[0]))[:2]
    first,p=ordered[0];runner=ordered[1][1]
    return {"score":list(first),"probability":round(p,7),
            "margin":round(p-runner,7),"runner_up_probability":round(runner,7)}


def rel_features(choice,feat,goals):
    prob=clip(choice["probability"],.0001,.9999)
    return (1.,clip(log(prob/(1-prob)),-6,3)/3,
            clip(choice["margin"]*8,0,2),
            clip(abs(goals[0]-goals[1])/3,0,1),
            clip(abs(feat[3]),0,1))


def sigmoid(x):
    x=clip(x,-30,30)
    return 1/(1+exp(-x))


def fit_logistic(rows,epochs=260):
    w=[0.]*5
    if len(rows)<60:return tuple(w)
    for i in range(epochs):
        grad=[0.]*5
        for x,y in rows:
            e=sigmoid(dot(w,x))-y
            for j,v in enumerate(x):grad[j]+=e*v
        eta=.16/(1+i/140)
        for j in range(5):
            penalty=0 if j==0 else .035*w[j]
            w[j]=clip(w[j]-eta*(grad[j]/len(rows)+penalty),-6,6)
    return tuple(w)


def reliability_loss(rows,weights,blend):
    if not rows:return None
    return sum(((1-blend)*p+blend*sigmoid(dot(weights,x))-y)**2
               for x,y,p in rows)/len(rows)


@dataclass(frozen=True)
class AdvancedModel:
    goal_weights:tuple
    goal_strength:float
    bias_weights:tuple
    bias_strength:float
    reliability_weights:tuple
    reliability_blend:float
    diagnostic:dict

    def info(self):
        return {"format":"mrx-single-advanced-2024-frozen-v1",
                "fitted_on":"2024 only","diagnostic":self.diagnostic,
                "goal_strength":self.goal_strength,
                "bias_strength":self.bias_strength,
                "reliability_blend":self.reliability_blend}


def advanced_prediction(event,index,model,*,now=None,expected=None):
    if expected is None:
        expected,reason=estimate_goals(event,index)
        if expected is None:return None
    if now is None:now=fixture_datetime(event)
    raw,feat,meta,goals=matrix(event,index,expected,model.goal_weights,
                              model.goal_strength)
    mat=bias_matrix(raw,model.bias_weights,model.bias_strength)
    chosen=pick(mat)
    score_prob=chosen["probability"]
    calibrated=(1-model.reliability_blend)*score_prob+model.reliability_blend*sigmoid(
        dot(model.reliability_weights,rel_features(chosen,feat,goals)))
    chosen["matrix_probability"]=score_prob
    chosen["probability"]=round(clip(calibrated,.001,.999),7)
    context=prematch_context(event,now,fixture_datetime(event))
    return {"choice":chosen,"expected_goals":{"home":round(goals[0],5),
            "away":round(goals[1],5)},"rest_and_xg":meta,
            "context":context,"score_model":"2024_frozen","experimental":True}


def train_advanced(index,cap=1700):
    rows=[]
    for event in year_sample(index,2024,cap):
        base,why=estimate_goals(event,index)
        if base is None:continue
        truth=outcome_scores(event)
        if truth is None:continue
        feat,metadata=features(event,index,base)
        rows.append({"index":index,"event":event,"base":base,
                    "feat":feat,"truth":tuple(truth),
                    "month":fixture_datetime(event).month})
    goal_train=[r for r in rows if r["month"]<=4]
    goal_valid=[r for r in rows if 5<=r["month"]<=6]
    weights=goal_fit(goal_train)
    gbase=goal_loss(goal_valid,weights,0)
    strengths=(0.,.5,1.)
    gstrength=min(strengths,key=lambda s:goal_loss(goal_valid,weights,s)) if goal_valid else 0.
    if gbase is None or gbase-goal_loss(goal_valid,weights,gstrength)<.0003:
        gstrength=0.
    bias_train=[r for r in rows if r["month"]<=6]
    bias_valid=[r for r in rows if 7<=r["month"]<=8]
    bias=bias_fit(bias_train,weights,gstrength)
    bbase=distribution_loss(bias_valid,weights,gstrength,bias,0)
    bstrength=min(strengths,key=lambda s:distribution_loss(
        bias_valid,weights,gstrength,bias,s)) if bias_valid else 0.
    if bbase is None or bbase-distribution_loss(bias_valid,weights,gstrength,bias,bstrength)<.0003:
        bstrength=0.
    train=[];valid=[]
    for row in rows:
        if row["month"]<9:continue
        mat,feat,_,goals=matrix(row["event"],index,row["base"],weights,gstrength)
        ch=pick(bias_matrix(mat,bias,bstrength))
        sample=(rel_features(ch,feat,goals),int(tuple(ch["score"])==row["truth"]),
                ch["probability"])
        (train if row["month"]<=10 else valid).append(sample)
    rel=fit_logistic([(x,y) for x,y,_ in train])
    rbase=reliability_loss(valid,rel,0.)
    rblend=min((0.,.25,.5,.75,1.),key=lambda s:reliability_loss(valid,rel,s)) if valid else 0.
    if (len(train)<60 or len(valid)<40 or rbase is None or
        rbase-reliability_loss(valid,rel,rblend)<.0002):
        rblend=0.
    info={"eligible_2024":len(rows),"goal_train":len(goal_train),
          "goal_valid":len(goal_valid),"bias_train":len(bias_train),
          "bias_valid":len(bias_valid),"reliability_train":len(train),
          "reliability_valid":len(valid),
          "goal_validation_gain":round(gbase-goal_loss(goal_valid,weights,gstrength),6)
                        if gbase is not None else None,
          "bias_validation_gain":round(bbase-distribution_loss(
              bias_valid,weights,gstrength,bias,bstrength),6) if bbase is not None else None,
          "reliability_validation_gain":round(rbase-reliability_loss(
              valid,rel,rblend),6) if rbase is not None else None,
          "no_future_year_labels":True}
    return AdvancedModel(weights,gstrength,bias,bstrength,rel,rblend,info)
