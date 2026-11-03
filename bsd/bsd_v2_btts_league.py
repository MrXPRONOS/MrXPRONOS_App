"""BTTS league-aware Bayesian residual calibration, strictly pre-2026.

A country/league's empirical scoring rate alone does not account for the
teams' strength already used by Poisson and the specialist. Instead we
estimate the residual (actual BTTS minus model probability) on pre-2026
fixtures and shrink the correction to zero when a league has few samples.

Jan-Jun 2025 trains residuals, Jul-Aug selects their mixing coefficient,
Sep-Dec verifies it out of sample; 2026 is never used to fit or select.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass

from bsd_v2_core import fixture_datetime, league_key, outcome_scores


def league_btts_deviation(event,index,*,min_league_games=40):
    """Legacy point-in-time league-rate deviation; available for comparison."""
    at=fixture_datetime(event)
    key=league_key(event)
    if not key:return 0.
    recent=index.league(key,at,limit=300)
    if len(recent)<min_league_games:return 0.
    global_games=index.global_prior(at,limit=1200)
    if not global_games:return 0.
    g_hits=sum(1 for r in global_games
               if outcome_scores(r)[0]>0 and outcome_scores(r)[1]>0)
    l_hits=sum(1 for r in recent
               if outcome_scores(r)[0]>0 and outcome_scores(r)[1]>0)
    global_p=(g_hits+200*.52)/(len(global_games)+200)
    league_p=(l_hits+80*global_p)/(len(recent)+80)
    return max(-.12,min(.12,league_p-global_p))


@dataclass(frozen=True)
class LeagueBTTSModel:
    residuals: dict
    counts: dict
    trained_fixtures: int
    shrinkage: float = 100.
    min_samples: int = 20

    def deviation(self,event):
        k=league_key(event)
        if self.counts.get(k,0)<self.min_samples:
            return 0.
        return self.residuals.get(k,0.)

    def to_dict(self):
        return {"version":"btts-league-residual-1",
                "trained_fixtures":self.trained_fixtures,
                "league_count":len(self.residuals),
                "shrinkage":self.shrinkage,
                "min_samples":self.min_samples}


def fit_league_residual_model(rows,*,shrinkage=100.,min_samples=20):
    """Fit from (fixture, probability_before_league, actual_yes) rows.

    The caller must enforce a strict pre-2026 2025-Jan-Jun training range.
    """
    totals=defaultdict(lambda:[0,0.])
    for event,probability,actual in rows:
        at=fixture_datetime(event)
        if at.year!=2025 or at.month>6:
            raise ValueError("League residual training must be Jan-Jun 2025")
        key=league_key(event)
        if not key:continue
        row=totals[key]
        row[0]+=1
        row[1]+=float(actual)-float(probability)
    counts={k:r[0] for k,r in totals.items()}
    residuals={k:max(-.10,min(.10,r[1]/(r[0]+shrinkage)))
               for k,r in totals.items() if r[0]>=min_samples}
    return LeagueBTTSModel(residuals,counts,sum(counts.values()),shrinkage,min_samples)
