"""Standalone replay for BSD V2 single-market picks under a form-regime veto.

Uses the existing BSD V2 market engine UNMODIFIED for the baseline and the
alternative. Only vetoes relevant low-scoring markets; does not change an over,
BTTS yes, home/away selection or the bookmaker prices. No historic odds or ROI.
"""
from __future__ import annotations
import argparse,json
from collections import Counter
from pathlib import Path
from bsd_v2_core import V2History,predict_v2,fixture_datetime,outcome_scores
from exact_scores import year_sample
from exact_scores_h2h import H2HIndex
from bsd_form_shift import form_shift,simple_market_veto_keys,VERSION
from bsd_markets import realized,Candidate

def bucket():
    return {"n":0,"wins":0,"sum_p":0.,"families":Counter()}
def count(b,pred,score):
    if pred is None:return
    market=pred["prediction"]
    key=market["key"]
    c=Candidate(key=key,label="",family="goals" if key.startswith(("OVER_","UNDER_")) else
                "double_chance" if key in ("1X","X2","12") else
                "btts" if key.startswith("BTTS_") else "result",
                market="",outcome="",probability=market["probability"],line=market["line"])
    b["n"]+=1;b["wins"]+=realized(c,*score)
    b["sum_p"]+=market["probability"]
    b["families"][key]+=1
def stats(x,base_n):
    return {"n":x["n"],"wins":x["wins"],
      "hit_rate":round(x["wins"]/x["n"],6) if x["n"] else None,
      "mean_prediction_probability":round(x["sum_p"]/x["n"],6) if x["n"] else None,
      "coverage":round(x["n"]/base_n,6) if base_n else None,
      "market_counts":dict(x["families"])}
def run(events,*,years=(2025,2026),cap=0):
    index=V2History(events);hindex=H2HIndex(index)
    by_year={}
    for year in years:
        base_all=bucket();guard_all=bucket();base_on_changed=bucket();guard_on_changed=bucket()
        excluded=bucket();t=Counter()
        for e in year_sample(index,year,cap):
            actual=outcome_scores(e)
            if actual is None:continue
            # Forecast status must be upcoming: the finished result remains in
            # the immutable index and cannot enter features before kickoff.
            f=dict(e);f["status"]="notstarted";f["home_score"]=None;f["away_score"]=None
            base,reason=predict_v2(f,index,rho=0.,require_odds=False,mode="reliability")
            if base is None:
                t["skipped_"+str(reason)]+=1;continue
            t["eligible"]+=1
            selected=base
            key=base["prediction"]["key"]
            if key in ("UNDER_15","UNDER_25","UNDER_35","UNDER_45","BTTS_NO","X"):
                expected=base["estimated_goals"]
                shift=form_shift(f,index,hindex,expected=expected,include_h2h=True)
                if shift["valid"] and shift["bsd_low_goals_veto"]:
                    t["alerts"]+=1
                    forbidden=simple_market_veto_keys(shift)
                    guarded,why=predict_v2(f,index,rho=0.,require_odds=False,
                                            mode="reliability",excluded_keys=forbidden)
                    if guarded is None:
                        selected=None;t["abstentions"]+=1
                    else:
                        selected=guarded
                        if selected["prediction"]["key"]!=key:
                            t["switched_market"]+=1
                    count(base_on_changed,base,actual)
                    count(guard_on_changed,selected,actual)
                    if selected is None:count(excluded,base,actual)
            count(base_all,base,actual);count(guard_all,selected,actual)
        by_year[str(year)]={"base":stats(base_all,base_all["n"]),
            "form_guard":stats(guard_all,base_all["n"]),
            "on_alert_base":stats(base_on_changed,base_all["n"]),
            "on_alert_form_guard":stats(guard_on_changed,base_all["n"]),
            "vetoed_original":stats(excluded,base_all["n"]),"counts":dict(t)}
    return {"format":"mrx-bsd-v2-form-shift-single-markets-v1",
            "years":list(years),"sample_cap":cap or None,"model":VERSION,
            "experimental":True,"published":False,
            "results":by_year,
            "warning":"Historical comparison without real odds, no implied profitable bet. 2026 explored before."}

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--history",default="bsd/all_matches_bsd.json")
    a.add_argument("--cap",type=int,default=0)
    a.add_argument("--out",default="tmp/grouped-correct-score/bsd-v2-form-shift.json")
    args=a.parse_args()
    result=run(json.loads(Path(args.history).read_text()),cap=args.cap)
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("FORM_SHIFT_BSD_SINGLES",json.dumps(result,ensure_ascii=False))

if __name__=="__main__":main()
