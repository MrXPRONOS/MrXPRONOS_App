"""Bivariate-Poisson joint goals for BSD V2 BTTS.

H=U+W, A=V+W with independent Poisson U,V,W. The shared-goal
component W introduces nonnegative covariance; total marginal goal
means are preserved. Learn the shared fraction by 2024-only
joint-score likelihood. Never use 2026 scores for fitting.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import exp, factorial, log
from bsd_v2_core import estimate_goals, fixture_datetime, outcome_scores

SHARES=(0., .025, .05, .075, .10, .15, .20, .30, .40)


def poisson_pmf(n,mean):
    if n<0:return 0.
    return exp(-mean)*(mean**n)/factorial(n)


def joint_pmf(home_goals,away_goals,mean_home,mean_away,share):
    if not 0<=share<=.95:
        raise ValueError("Bivariate share must be in [0,.95]")
    if mean_home<=0 or mean_away<=0:
        raise ValueError("Goal means must be positive")
    covariance=share*min(mean_home,mean_away)
    independent_home=mean_home-covariance
    independent_away=mean_away-covariance
    return sum(poisson_pmf(home_goals-k,independent_home)*
               poisson_pmf(away_goals-k,independent_away)*
               poisson_pmf(k,covariance)
               for k in range(min(home_goals,away_goals)+1))


def btts_probability(mean_home,mean_away,share):
    if not 0<=share<=.95:
        raise ValueError("Invalid shared goals fraction")
    covariance=share*min(mean_home,mean_away)
    result=1-exp(-mean_home)-exp(-mean_away)+exp(-mean_home-mean_away+covariance)
    return min(.99,max(.01,result))


@dataclass(frozen=True)
class BivariatePoissonBTTS:
    share: float
    trained_fixtures: int
    mean_log_likelihood: float

    def predict(self,expected):
        return btts_probability(expected["home"],expected["away"],self.share)

    def to_dict(self):
        return {"family":"bivariate_poisson","trained":self.trained_fixtures,
                "shared_fraction":self.share,"log_likelihood":self.mean_log_likelihood}


def fit_bivariate(index,fixtures,*,max_training=3000,min_training=200):
    games=sorted(fixtures,key=lambda e:(e["event_date"],str(e["id"])))
    if len(games)>max_training:
        games=[games[int(i*len(games)/max_training)] for i in range(max_training)]
    examples=[]
    for e in games:
        at=fixture_datetime(e)
        if at.year!=2024 or at.month>8:
            raise ValueError("Bivariate training must be Jan-Aug 2024 only")
        goals=outcome_scores(e)
        exp_goals,_=estimate_goals(e,index)
        if goals is None or exp_goals is None:continue
        examples.append((goals,exp_goals["home"],exp_goals["away"]))
    if len(examples)<min_training:return None
    def log_likelihood(share):
        return sum(log(max(1e-20,joint_pmf(g[0],g[1],h,a,share)))
                   for g,h,a in examples)/len(examples)
    winner=max(SHARES,key=log_likelihood)
    return BivariatePoissonBTTS(winner,len(examples),round(log_likelihood(winner),7))
