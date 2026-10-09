"""Point-in-time 1/X/2 model; coherent 1X, X2 and 12 probabilities.

2024 Jan-Aug: train; 2024 Sep-Dec: choose baseline/specialist blend.
2025 Jan-Aug: outcome calibration; late 2025: quality checks.
2026: strictly held-out testing. No odds are inferred from scores.
"""
from __future__ import annotations
from bisect import bisect_right
from dataclasses import dataclass, replace
from math import exp, log, sqrt
from bsd_h2h import _team_id
from bsd_v2_core import fixture_datetime, league_key, outcome_scores, estimate_goals, score_matrix, markets_from_matrix

KEYS=("1","X","2")
DC_KEYS=("1X","X2","12")
FEATURES=17

def _softmax(values):
    top=max(values)
    weights=[exp(max(-60.,v-top)) for v in values]
    total=sum(weights)
    return tuple(max(1e-10,v/total) for v in weights)

def _decay_rate(games, at, outcome, prior=.33, strength=6., half_life=100.):
    num=0.;den=0.
    for game in games:
        score=outcome_scores(game)
        if score is None:continue
        days=max(0.,(at-fixture_datetime(game)).total_seconds()/86400)
        weight=exp(-log(2)*days/half_life)
        num+=weight*outcome(game,score)
        den+=weight
    return (num+strength*prior)/(den+strength)

def _team_rates(games,team,at,prior_draw):
    def result(match,score):
        is_home=_team_id(match,"home")==team
        gd=score[0]-score[1] if is_home else score[1]-score[0]
        return gd
    win=_decay_rate(games,at,lambda e,s:int(result(e,s)>0),prior=.40)
    draw=_decay_rate(games,at,lambda e,s:int(result(e,s)==0),prior=prior_draw)
    avoid=_decay_rate(games,at,lambda e,s:int(result(e,s)>=0),prior=.67)
    return win,draw,avoid

def _goal_rates(games,team,at):
    scored=0.;conceded=0.;total=0.
    for game in games:
        scores=outcome_scores(game)
        if scores is None:continue
        home=_team_id(game,"home")==team
        gf=scores[0] if home else scores[1]
        ga=scores[1] if home else scores[0]
        w=exp(-log(2.)*max(0.,(at-fixture_datetime(game)).total_seconds()/86400)/110.)
        scored+=gf*w;conceded+=ga*w;total+=w
    return ((scored+5*1.35)/(total+5),
            (conceded+5*1.35)/(total+5))


def _build_elo(index):
    # Each update becomes visible only after BSD's four-hour settlement delay.
    timeline={}
    ratings={}
    for available,event in index.global_games:
        home=_team_id(event,"home");away=_team_id(event,"away")
        score=outcome_scores(event)
        if not home or not away or score is None:continue
        h=ratings.get(home,1500.);a=ratings.get(away,1500.)
        expectation=1/(1+10**(-(h+65-a)/400))
        result=1. if score[0]>score[1] else .5 if score[0]==score[1] else 0.
        shift=16.*(result-expectation)
        ratings[home]=h+shift
        ratings[away]=a-shift
        timeline.setdefault(home,[]).append((available,ratings[home]))
        timeline.setdefault(away,[]).append((available,ratings[away]))
    return {team:([x[0] for x in events],[x[1] for x in events])
            for team,events in timeline.items()}

def _rating(index,team,at):
    if not hasattr(index,"_dc_elo_history"):
        index._dc_elo_history=_build_elo(index)
    times,values=index._dc_elo_history.get(team,([],[]))
    pos=bisect_right(times,at.timestamp())-1
    return values[pos] if pos>=0 else 1500.

def _opponent_strength_form(index,team,games,at):
    """Historical form vs opponents' *then-current* Elo, never future Elo."""
    win=avoid=weight_sum=0.
    for game in games:
        result=outcome_scores(game)
        if result is None:continue
        team_home=_team_id(game,"home")==team
        opponent=_team_id(game,"away" if team_home else "home")
        played=fixture_datetime(game)
        opposing_elo=_rating(index,opponent,played) if opponent else 1500.
        # Weight difficult opponents modestly more; cap outliers.
        quality=max(.80,min(1.20,1+(opposing_elo-1500.)/1500.))
        strength=exp(-log(2)*max(0.,(at-played).total_seconds()/86400)/100.)
        goal_diff=result[0]-result[1] if team_home else result[1]-result[0]
        win+=strength*quality*int(goal_diff>0)
        avoid+=strength*quality*int(goal_diff>=0)
        weight_sum+=strength
    return ((win+6*.38)/(weight_sum+6),
            (avoid+6*.65)/(weight_sum+6))


