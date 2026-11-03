"""Point-in-time league BTTS deviation, safely shrunk to a global prior.

No league IDs are hardcoded. League observations always predate the fixture.
The multiplier is selected on a separate 2024 validation period and defaults
to zero when no measurable improvement exists.
"""
from __future__ import annotations
from bsd_v2_core import fixture_datetime,league_key,outcome_scores


def league_btts_deviation(event,index,*,min_league_games=40):
    at=fixture_datetime(event)
    key=league_key(event)
    if not key:
        return 0.0
    recent=index.league(key,at,limit=300)
    if len(recent)<min_league_games:
        return 0.0
    global_games=index.global_prior(at,limit=1200)
    if not global_games:
        return 0.0
    g_hits=sum(1 for r in global_games if outcome_scores(r)[0]>0 and outcome_scores(r)[1]>0)
    league_hits=sum(1 for r in recent if outcome_scores(r)[0]>0 and outcome_scores(r)[1]>0)
    global_p=(g_hits+200*.52)/(len(global_games)+200)
    league_p=(league_hits+80*global_p)/(len(recent)+80)
    return max(-.12,min(.12,league_p-global_p))
