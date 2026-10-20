"""Historical 12:13 UTC score replay using a bounded statistics as-of time.

This is a *schedule-assumed proxy*, not a real capture replay: old BSD rows
do NOT prove when an upcoming fixture was first visible in the calendar.
Only first-seen prospective encrypted archives can measure actual live results.
"""
from __future__ import annotations
import argparse,json
from collections import defaultdict,Counter
from datetime import datetime,timezone,timedelta
from pathlib import Path
from bsd_v2_core import V2History,fixture_datetime,outcome_scores
from exact_scores import year_sample
from exact_scores_h2h import H2HIndex
from single_exact_score_engine import forecast,train_dc
from single_exact_score_advanced import train_advanced
from single_exact_score_research import wilson,rank

class PointInTimeHistory:
    """Stop every historical stats lookup at the capture instant, not kickoff."""
    def __init__(self,history,as_of):
        if as_of.tzinfo is None:raise ValueError("timezone-aware replay required")
        self._history=history
        self.as_of=as_of
    def _at(self,when):
        return min(when,self.as_of)
    def _visible(self,rows):
        # A past result may have been available, while its later measured xG
        # was still unknown. Mask those future feature values as well.
        result=[]
        for event in rows:
            stamp=event.get("xg_available_at_utc")
            if stamp:
                try:
                    xg_at=datetime.fromisoformat(str(stamp).replace("Z","+00:00"))
                    if xg_at.tzinfo is None or xg_at>self.as_of:
                        event={k:v for k,v in event.items() if k not in (
                            "home_xg_live","away_xg_live","xg_estimated",
                            "xg_available_at_utc")}
                except (ValueError,TypeError,OverflowError):
                    event={k:v for k,v in event.items() if k not in (
                        "home_xg_live","away_xg_live","xg_estimated",
                        "xg_available_at_utc")}
            result.append(event)
        return result
    def team(self,team,when,limit=12,venue=None):
        return self._visible(self._history.team(team,self._at(when),limit=limit,venue=venue))
    def league(self,key,when,limit=600):
        return self._visible(self._history.league(key,self._at(when),limit=limit))
    def global_prior(self,when,limit=1200):
        return self._visible(self._history.global_prior(self._at(when),limit=limit))
    def league_baselines(self,key,when):
        return self._history.league_baselines(key,self._at(when))

class PointInTimeH2H:
    def __init__(self,history,as_of):
        self._history=history
        self.as_of=as_of
    def past_scores(self,fixture,**kwargs):
        earlier={**fixture,"event_date":self.as_of.isoformat()}
        return self._history.past_scores(earlier,**kwargs)

def cutoff_for(kickoff):
    at=kickoff.astimezone(timezone.utc)
    return at.replace(hour=12,minute=13,second=0,microsecond=0)

def replay(matches,year,cap=0):
    history=V2History(matches)
    h2h=H2HIndex(history)
    dc,_=train_dc(history)
    advanced=train_advanced(history)
    day_picks=defaultdict(list)
    stats=Counter()
    for event in year_sample(history,year,cap):
        truth=outcome_scores(event)
        if truth is None:continue
        stats["finished"]+=1
        kickoff=fixture_datetime(event)
        captured=cutoff_for(kickoff)
        if kickoff<=captured+timedelta(minutes=30):
            stats["too_early_for_1213_cutoff"]+=1
            continue
        # Match score/status were unknown at capture time.
        pre={**event,"status":"notstarted","home_score":None,"away_score":None}
        snapshot=PointInTimeHistory(history,captured)
        pred,reason=forecast(pre,snapshot,PointInTimeH2H(h2h,captured),
                             now=captured,dc_model=dc,compute_form=False,
                             advanced_model=advanced)
        if pred is None:
            stats["skipped_"+reason]+=1
            continue
        stats["eligible"]+=1
        option=pred["ablation"]["under25_fusion"]
        row={"id":str(event["id"]),"date":captured.date().isoformat(),
             "kickoff":kickoff.isoformat(),"actual":list(truth),
             "variants":{k:v for k,v in pred["ablation"].items()},
             "score":list(option["score"]),"rank":rank({
                 "variants":pred["ablation"],"quality":pred["data_quality"]}),
             "snapshot_at_utc":captured.isoformat()}
        day_picks[row["date"]].append(row)
    winning=0;baskets=0;hits=0
    selected=[]
    for day,rows in sorted(day_picks.items()):
        if len(rows)<3:
            stats["days_with_less_than_three_candidates"]+=1
            continue
        chosen=sorted(rows,key=lambda x:(-x["rank"],x["kickoff"],x["id"]))[:3]
        baskets+=1
        found=sum(int(x["score"]==x["actual"]) for x in chosen)
        hits+=found
        winning+=int(found>0)
        selected.extend(chosen)
    return {
        "format":"mrx-single-fixed-clock-replay-v1",
        "year":year,"capture_clock_utc":"12:13","minimum_lead_minutes":30,
        "calendar_availability":"assumed; past fixture scheduling snapshots unavailable",
        "history_as_of_bound":True,"h2h_as_of_bound":True,
        "real_prematch_forecasts":False,"experimental":True,"published":False,
        "finished":stats["finished"],"eligible":stats["eligible"],
        "excluded_early":stats["too_early_for_1213_cutoff"],
        "skips":{k:v for k,v in stats.items() if k.startswith("skipped_")},
        "days_under_three":stats["days_with_less_than_three_candidates"],
        "top3_baskets":baskets,"top3_with_a_hit":winning,
        "top3_match_hits":hits,
        "top3_win_rate":round(winning/baskets,6) if baskets else None,
        "top3_wilson95":wilson(winning,baskets),
        "limitations":[
          "Fixture calendar is reconstructed from completed matches; actual availability at 12:13 not recorded.",
          "Only archived first-seen prospective forecasts count as real production validation.",
          "Capture times and completeness of historic external data are not known."
        ]
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--history",default="bsd/all_matches_bsd.json")
    parser.add_argument("--year",type=int,choices=(2025,2026),default=2026)
    parser.add_argument("--cap",type=int,default=120)
    parser.add_argument("--output",default="tmp/single-exact-score/fixed-clock-replay.json")
    args=parser.parse_args()
    data=json.loads(Path(args.history).read_text(encoding="utf8"))
    result=replay(data,args.year,args.cap)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf8")
    print("SINGLE_SCORE_FIXED_CLOCK_REPLAY",json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
