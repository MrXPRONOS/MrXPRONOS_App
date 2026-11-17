"""Remove bookmaker/consensus overround ONLY when complete exclusive outcomes exist.

No mixing of different books, no guesses from a single moneyline or DC quote.
Only full time 1X2, both BTTS choices, and both sides of a goal line.
"""
from __future__ import annotations
from math import isfinite

from bsd_v2_odds_comparison import valid_independent_quote

GROUPS=[
  ('1X2_HOME_FT','1X2_DRAW_FT','1X2_AWAY_FT'),
  ('BTTS_YES_FT','BTTS_NO_FT'),
  *[(f'OU_{line}_OVER_FT',f'OU_{line}_UNDER_FT') for line in ('1.5','2.5','3.5','4.5')]
]
BY_MARKET={code:group for group in GROUPS for code in group}

def no_vig_probability(target, quotes, *, captured, kickoff):
    group=BY_MARKET.get(target)
    if group is None:return None,'no_complete_outcome_group_supported'
    rows=[]
    for code in group:
        row=quotes.get(code) if isinstance(quotes,dict) else None
        if row is None:return None,'missing_complementary_market_quote'
        checked,reason=valid_independent_quote(row,code=code,now=captured,kickoff=kickoff)
        if not checked:return None,reason
        rows.append(row)
    if len({r.get('bookmaker') for r in rows})!=1:
        return None,'complements_from_different_bookmakers'
    if len({r.get('origin') for r in rows})!=1:
        return None,'complements_from_different_provider_origins'
    implied=[1/float(r['odds']) for r in rows]
    gross=sum(implied)
    if not isfinite(gross) or gross<=0:return None,'invalid_complete_market'
    p=implied[group.index(target)]/gross
    return {'no_vig_probability':round(p,6),
            'overround':round(gross-1,6),
            'complement_count':len(group),
            'bookmaker':rows[0].get('bookmaker')},'ok'
