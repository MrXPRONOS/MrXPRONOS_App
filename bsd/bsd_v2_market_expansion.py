"""Seven experimental BSD V2 markets, isolated from production publication.

Four team-goal markets, handicap +1.5 (both sides), draw-no-bet (both
sides, including void/refund), first-half under 1.5 (observed HT required).
No retrospective bookmaker prices are generated.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import exp, isfinite

@dataclass(frozen=True)
class ExtendedMarket:
    key: str
    market_code: str
    family: str
    probability: float | None
    refund_probability: float = 0.0

FT_KEYS = (
    "HOME_OVER_05", "AWAY_OVER_05", "HOME_UNDER_15", "AWAY_UNDER_15",
    "AH_HOME_PLUS_15", "AH_AWAY_PLUS_15", "DNB_HOME", "DNB_AWAY",
)
ALL_KEYS = FT_KEYS + ("HT_UNDER_15",)

def first_half_scores(event):
    """Only explicit historical half-time scores can settle first-half bets."""
    for hk, ak in (
        ("ht_home_score", "ht_away_score"),
        ("home_ht_score", "away_ht_score"),
        ("half_time_home_score", "half_time_away_score"),
        ("home_score_ht", "away_score_ht"),
    ):
        h, a = event.get(hk), event.get(ak)
        if type(h) is int and type(a) is int and min(h,a)>=0:
            return h,a
    return None

def half_time_share(training_events, *, min_matches=100):
    """Train from 2024 observed HT/FT scores alone; unavailable means None."""
    ht_total=ft_total=found=0
    for e in training_events:
        if not str(e.get("event_date") or "").startswith("2024-"):
            continue
        ht=first_half_scores(e)
        h,a=e.get("home_score"),e.get("away_score")
        if ht is None or type(h) is not int or type(a) is not int:
            continue
        if not (0<=ht[0]<=h and 0<=ht[1]<=a):
            continue
        found+=1
        ht_total+=sum(ht)
        ft_total+=h+a
    if found<min_matches or ft_total==0:
        return None,{"training_2024_ht_matches":found,"required":min_matches,
                     "reason":"missing_or_insufficient_observed_first_half_scores"}
    ratio=max(.20,min(.65,ht_total/ft_total))
    return ratio,{"training_2024_ht_matches":found,"ratio":round(ratio,6),
                  "reason":"trained_2024_only"}

def candidates(matrix, *, home_xg=None, away_xg=None, halftime_share=None):
    """Nine independent outcomes across seven new bet families."""
    if not isinstance(matrix,dict) or not matrix:
        raise ValueError("Score matrix missing")
    if any(not isinstance(h,int) or not isinstance(a,int) or h<0 or a<0
           or not isfinite(float(p)) or p<0
           for (h,a),p in matrix.items()):
        raise ValueError("Invalid score matrix")
    mass=sum(matrix.values())
    if not .999<=mass<=1.001:
        raise ValueError("Score matrix must sum to one")
    def prob(f):
        return sum(float(p) for (h,a),p in matrix.items() if f(h,a))/mass
    draw=prob(lambda h,a:h==a)
    home_win=prob(lambda h,a:h>a)
    away_win=prob(lambda h,a:a>h)
    options=[
        ExtendedMarket("HOME_OVER_05","HOME_TEAM_OVER_0.5_FT","team_goals",prob(lambda h,a:h>=1)),
        ExtendedMarket("AWAY_OVER_05","AWAY_TEAM_OVER_0.5_FT","team_goals",prob(lambda h,a:a>=1)),
        ExtendedMarket("HOME_UNDER_15","HOME_TEAM_UNDER_1.5_FT","team_goals",prob(lambda h,a:h<=1)),
        ExtendedMarket("AWAY_UNDER_15","AWAY_TEAM_UNDER_1.5_FT","team_goals",prob(lambda h,a:a<=1)),
        ExtendedMarket("AH_HOME_PLUS_15","ASIAN_HANDICAP_HOME_+1.5_FT","asian_handicap",prob(lambda h,a:h+1.5>a)),
        ExtendedMarket("AH_AWAY_PLUS_15","ASIAN_HANDICAP_AWAY_+1.5_FT","asian_handicap",prob(lambda h,a:a+1.5>h)),
        ExtendedMarket("DNB_HOME","DRAW_NO_BET_HOME_FT","dnb",home_win,draw),
        ExtendedMarket("DNB_AWAY","DRAW_NO_BET_AWAY_FT","dnb",away_win,draw),
    ]
    ht=None
    if halftime_share is not None:
        if (home_xg is None or away_xg is None or not 0<halftime_share<1
                or not 0<home_xg<=5 or not 0<away_xg<=5):
            raise ValueError("Incomplete first-half trained model")
        lam=(home_xg+away_xg)*halftime_share
        ht=exp(-lam)*(1+lam)
    options.append(ExtendedMarket("HT_UNDER_15","TOTAL_UNDER_1.5_HT","first_half_goals",ht))
    return options

def outcome(key,home,away,*,half_time=None):
    """1=win, 0=loss, -1=push/refund, None=unobserved halftime."""
    if type(home) is not int or type(away) is not int or min(home,away)<0:
        raise ValueError("Missing or invalid final score")
    if key=="HOME_OVER_05":return int(home>=1)
    if key=="AWAY_OVER_05":return int(away>=1)
    if key=="HOME_UNDER_15":return int(home<=1)
    if key=="AWAY_UNDER_15":return int(away<=1)
    if key=="AH_HOME_PLUS_15":return int(home+1.5>away)
    if key=="AH_AWAY_PLUS_15":return int(away+1.5>home)
    if key=="DNB_HOME":return -1 if home==away else int(home>away)
    if key=="DNB_AWAY":return -1 if home==away else int(away>home)
    if key=="HT_UNDER_15":
        if half_time is None:return None
        h,a=half_time
        if not (type(h) is int and type(a) is int
                and 0<=h<=home and 0<=a<=away):
            return None
        return int(h+a<1.5)
    raise ValueError("Unknown extended market: "+str(key))
