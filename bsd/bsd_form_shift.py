"""Pre-match team form-regime change detector for H2H and BSD V2.

A scoreline in an old H2H is contextual evidence, not a forecast of today's
attacking state. This module only uses scores available before each kickoff.

All alert thresholds are *research hypotheses*, not calibrated confidence or
evidence of changed players; only match results are available from BSD.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import exp, log
from bsd_h2h import _team_id
from bsd_v2_core import fixture_datetime,outcome_scores

VERSION="bsd-form-drift-shadow-v1"
SHORT=5
LONG=15

def _rate(matches, team):
    n=0;gf=ga=0.
    for event in matches:
        score=outcome_scores(event)
        if score is None:continue
        home=_team_id(event,"home")==team
        gf+=score[0] if home else score[1]
        ga+=score[1] if home else score[0]
        n+=1
    return {"n":n,"scored":gf/n if n else None,
            "conceded":ga/n if n else None}

def _delta(now,old,field):
    if now["n"]<4 or old["n"]<4:return None
    return now[field]-old[field]

def _team_profile(index,team,at,venue):
    all_games=index.team(team,at,limit=LONG)
    recent=_rate(all_games[:SHORT],team)
    previous=_rate(all_games[SHORT:LONG],team)
    venue_games=index.team(team,at,venue=venue,limit=8)
    venue_recent=_rate(venue_games[:4],team)
    venue_old=_rate(venue_games[4:8],team)
    return {"recent":recent,"previous":previous,
            "attack_delta":_delta(recent,previous,"scored"),
            "defence_delta":_delta(recent,previous,"conceded"),
            "venue_recent":venue_recent,"venue_previous":venue_old,
            "venue_attack_delta":_delta(venue_recent,venue_old,"scored"),
            "venue_defence_delta":_delta(venue_recent,venue_old,"conceded")}

def _past_h2h_context(fixture,index,hindex):
    """What each team was scoring BEFORE its historical H2H meeting.

    Must not look up team form at the target fixture and pretend that was the
    team's form at the earlier meeting.
    """
    from exact_scores_h2h_v2 import meetings_before
    home=_team_id(fixture,"home");away=_team_id(fixture,"away")
    meetings=meetings_before(fixture,hindex,limit=8,years=4)
    h_attack=[];a_attack=[];h_concede=[];a_concede=[]
    for meeting in meetings:
        at=meeting["date"]
        hs=_rate(index.team(home,at,limit=8),home)
        aws=_rate(index.team(away,at,limit=8),away)
        if hs["n"]>=4 and aws["n"]>=4:
            h_attack.append(hs["scored"]);a_attack.append(aws["scored"])
            h_concede.append(hs["conceded"]);a_concede.append(aws["conceded"])
    if len(h_attack)<2:return {"meetings":len(meetings),"form_samples":len(h_attack)}
    avg=lambda vals:sum(vals)/len(vals)
    return {"meetings":len(meetings),"form_samples":len(h_attack),
            "home_scored_then":avg(h_attack),"away_scored_then":avg(a_attack),
            "home_conceded_then":avg(h_concede),"away_conceded_then":avg(a_concede)}

def form_shift(fixture,index,hindex=None,*,expected=None,under25=None,direction=None,
               include_h2h=True):
    """Structured 5/15-vs-past + historical-H2H + venue + model agreement flags.

    A risk flag implies uncertainty, not a prediction that goals will exceed 2.5.
    No risk is declared from missing samples alone; report evidence counts.
    """
    at=fixture_datetime(fixture)
    home,away=_team_id(fixture,"home"),_team_id(fixture,"away")
    if not home or not away or home==away:return {"valid":False,"reason":"missing_teams"}
    hp=_team_profile(index,home,at,"home")
    ap=_team_profile(index,away,at,"away")
    if min(hp["recent"]["n"],ap["recent"]["n"])<4:
        return {"valid":False,"reason":"insufficient_recent_form"}
    flags={}
    def up(key,value,threshold):
        flags[key]=bool(value is not None and value>=threshold)
    def down(key,value,threshold):
        flags[key]=bool(value is not None and value<=-threshold)
    # Changes in both direction and magnitude (means of scored/conceded).
    up("home_attack_surged",hp["attack_delta"],.75)
    up("away_attack_surged",ap["attack_delta"],.75)
    down("home_attack_collapsed",hp["attack_delta"],.70)
    down("away_attack_collapsed",ap["attack_delta"],.70)
    up("home_defence_weakened",hp["defence_delta"],.75)
    up("away_defence_weakened",ap["defence_delta"],.75)
    down("home_defence_strengthened",hp["defence_delta"],.70)
    down("away_defence_strengthened",ap["defence_delta"],.70)
    up("home_venue_attack_surged",hp["venue_attack_delta"],.80)
    up("away_venue_attack_surged",ap["venue_attack_delta"],.80)
    up("home_venue_defence_weakened",hp["venue_defence_delta"],.80)
    up("away_venue_defence_weakened",ap["venue_defence_delta"],.80)
    h2h_context={"meetings":0,"form_samples":0}
    if include_h2h and hindex is not None:
        h2h_context=_past_h2h_context(fixture,index,hindex)
        if h2h_context["form_samples"]>=2:
            up("home_vs_old_h2h_attack_jump",
               hp["recent"]["scored"]-h2h_context["home_scored_then"],.85)
            up("away_vs_old_h2h_attack_jump",
               ap["recent"]["scored"]-h2h_context["away_scored_then"],.85)
            up("home_vs_old_h2h_defence_worse",
               hp["recent"]["conceded"]-h2h_context["home_conceded_then"],.85)
            up("away_vs_old_h2h_defence_worse",
               ap["recent"]["conceded"]-h2h_context["away_conceded_then"],.85)
    attack_alert=flags["home_attack_surged"] or flags["away_attack_surged"]
    defence_alert=flags["home_defence_weakened"] or flags["away_defence_weakened"]
    venue_alert=any(flags[k] for k in ("home_venue_attack_surged",
                       "away_venue_attack_surged","home_venue_defence_weakened",
                       "away_venue_defence_weakened"))
    old_context_alert=any(v for k,v in flags.items() if "_vs_old_h2h_" in k)
    # Only contradictions against a conservative low-scoring interpretation.
    projected=(float(expected["home"])+float(expected["away"])) if expected else None
    model_conflict=(projected is not None and projected>=2.75
                    and under25 is not None and under25>=.62)
    home_form=hp["recent"]["scored"]-ap["recent"]["conceded"]
    away_form=ap["recent"]["scored"]-hp["recent"]["conceded"]
    # A Double Chance orientation is not proof of outright victory.
    dc_contradiction=bool(direction and (
      (direction.get("direction")=="home" and away_form-home_form>=.8) or
      (direction.get("direction")=="away" and home_form-away_form>=.8)))
    flags["under25_goals_model_conflict"]=model_conflict
    flags["dc_recent_form_conflict"]=dc_contradiction
    alert_count=sum((attack_alert,defence_alert,venue_alert,old_context_alert,model_conflict))
    # Ablations allow evaluation of each independent new signal.
    variants={
        "legacy":True,
        "recent_attack":not attack_alert,
        "recent_defence":not defence_alert,
        "historical_h2h_context":not old_context_alert,
        "venue_shift":not venue_alert,
        "model_agreement":not (model_conflict or dc_contradiction),
        "combined":not (alert_count>=2 or (model_conflict and attack_alert)),
        "strict":not any((attack_alert,defence_alert,venue_alert,
                          old_context_alert,model_conflict,dc_contradiction)),
    }
    # For BSD singles: only question *low-scoring* market families on a
    # credible upward scoring/defence change. Never veto unrelated over markets.
    upward=attack_alert or defence_alert or venue_alert or old_context_alert
    bsd_veto=bool((upward and alert_count>=2) or model_conflict)
    return {"valid":True,"version":VERSION,"home":hp,"away":ap,
        "historic_h2h_form":h2h_context,"flags":flags,"variant_pass":variants,
        "positive_drift_components":alert_count,
        "upward_scoring_risk":upward,
        "bsd_low_goals_veto":bsd_veto,
        "current_expected_total":projected,
        "under25_probability":under25,
        "direction":direction.get("direction") if direction else None}

def simple_market_veto_keys(shift):
    """Allowed only in research opt-in BSD V2 comparison, never global deploy."""
    if not shift or not shift.get("valid") or not shift.get("bsd_low_goals_veto"):
        return ()
    return ("UNDER_15","UNDER_25","UNDER_35","BTTS_NO","X")

