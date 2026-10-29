"""Independent, chronological total-goal bands for 1xBet group-score research.

CRITICAL: goals ceilings identify candidate MATCHES, not new 1xBet bet groups.
Never turn a three-score G1..G9 quote into a synthetic expanded market.
No odds, profit claims, or publisher actions. Every score is counted once.
"""
from __future__ import annotations
from math import isfinite

VERSION="mrx-grouped-goals-ceilings-research-v1"
CEILINGS=(2,3,4,5,6,7)
# Research-only screening requirements, fixed before future validation.
MIN_UNDER_PROBABILITY=.62
MIN_GROUP_PROBABILITY=.12
MIN_GROUP_MASS_INSIDE_CEILING=.60

def cumulative_goals(matrix,ceilings=CEILINGS):
    """Normalized score-distribution CDF, including upper tail 8+."""
    if not matrix:
        raise ValueError("Empty exact-score distribution")
    total=sum(matrix.values())
    if (not isfinite(total) or abs(total-1.0)>1e-5
        or any(not isfinite(p) or p<0 for p in matrix.values())):
        raise ValueError("Non-normalized or invalid score matrix")
    out={}
    last=0.
    for limit in ceilings:
        p=sum(prob for (h,a),prob in matrix.items() if h+a<=limit)
        if p+1e-12<last:
            raise ValueError("Cumulative totals must be monotonic")
        out[limit]=max(0.,min(1.,p))
        last=p
    return out

def goal_profile(matrix):
    cdf=cumulative_goals(matrix)
    def mass(low,high):
        return sum(p for (h,a),p in matrix.items() if low<=h+a<=high)
    bins={"0_to_2":mass(0,2),"3_to_4":mass(3,4),
          "5_to_7":mass(5,7),"8_plus":mass(8,100)}
    assert abs(sum(bins.values())-1.0)<1e-5
    tiers={f"under_{n}5":round(cdf[n],7) for n in CEILINGS}
    eligible={f"under_{n}5":cdf[n]>=MIN_UNDER_PROBABILITY for n in CEILINGS}
    first=next((n for n in CEILINGS if cdf[n]>=MIN_UNDER_PROBABILITY),None)
    return {"version":VERSION,"under_probabilities":tiers,
            "eligible_ceiling":eligible,
            "smallest_eligible_max_goals":first,
            "exclusive_goal_bands":{k:round(v,7) for k,v in bins.items()},
            "selection_requirements":{"min_under_probability":MIN_UNDER_PROBABILITY,
               "min_group_probability":MIN_GROUP_PROBABILITY,
               "min_group_mass_inside_ceiling":MIN_GROUP_MASS_INSIDE_CEILING},
            "source":"score-matrix after frozen Under2.5 recalibration",
            "note":"These are estimated match-goals CDFs, not 1xBet prices."}

def group_share_below_ceiling(scores,matrix,cap):
    group=sum(matrix.get(tuple(s),0.) for s in scores)
    if group<=0:return 0.
    low=sum(matrix.get(tuple(s),0.) for s in scores if sum(s)<=cap)
    return min(1.,max(0.,low/group))

def select_for_ceiling(groups,profile,matrix,cap,*,require_direction=True):
    """Choose one offered/research-template 1xBet group; no invented subsets."""
    if cap not in CEILINGS:
        raise ValueError("Unrecognized total-goals ceiling")
    key=f"under_{cap}5"
    if not profile["eligible_ceiling"][key]:
        return None
    candidates=[]
    for group in groups:
        if require_direction and not group["direction_eligible"]:
            continue
        if group["probability"]<MIN_GROUP_PROBABILITY:
            continue
        share=group_share_below_ceiling(group["scores"],matrix,cap)
        if share<MIN_GROUP_MASS_INSIDE_CEILING:
            continue
        candidates.append((group,share))
    if not candidates:return None
    best,share=max(candidates,key=lambda x:(x[0]["probability"],x[1]))
    return best,round(share,6)

def select_many(groups,profile,matrix):
    return {f"ceiling_under_{cap}5":(select_for_ceiling(groups,profile,matrix,cap) or (None,None))[0]
            for cap in CEILINGS}
