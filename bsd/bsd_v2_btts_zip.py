"""Zero-Inflated Poisson (ZIP) goal distributions for both teams.

Unlike a binary blank classifier, this models the entire probability mass
of 0,1,2,... goals. Structural-zero probability depends on historical blank
and clean-sheet tendency; the Poisson mean is adjusted to preserve the
expected goal total. Parameters are learned by likelihood on 2024 matches.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import exp, log, lgamma
from bsd_v2_core import estimate_goals, fixture_datetime, outcome_scores
from bsd_v2_btts_zero import zero_goal_features

INTERCEPTS=("none",-6.,-5.,-4.,-3.,-2.)
SLOPES=(0.,2.,4.,7.,10.)


def _sigmoid(z):
    return 1/(1+exp(-max(-24.,min(24.,z))))


def _signal(feature):
    """Centered zero-goal propensity from available pre-match features."""
    return (.45*feature[1]+.20*feature[2]+.25*feature[4]+
            .10*feature[8])


def _pi(feature,intercept,slope):
    if intercept=="none":return 0.
    return min(.40,max(0.,_sigmoid(intercept+slope*_signal(feature))))


def zip_pmf(goals,mean,inflation):
    if goals<0 or mean<=0 or not 0<=inflation<1:
        raise ValueError("Invalid ZIP arguments")
    lam=mean/(1-inflation)
    if goals==0:
        return inflation+(1-inflation)*exp(-lam)
    return (1-inflation)*exp(-lam+goals*log(lam)-lgamma(goals+1))


def zip_btts_probability(home_mean,away_mean,home_pi,away_pi):
    home_zero=zip_pmf(0,home_mean,home_pi)
    away_zero=zip_pmf(0,away_mean,away_pi)
    return min(.99,max(.01,(1-home_zero)*(1-away_zero)))


@dataclass(frozen=True)
class ZeroInflatedPoissonBTTS:
    home_intercept: object
    home_slope: float
    away_intercept: object
    away_slope: float
    trained_fixtures: int

    def predict(self,event,index,expected=None):
        if expected is None:
            expected,_=estimate_goals(event,index)
            if expected is None:return None
        pair=zero_goal_features(event,index,expected)
        if pair is None:return None
        pih=_pi(pair[0][1],self.home_intercept,self.home_slope)
        pia=_pi(pair[1][1],self.away_intercept,self.away_slope)
        home0=zip_pmf(0,expected["home"],pih)
        away0=zip_pmf(0,expected["away"],pia)
        return {"btts_yes":zip_btts_probability(expected["home"],expected["away"],pih,pia),
                "home_blank":home0,"away_blank":away0,
                "home_structural_zero":pih,"away_structural_zero":pia}

    def to_dict(self):
        return {"family":"zero_inflated_poisson",
                "trained":self.trained_fixtures,
                "home_intercept":self.home_intercept,"home_slope":self.home_slope,
                "away_intercept":self.away_intercept,"away_slope":self.away_slope}


def fit_zip(index,fixtures,*,max_training=3000,min_training=200):
    events=sorted(fixtures,key=lambda e:(e["event_date"],str(e["id"])))
    if len(events)>max_training:
        events=[events[int(i*len(events)/max_training)] for i in range(max_training)]
    home,away=[],[]
    for e in events:
        dt=fixture_datetime(e)
        if dt.year!=2024 or dt.month>8:
            raise ValueError("ZIP training must be Jan-Aug 2024")
        goals=outcome_scores(e)
        expected,_=estimate_goals(e,index)
        if goals is None or expected is None:continue
        features=zero_goal_features(e,index,expected)
        if features is None:continue
        home.append((goals[0],expected["home"],features[0][1]))
        away.append((goals[1],expected["away"],features[1][1]))
    if min(len(home),len(away))<min_training:return None

    def fit_side(rows):
        def loss(params):
            intercept,slope=params
            return -sum(log(max(1e-20,zip_pmf(y,lam,_pi(x,intercept,slope))))
                        for y,lam,x in rows)/len(rows)
        choices=[("none",0.)]+[(a,b) for a in INTERCEPTS if a!="none" for b in SLOPES]
        return min(choices,key=loss)
    hi,hs=fit_side(home)
    ai,asslope=fit_side(away)
    return ZeroInflatedPoissonBTTS(hi,hs,ai,asslope,len(home))
