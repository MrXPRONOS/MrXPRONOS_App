"""H2H V2: point-in-time features for phase 1, strictly research-only.

2026 results must NOT tune these thresholds: they are exploratory backtests.
The existing V1 H2H filter and all production pick engines remain unchanged.
"""
from bisect import bisect_right
from datetime import timedelta
from math import exp,log,sqrt
from bsd_h2h import _team_id
from bsd_v2_core import fixture_datetime,outcome_scores,league_key
from exact_scores_h2h import h2h_signal

HALF_LIFE_DAYS=540.0

def meetings_before(event,hindex,limit=8,years=4):
    """Return correctly oriented, settled historical meetings with dates."""
    home,away=_team_id(event,"home"),_team_id(event,"away")
    if not home or not away or home==away:return []
    now=fixture_datetime(event)
    pair=tuple(sorted((home,away)))
    entries,times=hindex.pairs.get(pair,([],[]))
    cutoff=now.timestamp()
    earliest=now-timedelta(days=365.25*years)
    out=[]
    for settled,prior in reversed(entries[:bisect_right(times,cutoff)]):
        played=fixture_datetime(prior)
        if played<earliest:break
        if played>=now or settled>cutoff:continue
        score=outcome_scores(prior)
        if score is None:continue
        same_venue=_team_id(prior,"home")==home
        oriented=score if same_venue else (score[1],score[0])
        out.append({"score":oriented,"total":sum(score),"date":played,
                    "same_venue":same_venue,
                    "league_match":league_key(prior)==league_key(event)})
        if len(out)>=limit:break
    return out

def _weighted_totals(rows,now):
    weights=[exp(-log(2)*max(0,(now-r["date"]).total_seconds()/86400)/HALF_LIFE_DAYS)
             for r in rows]
    total=sum(weights)
    avg=sum(w*r["total"] for r,w in zip(rows,weights))/total
    std=sqrt(sum(w*(r["total"]-avg)**2 for r,w in zip(rows,weights))/total)
    low=sum(w*(r["total"]<=2) for r,w in zip(rows,weights))/total
    n_eff=total*total/sum(w*w for w in weights)
    return avg,std,low,n_eff

def _team_attack_rate(index,team_id,at,venue,league_rate):
    """A defensive-strength proxy based ONLY on previous goals, shrunk to league."""
    matches=index.team(team_id,at,limit=8,venue=venue)
    goals=[]
    for m in matches:
        score=outcome_scores(m)
        if score is not None:
            goals.append(score[0] if _team_id(m,"home")==team_id else score[1])
    return (sum(goals)+4*league_rate)/(len(goals)+4),len(goals)

def profile(event,index,hindex):
    rows=meetings_before(event,hindex)
    original=h2h_signal([r["score"] for r in rows])
    out={"legacy":original["prioritized"],"meetings":len(rows),
         "legacy_signal":original,"candidate":False,"features":{}}
    if len(rows)<3:return out
    now=fixture_datetime(event)
    avg,std,low,n_eff=_weighted_totals(rows,now)
    recent=rows[:min(3,len(rows))]
    recent_avg=sum(r["total"] for r in recent)/len(recent)
    venue_rows=[r for r in rows if r["same_venue"]]
    # Venue gate only acts when there is sufficient same-orientation evidence.
    venue_ok=(len(venue_rows)<2 or
              (sum(r["total"]<=2 for r in venue_rows)/len(venue_rows)>=.5
               and sum(r["total"] for r in venue_rows)/len(venue_rows)<=2.5))
    recent_ok=avg<=1.85 and std<=1.15 and low>=.70 and recent_avg<=2.5
    lh,la,_=index.league_baselines(league_key(event),now)
    hid,aid=_team_id(event,"home"),_team_id(event,"away")
    home_attack,hn=_team_attack_rate(index,hid,now,"home",lh)
    away_attack,an=_team_attack_rate(index,aid,now,"away",la)
    strength=max(home_attack/lh,away_attack/la)
    # Attack-strength gate only acts when both venues have adequate evidence.
    strength_ok=(min(hn,an)<3 or strength<=1.35)
    league_rows=index.league(league_key(event),now,limit=200)
    league_under=sum(sum(outcome_scores(r))<=2 for r in league_rows)
    league_prior=(league_under+25*.5)/(len(league_rows)+25)
    # Beta-smoothed H2H low-goals confidence, not a claimed betting probability.
    prior_weight=5.0
    posterior=(sum((r["total"]<=2)*exp(-log(2)*
               max(0,(now-r["date"]).total_seconds()/86400)/HALF_LIFE_DAYS)
               for r in rows)+prior_weight*league_prior) / (
               sum(exp(-log(2)*max(0,(now-r["date"]).total_seconds()/86400)/
                   HALF_LIFE_DAYS) for r in rows)+prior_weight)
    # Approximate one-sided uncertainty penalty, conservative screening only.
    lower=posterior-.8*sqrt(posterior*(1-posterior)/(n_eff+prior_weight+1))
    reliability_ok=n_eff>=2.4 and lower>=.42
    gates={"recency":recent_ok,"venue":venue_ok,"strength":strength_ok,
           "reliability":reliability_ok}
    score=100*max(0,min(1,(low*.30+(1-min(1,avg/3))*.2+
                 (1-min(1,std/2))*.2+(n_eff/(n_eff+6))*.15+
                 max(0,min(1,lower))*.15)))
    out["features"]={"recency_mean":round(avg,4),"recency_sd":round(std,4),
                     "recency_low_share":round(low,4),
                     "recent3_total_mean":round(recent_avg,4),
                     "same_venue_h2h":len(venue_rows),
                     "current_home_attack_rate":round(home_attack,4),
                     "current_away_attack_rate":round(away_attack,4),
                     "opponent_attack_strength_ratio":round(strength,4),
                     "current_venue_samples":min(hn,an),
                     "league_under_prior":round(league_prior,4),
                     "low_goals_posterior":round(posterior,4),
                     "conservative_low_goals_lower":round(lower,4),
                     "effective_h2h_n":round(n_eff,4),
                     "stability_quality_index":round(score,2)}
    out["gates"]=gates
    out["variants"]={"legacy":original["prioritized"],
                     **{key:original["prioritized"] and passed for key,passed in gates.items()},
                     "combined":original["prioritized"] and all(gates.values())}
    out["candidate"]=True
    return out
