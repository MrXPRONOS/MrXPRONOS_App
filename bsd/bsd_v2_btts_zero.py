"""BTTS V2: new independent zero-goal (scoreless) hazard model.

Predicts P(home blank) and P(away blank) using an offset logistic model around
Poisson exp(-lambda), with genuinely different pre-match signals: short-term
scoreless/clean-sheet streaks, venue clean sheets, scoring zero-inflation
(residual to the team's average goals) and rest. No external xG is fabricated.

Trained strictly on pre-2025 fixtures; BTTS contribution requires validation
on 2024 Q4 and a separate 2025 late-year confirmation. If not validated, it
remains shadow-only. All features are point-in-time via V2History.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, log
from bsd_h2h import _team_id
from bsd_v2_core import fixture_datetime, league_key, outcome_scores, estimate_goals

FEATURE_NAMES = (
    "intercept", "own_blank_rate", "own_last4_blank", "own_venue_blank",
    "opponent_clean_sheet", "opponent_last4_clean", "opponent_venue_clean",
    "blank_streak", "clean_sheet_streak", "team_zero_inflation",
    "league_blank_rate", "rest_days",
)
MIN_TEAM = 8
MIN_VENUE = 3


def _clip(x):
    return max(.025,min(.975,float(x)))


def _logit(p):
    p=_clip(p)
    return log(p/(1-p))


def _sigmoid(z):
    z=max(-24.,min(24.,z))
    return 1/(1+exp(-z))


def _stat(games,team,at,*,kind):
    """Recent (time-decayed) zero rates and sample size."""
    weight=zero=goals=0.
    for event in games:
        score=outcome_scores(event)
        if score is None:continue
        is_home=(_team_id(event,"home")==team)
        own,other=score if is_home else score[::-1]
        value=own if kind=="blank" else other
        age=max(0.,(at-fixture_datetime(event)).total_seconds()/86400.)
        w=exp(-log(2)*age/75.)
        weight+=w
        zero+=w*int(value==0)
        goals+=w*value
    base=.30
    return ((zero+5*base)/(weight+5),
            (goals+5*1.18)/(weight+5),weight)


def _last4(games,team,*,kind):
    scores=[]
    for e in games[:4]:
        result=outcome_scores(e)
        if result is None:continue
        is_home=(_team_id(e,"home")==team)
        own,opp=result if is_home else result[::-1]
        scores.append(int((own if kind=="blank" else opp)==0))
    return (sum(scores)+2*.30)/(len(scores)+2) if scores else .30


def _streak(games,team,*,kind):
    n=0
    for e in games[:6]:
        score=outcome_scores(e)
        if score is None:break
        own,opp=score if _team_id(e,"home")==team else score[::-1]
        if (own if kind=="blank" else opp)!=0:break
        n+=1
    return min(n,4)/4.


def _league_zero_rates(event,index,at):
    games=index.league(league_key(event),at,limit=160)
    n=len(games)
    home_zero=sum(outcome_scores(g)[0]==0 for g in games)
    away_zero=sum(outcome_scores(g)[1]==0 for g in games)
    return (home_zero+50*.25)/(n+50),(away_zero+50*.31)/(n+50)


def zero_goal_features(event,index,expected=None):
    """Returns home/away offset and feature tuples; None on scant histories."""
    hid,aid=_team_id(event,"home"),_team_id(event,"away")
    if not hid or not aid or hid==aid:return None
    at=fixture_datetime(event)
    home=index.team(hid,at,limit=14)
    away=index.team(aid,at,limit=14)
    hv=index.team(hid,at,limit=10,venue="home")
    av=index.team(aid,at,limit=10,venue="away")
    if min(len(home),len(away))<MIN_TEAM or min(len(hv),len(av))<MIN_VENUE:
        return None
    if expected is None:
        expected,_=estimate_goals(event,index)
        if expected is None:return None
    lh,la=_league_zero_rates(event,index,at)
    out=[]
    for side,team,own_games,own_venue,opponent,opp_games,opp_venue,league_rate,lam in (
       ("home",hid,home,hv,aid,away,av,lh,expected["home"]),
       ("away",aid,away,av,hid,home,hv,la,expected["away"])):
        own_zero,own_goals,_=_stat(own_games,team,at,kind="blank")
        vzero,_,vweight=_stat(own_venue,team,at,kind="blank")
        opp_clean,_,_=_stat(opp_games,opponent,at,kind="clean")
        vclean,_,vw=_stat(opp_venue,opponent,at,kind="clean")
        # A small away/home venue sample cannot override longer-term form.
        own_v=(vweight*vzero+7*own_zero)/(vweight+7)
        opp_v=(vw*vclean+7*opp_clean)/(vw+7)
        own_recent=_last4(own_games,team,kind="blank")
        opp_recent=_last4(opp_games,opponent,kind="clean")
        own_streak=_streak(own_games,team,kind="blank")
        opp_streak=_streak(opp_games,opponent,kind="clean")
        inflation=max(-.40,min(.40,own_zero-exp(-own_goals)))
        days=max(0.,(at-fixture_datetime(own_games[0])).total_seconds()/86400.)
        # Centered roughly around the typical prior so the L2 intercept is stable.
        x=(1.,own_zero-.30,own_recent-.30,own_v-.30,
           opp_clean-.30,opp_recent-.30,opp_v-.30,
           own_streak-.20,opp_streak-.20,inflation,
           league_rate-.30,min(days,30.)/30.-.33)
        prior=_clip(exp(-max(.1,min(5.,lam))))
        out.append((prior,x))
    return tuple(out)


def _learn(rows,*,epochs=180):
    if not rows:return ()
    d=len(FEATURE_NAMES)
    w=[0.]*d
    for i in range(epochs):
        grad=[0.]*d
        for baseline,x,observed in rows:
            p=_sigmoid(_logit(baseline)+sum(a*b for a,b in zip(w,x)))
            diff=p-observed
            for j in range(d):
                grad[j]+=diff*x[j]
        lr=1.65/(1+i/180.)
        for j in range(d):
            w[j]-=lr*(grad[j]/len(rows)+(.012*w[j] if j>0 else .006*w[j]))
            w[j]=max(-3.,min(3.,w[j]))
    return tuple(w)


@dataclass(frozen=True)
class ZeroGoalModel:
    home_weights: tuple
    away_weights: tuple
    training_matches: int

    def predict(self,event,index,expected=None):
        feat=zero_goal_features(event,index,expected)
        if feat is None:return None
        (ph,xh),(pa,xa)=feat
        ph=_clip(_sigmoid(_logit(ph)+sum(a*b for a,b in zip(xh,self.home_weights))))
        pa=_clip(_sigmoid(_logit(pa)+sum(a*b for a,b in zip(xa,self.away_weights))))
        # Independence is only a candidate; its BTTS mixing is validated separately.
        return {"home_blank":ph,"away_blank":pa,
                "home_scores":1-ph,"away_scores":1-pa,
                "btts_yes":_clip((1-ph)*(1-pa)),
                "baseline_home_blank":feat[0][0],
                "baseline_away_blank":feat[1][0]}

    def to_dict(self):
        return {"version":"zero-goal-offset-logit-1",
                "trained":self.training_matches,
                "features":list(FEATURE_NAMES),
                "home_weights":list(self.home_weights),
                "away_weights":list(self.away_weights)}


def fit_zero_goal_model(index,fixtures,*,max_training=3600):
    """Train on Jan-Aug 2024 exclusively; reject any other dates."""
    ordered=sorted(fixtures,key=lambda x:(x["event_date"],str(x["id"])))
    if len(ordered)>max_training:
        ordered=[ordered[int(i*len(ordered)/max_training)] for i in range(max_training)]
    home_rows,away_rows=[],[]
    for event in ordered:
        dt=fixture_datetime(event)
        if dt.year!=2024 or dt.month>8:
            raise ValueError("Zero-goal training restricted to Jan-Aug 2024")
        score=outcome_scores(event)
        if score is None:continue
        pair=zero_goal_features(event,index)
        if pair is None:continue
        home_rows.append((pair[0][0],pair[0][1],int(score[0]==0)))
        away_rows.append((pair[1][0],pair[1][1],int(score[1]==0)))
    if len(home_rows)<100:return None
    return ZeroGoalModel(_learn(home_rows),_learn(away_rows),len(home_rows))
