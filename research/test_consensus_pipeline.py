#!/usr/bin/env python3
"""Integration regression: all six engines vote; future/same-day scores cannot leak."""
from datetime import date, timedelta
from exact_scores_2026 import Match
from predict_consensus import predict, consensus, SIX

def check():
    hist=[]
    base=date(2026,6,1)
    for i in range(385):
        day=base+timedelta(days=i//12)
        a=i%18
        b=(i+3)%18
        hist.append(Match(str(i),day,"Example League",f"Team {a}",f"Team {b}",
                          (i*7)%4,(i*13)%3))
    future=[{"date":date(2026,8,1),"id":"upcoming-1",
             "league":"Example League","home_team":"Team 2","away_team":"Team 4"}]
    before=predict(future,hist,minimum=5)
    assert len(before)==1
    record=before[0]
    assert record["previous_completed_match_count"]==len(hist),record
    assert set(record["models"])==set(SIX)
    assert record["decision"]["highest_vote_count"]>=1
    assert record["status"] in ("SELECTED","ABSTAIN")
    # Poison: match on same calendar day with deliberately extreme (unrealistic)
    # 10-10 result. Correct pipeline MUST ignore it when predicting this date.
    poisoned=hist+[Match("poison",date(2026,8,1),"Example League",
                         "Team 2","Team 4",10,10)]
    after=predict(future,poisoned,minimum=5)
    assert before==after, (before,after)
    selected=consensus({m:"1:1" for m in SIX},6)
    assert selected["status"]=="SELECTED"
    print("FUTURE_FIXTURE_PIPELINE_AND_NO_LEAKAGE_OK")

if __name__=="__main__":
    check()
