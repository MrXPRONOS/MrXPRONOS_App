"""BSD V3 shadow: exact 40-market catalogue derived from ONE coherent score matrix.
No bookmaker code inference, no publishing, no Supabase.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Mapping

@dataclass(frozen=True)
class Spec:
    number: int
    key: str
    group: str
    label: str

ROWS = [
    (1,"DC_1X","outcome","Double chance 1X"),
    (2,"DC_X2","outcome","Double chance X2"),
    (3,"TOTAL_UNDER_55","total","Moins de 5,5 buts"),
    (4,"TOTAL_OVER_05","total","Plus de 0,5 but"),
    (5,"TOTAL_UNDER_45","total","Moins de 4,5 buts"),
    (6,"TOTAL_OVER_15","total","Plus de 1,5 but"),
    (7,"TOTAL_UNDER_35","total","Moins de 3,5 buts"),
    (8,"TOTAL_OVER_25","total","Plus de 2,5 buts"),
    (9,"TOTAL_UNDER_25","total","Moins de 2,5 buts"),
    (10,"BTTS_NO","btts","Les deux equipes marquent : Non"),
    (11,"BTTS_YES","btts","Les deux equipes marquent : Oui"),
    (12,"DNB_HOME","dnb","Domicile Draw No Bet"),
    (13,"DNB_AWAY","dnb","Exterieur Draw No Bet"),
    (14,"HOME_OVER_05","team_goals","Domicile plus de 0,5 but"),
    (15,"AWAY_OVER_05","team_goals","Exterieur plus de 0,5 but"),
    (16,"HOME_UNDER_25","team_goals","Domicile moins de 2,5 buts"),
    (17,"AWAY_UNDER_25","team_goals","Exterieur moins de 2,5 buts"),
    (18,"RESULT_HOME","outcome","Victoire domicile"),
    (19,"RESULT_AWAY","outcome","Victoire exterieur"),
    (20,"RESULT_DRAW","outcome","Match nul"),
    (21,"HANDICAP_HOME_P15","handicap","Domicile handicap +1,5"),
    (22,"HANDICAP_AWAY_P15","handicap","Exterieur handicap +1,5"),
    (23,"HANDICAP_HOME_P25","handicap","Domicile handicap +2,5"),
    (24,"HANDICAP_AWAY_P25","handicap","Exterieur handicap +2,5"),
    (25,"HOME_OVER_15","team_goals","Domicile plus de 1,5 but"),
    (26,"AWAY_OVER_15","team_goals","Exterieur plus de 1,5 but"),
    (27,"HOME_UNDER_15","team_goals","Domicile moins de 1,5 but"),
    (28,"AWAY_UNDER_15","team_goals","Exterieur moins de 1,5 but"),
    (29,"CLEAN_HOME","btts","Domicile clean sheet"),
    (30,"CLEAN_AWAY","btts","Exterieur clean sheet"),
    (31,"WIN_TO_NIL_HOME","btts","Domicile gagne sans encaisser"),
    (32,"WIN_TO_NIL_AWAY","btts","Exterieur gagne sans encaisser"),
    (33,"TOTAL_OVER_35","total","Plus de 3,5 buts"),
    (34,"TOTAL_OVER_45","total","Plus de 4,5 buts"),
    (35,"TOTAL_UNDER_15","total","Moins de 1,5 but"),
    (36,"HOME_OVER_25","team_goals","Domicile plus de 2,5 buts"),
    (37,"AWAY_OVER_25","team_goals","Exterieur plus de 2,5 buts"),
    (38,"TOTAL_RANGE_2_3","total","Exactement 2 ou 3 buts"),
    (39,"TOTAL_RANGE_3_4","total","Exactement 3 ou 4 buts"),
    (40,"TOTAL_EXACT_2","total","Exactement 2 buts"),
]
SPECS = tuple(Spec(*row) for row in ROWS)
BY_KEY = {s.key:s for s in SPECS}
assert len(SPECS)==40 and len(BY_KEY)==40 and {s.number for s in SPECS}==set(range(1,41))

def result(key:str, h:int, a:int)->str:
    """Return win/lose/push; completed matches only. No double-counted goals."""
    if not all(type(n) is int and n >= 0 for n in (h,a)):
        raise ValueError("Final scores must be nonnegative integers")
    if key not in BY_KEY: raise KeyError(key)
    t=h+a
    if key=="DNB_HOME": return "push" if h==a else ("win" if h>a else "lose")
    if key=="DNB_AWAY": return "push" if h==a else ("win" if a>h else "lose")
    win = {
      "DC_1X": h>=a, "DC_X2": a>=h,
      "TOTAL_UNDER_55":t<=5, "TOTAL_OVER_05":t>=1,
      "TOTAL_UNDER_45":t<=4, "TOTAL_OVER_15":t>=2,
      "TOTAL_UNDER_35":t<=3, "TOTAL_OVER_25":t>=3,
      "TOTAL_UNDER_25":t<=2,
      "BTTS_NO":not(h>0 and a>0),"BTTS_YES":h>0 and a>0,
      "HOME_OVER_05":h>=1,"AWAY_OVER_05":a>=1,
      "HOME_UNDER_25":h<=2,"AWAY_UNDER_25":a<=2,
      "RESULT_HOME":h>a,"RESULT_AWAY":a>h,"RESULT_DRAW":h==a,
      "HANDICAP_HOME_P15":h-a>=-1,"HANDICAP_AWAY_P15":a-h>=-1,
      "HANDICAP_HOME_P25":h-a>=-2,"HANDICAP_AWAY_P25":a-h>=-2,
      "HOME_OVER_15":h>=2,"AWAY_OVER_15":a>=2,
      "HOME_UNDER_15":h<=1,"AWAY_UNDER_15":a<=1,
      "CLEAN_HOME":a==0,"CLEAN_AWAY":h==0,
      "WIN_TO_NIL_HOME":h>a and a==0,"WIN_TO_NIL_AWAY":a>h and h==0,
      "TOTAL_OVER_35":t>=4,"TOTAL_OVER_45":t>=5,
      "TOTAL_UNDER_15":t<=1,
      "HOME_OVER_25":h>=3,"AWAY_OVER_25":a>=3,
      "TOTAL_RANGE_2_3":t in (2,3),"TOTAL_RANGE_3_4":t in (3,4),
      "TOTAL_EXACT_2":t==2
    }[key]
    return "win" if win else "lose"

def probabilities(matrix:Mapping[tuple[int,int],float])->list[dict]:
    """All 40 prices derive from one normalized P(home goals,away goals)."""
    if not matrix or abs(sum(matrix.values())-1.0)>1e-5:
        raise ValueError("Score probabilities must sum to one")
    if any(not(isinstance(h,int) and isinstance(a,int) and h>=0 and a>=0
               and isfinite(float(p)) and 0<=p<=1) for (h,a),p in matrix.items()):
        raise ValueError("Invalid score matrix")
    output=[]
    for spec in SPECS:
        p={"win":0.,"push":0.,"lose":0.}
        for (h,a),mass in matrix.items():
            p[result(spec.key,h,a)] += mass
        win,push,lose=p["win"],p["push"],p["lose"]
        fair = (1-push)/win if win>0 else None
        output.append({
            "number":spec.number,"key":spec.key,"family":spec.group,
            "label":spec.label,"probability":round(win,9),
            "push_probability":round(push,9),"lose_probability":round(lose,9),
            "fair_odds":round(fair,6) if fair is not None else None,
            "market_code":None,"recommendation_eligible":False
        })
    return output

def settle_market(key:str, *, status:str,home_score=None,away_score=None)->str:
    """Never settle abandoned/postponed/incomplete fixtures from fabricated zeros."""
    status=(status or "").lower().replace("_","")
    if status in ("cancelled","canceled","abandoned","void"):
        return "void"
    if status != "finished" or home_score is None or away_score is None:
        return "pending"
    return result(key,home_score,away_score)