def features(event,index):
    at=fixture_datetime(event)
    home=_team_id(event,"home");away=_team_id(event,"away")
    if not home or not away or home==away:return None
    hg=index.team(home,at,limit=15);ag=index.team(away,at,limit=15)
    if min(len(hg),len(ag))<5:return None
    hv=index.team(home,at,limit=12,venue="home")
    av=index.team(away,at,limit=12,venue="away")
    league=index.league(league_key(event),at,limit=300)
    n=len(league)
    league_draw=(sum(int(outcome_scores(x)[0]==outcome_scores(x)[1]) for x in league)+
                 35*.27)/(n+35)
    hw,hd,ha=_team_rates(hg,home,at,league_draw)
    aw,ad,aa=_team_rates(ag,away,at,league_draw)
    hwv,hdv,hav=_team_rates(hv,home,at,league_draw)
    awv,adv,aav=_team_rates(av,away,at,league_draw)
    # Regress thin venue samples toward overall strength.
    shrink_h=len(hv)/(len(hv)+8)
    shrink_a=len(av)/(len(av)+8)
    hwv=shrink_h*hwv+(1-shrink_h)*hw
    awv=shrink_a*awv+(1-shrink_a)*aw
    hav=shrink_h*hav+(1-shrink_h)*ha
    aav=shrink_a*aav+(1-shrink_a)*aa
    hdv=shrink_h*hdv+(1-shrink_h)*hd
    adv=shrink_a*adv+(1-shrink_a)*ad
    # Historical opponent strength via pre-match Elo rating.
    elo=(_rating(index,home,at)-_rating(index,away,at))/400.
    recent_home=index.team(home,at,limit=5)
    recent_away=index.team(away,at,limit=5)
    hw5,hd5,_=_team_rates(recent_home,home,at,league_draw)
    aw5,ad5,_=_team_rates(recent_away,away,at,league_draw)
    home_for,home_against=_goal_rates(hg,home,at)
    away_for,away_against=_goal_rates(ag,away,at)
    home_win_quality,home_avoid_quality=_opponent_strength_form(index,home,hg,at)
    away_win_quality,away_avoid_quality=_opponent_strength_form(index,away,ag,at)
    return (1.,hw-aw,hwv-awv,ha-aav,hd+ad-2*league_draw,
            (hdv+adv)/2-league_draw,league_draw-.27,
            max(-1.5,min(1.5,elo)),hw5-aw5,
            (hw5-hw)-(aw5-aw),
            abs(hw-aw),min(ha,aav)-.6,
            (len(hv)/(len(hv)+8)-len(av)/(len(av)+8)),
            (home_for-away_against)/2.,
            (away_for-home_against)/2.,
            home_win_quality-away_win_quality,
            home_avoid_quality-away_avoid_quality)

def _train(rows,epochs=160):
    weights=[[0.]*FEATURES for _ in range(3)]
    if not rows:return tuple(tuple(w) for w in weights)
    for i in range(epochs):
        grad=[[0.]*FEATURES for _ in range(3)]
        for x,y in rows:
            prob=_softmax([sum(v*z for v,z in zip(row,x)) for row in weights])
            for cls in range(3):
                err=prob[cls]-int(y==cls)
                for j,value in enumerate(x):grad[cls][j]+=err*value
        eta=1.5/(1+i/100.)
        for cls in range(3):
            for j in range(FEATURES):
                penalty=0 if j==0 else .007*weights[cls][j]
                weights[cls][j]-=eta*(grad[cls][j]/len(rows)+penalty)
                weights[cls][j]=min(8.,max(-8.,weights[cls][j]))
    return tuple(tuple(w) for w in weights)

def score_probs(candidates):
    p={c.key:c.probability for c in candidates}
    return tuple(p[k] for k in KEYS)

def _correct(p):
    q=[max(1e-9,float(v)) for v in p]
    s=sum(q)
    return tuple(v/s for v in q)

@dataclass(frozen=True)
class DoubleChanceModel:
    weights:tuple
    blend:float=0.
    trained:int=0
    validated:int=0

    def predict(self,event,index,original):
        if self.blend<=0:return _correct(original)
        x=features(event,index)
        if x is None:return _correct(original)
        specialist=_softmax([sum(w*v for w,v in zip(row,x)) for row in self.weights])
        return _correct(tuple((1-self.blend)*o+self.blend*s
                              for o,s in zip(original,specialist)))

    def to_dict(self):
        return {"model":"bsd-double-chance-1","blend":self.blend,
                "train_count":self.trained,"validation_count":self.validated}

class OutcomeCalibration:
    """Joint multiclass calibration by pre-calibration draw-probability band.

    Trained using 2025 Jan-Aug only. Smoothing to a global residual prevents
    sparse draw-rate bins from producing extreme corrections.
    """
    def __init__(self,prior=130):
        self.prior=int(prior)
        self.n=0
        self.residual=[0.,0.,0.]
        self.bins={}

    @staticmethod
    def _bin(p):
        return min(4,max(0,int(float(p[1])*5)))

    def observe(self,prob,actual):
        p=_correct(prob)
        self.n+=1
        bucket=self._bin(p)
        count,residual=self.bins.get(bucket,(0,[0.,0.,0.]))
        residual=list(residual)
        for i in range(3):
            error=int(i==actual)-p[i]
            self.residual[i]+=error
            residual[i]+=error
        self.bins[bucket]=(count+1,residual)

    def apply(self,p):
        p=_correct(p)
        if self.n==0:return p
        global_offset=[r/(self.n+self.prior) for r in self.residual]
        count,residual=self.bins.get(self._bin(p),(0,[0.,0.,0.]))
        local_weight=count/(count+80.)
        offsets=[(1-local_weight)*global_offset[i]+local_weight*
                 residual[i]/(count+40.) for i in range(3)]
        return _correct([max(.0001,p[i]+offsets[i]) for i in range(3)])


def adjust_candidates(event,index,candidates,model=None,calibration=None):
    """Produce coherent 1X2 and derived 1X/X2/12; no other markets altered."""
    if model is None and calibration is None:return candidates
    original=score_probs(candidates)
    p=model.predict(event,index,original) if model is not None else original
    if calibration is not None:p=calibration.apply(p)
    resolved={"1":p[0],"X":p[1],"2":p[2],
              "1X":p[0]+p[1],"X2":p[1]+p[2],"12":p[0]+p[2]}
    return [replace(c,probability=resolved[c.key]) if c.key in resolved else c
            for c in candidates]

def uncertain(event,index,model,original):
    if model is None or model.blend<=0:return None
    at=fixture_datetime(event)
    h=_team_id(event,"home");a=_team_id(event,"away")
    home=index.team(h,at,limit=12);away=index.team(a,at,limit=12)
    if min(len(home),len(away))<6:return "dc_weak_form"
    if min(len(index.team(h,at,limit=12,venue="home")),
           len(index.team(a,at,limit=12,venue="away")))<3:
        return "dc_weak_venue"
    p=model.predict(event,index,original)
    if max(abs(x-y) for x,y in zip(p,original))>.22:
        return "dc_model_disagreement"
    return None

def fit_model(index,rho=0.,max_training=1500,max_validation=400):
    training=[];validation=[]
    for _,event in index.global_games:
        at=fixture_datetime(event)
        if at.year!=2024:continue
        x=features(event,index)
        estimated,_=estimate_goals(event,index)
        if x is None or estimated is None:continue
        score=outcome_scores(event)
        y=0 if score[0]>score[1] else 1 if score[0]==score[1] else 2
        p=score_probs(markets_from_matrix(score_matrix(estimated["home"],estimated["away"],rho)))
        (training if at.month<=8 else validation).append((at,x,y,p))
    def sample(rows,cap):
        rows.sort(key=lambda t:t[0])
        return rows if len(rows)<=cap else [rows[int(i*len(rows)/cap)] for i in range(cap)]
    training=sample(training,max_training);validation=sample(validation,max_validation)
    weights=_train([(x,y) for _,x,y,_ in training])
    def brier(weight):
        errors=0.
        for _at,x,y,baseline in validation:
            specialized=_softmax([sum(w*v for w,v in zip(row,x)) for row in weights])
            p=[(1-weight)*b+weight*s for b,s in zip(baseline,specialized)]
            errors+=sum((p[k]-int(k==y))**2 for k in range(3))
        return errors/len(validation)
    if len(training)<100 or len(validation)<50:
        blend=0.;diagnostics={"reason":"insufficient_2024_samples"}
    else:
        grid=(0.,.25,.5,.75,1.)
        best=min(grid,key=brier)
        blend=best if brier(best)<brier(0.)-.002 else 0.
        diagnostics={"baseline_brier":round(brier(0.),6),
                     "specialized_brier":round(brier(1.),6),
                     "selected_brier":round(brier(blend),6)}
    return DoubleChanceModel(weights,blend,len(training),len(validation)),{
        **diagnostics,"blend":blend,"trained":len(training),"validated":len(validation),
        "training_period":"2024-01 to 2024-08",
        "validation_period":"2024-09 to 2024-12"}
