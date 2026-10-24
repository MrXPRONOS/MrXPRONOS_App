"""Leakage-proof strength-of-schedule and opponent Elo features (ML-V2 #6).

Pre-match Elo is computed from earlier completed UTC days only. Team history
across competitions is joined ONLY by stable original provider team IDs and
matching normalized club names; league-only names never cross competitions.
Same-day results are processed atomically (snapshot then accumulate updates).

This is an experimental football rating, not an official world ranking.
Teams from disconnected competitions have no validated common league scale;
quality/missing flags expose those limitations to the ML model.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import date
import math
import re
import unicodedata
import numpy as np

OPPONENT_VERSION = "verified_identity_pregame_elo_sos_20261024_v1"
ELO_START = 1500.0
ELO_K = 24.0
ELO_HOME_ADVANTAGE = 65.0
MAX_HISTORY = 10
SIDES = ("home","away")
SCHEDULE_WINDOWS = (5,10)
OPPONENT_STAT_NAMES = (
    "elo_rating_scaled", "elo_prior_games",
    "opponents_last5_elo_scaled", "opponents_last10_elo_scaled",
    "opponents_last5_adjusted_result", "opponents_last10_adjusted_result",
    "opponents_last5_avg_prior_games", "opponents_last10_avg_prior_games",
    "opponents_last5_games", "opponents_last10_games",
    "opponents_last5_missing", "opponents_last10_missing",
    "cross_competition_prior_games", "verified_global_identity",
)
OPPONENT_FEATURE_NAMES = (
    tuple(side+"_"+name for side in SIDES for name in OPPONENT_STAT_NAMES)
    + ("fixture_prior_elo_difference_scaled", "fixture_home_expected_elo_result")
)

def canonical_name(name):
    if not isinstance(name,str) or not name.strip():
        raise ValueError("Club identity is missing")
    s=unicodedata.normalize("NFKD",name)
    return re.sub(r"[^a-z0-9]+","",
        "".join(c for c in s if not unicodedata.combining(c)).casefold())

def identifier(value):
    if value is None or isinstance(value,bool):
        return None
    raw=str(value).strip()
    if not raw or raw.lower() in ("none","null","unknown","0"):
        return None
    if len(raw)>128 or not re.fullmatch(r"[a-zA-Z0-9_-]+",raw):
        raise ValueError("Unverified provider identity format")
    return raw

def competition_key(match):
    comp=identifier(getattr(match,"competition_id",None))
    return ("competition-id",comp) if comp is not None else ("league",canonical_name(match.league))

def team_key(match,side):
    name=match.home if side=="home" else match.away
    raw_id=identifier(getattr(match,side+"_id",None))
    if raw_id:
        return ("global-provider-id",raw_id), canonical_name(name),True
    # Never guess that equal textual names in different leagues are same club.
    return ("local-team",competition_key(match),canonical_name(name)),canonical_name(name),False

def expected_result(home_rating,away_rating):
    """Elo expected score (win=1, draw=.5, loss=0), home edge fixed in advance."""
    return 1./(1.+10.**((away_rating-home_rating-ELO_HOME_ADVANTAGE)/400.))

def actual_result(goals_for,goals_against):
    return 1. if goals_for>goals_against else .5 if goals_for==goals_against else 0.

class OpponentStrengthState:
    """Season-independent online Elo + frozen prior-opponent strength per fixture."""

    def __init__(self):
        self.ratings={}
        self.games=Counter()
        self.history=defaultdict(list)
        self.provider_names={}
        self.competition_counts=defaultdict(Counter)
        self.last_ingested_day=None
        self.seen_ids=set()
        self.audit=Counter()

    def _preview(self,m):
        teams={}
        for side in SIDES:
            key,name,verified=team_key(m,side)
            if verified and key in self.provider_names and self.provider_names[key]!=name:
                raise ValueError("Conflicting provider ID associated to different club names")
            teams[side]=(key,verified,name)
        if teams["home"][0]==teams["away"][0]:
            raise ValueError("Both sides resolved to the same team identity")
        league=competition_key(m)
        rh=self.ratings.get(teams["home"][0],ELO_START)
        ra=self.ratings.get(teams["away"][0],ELO_START)
        p=expected_result(rh,ra)
        return teams,league,rh,ra,p

    def features(self,m):
        if self.last_ingested_day is not None and m.day<=self.last_ingested_day:
            raise ValueError("Opponent strength would use current/future results")
        teams,league,rh,ra,p=self._preview(m)
        per_side=[]
        quality={}
        for side in SIDES:
            key,verified,_=teams[side]
            hist=self.history[key]
            if any(item[0]>=m.day for item in hist):
                raise ValueError("Future opponent played a game inside prematch history")
            def roll(n):
                rows=hist[-n:]
                if not rows:
                    return (0.,0.,0.,0.)
                return (float(np.mean([r[1] for r in rows])),
                        float(np.mean([r[2] for r in rows])),
                        float(np.mean([r[3] for r in rows])),
                        float(len(rows)))
            five,ten=roll(5),roll(10)
            comp=self.competition_counts[key]
            # Only meaningful if a stable source identity has been verified.
            cross=sum(n for source_comp,n in comp.items() if source_comp!=league) if verified else 0
            own_rating=self.ratings.get(key,ELO_START)
            per_side += [
                (own_rating-ELO_START)/400.,float(self.games[key]),
                (five[0]-ELO_START)/400. if five[3] else 0.,
                (ten[0]-ELO_START)/400. if ten[3] else 0.,
                five[1],ten[1],five[2],ten[2],
                five[3],ten[3],
                float(not bool(five[3])),float(not bool(ten[3])),
                float(cross),float(verified),
            ]
            quality[side]={
                "prior_games":int(self.games[key]),
                "opponents_last5_n":int(five[3]),
                "opponents_last10_n":int(ten[3]),
                "verified_global_id":verified,
                "cross_competition_prior_games":int(cross),
                "competition_scope":str(league),
            }
        vector=np.asarray([*per_side,(rh-ra)/400.,p],dtype=float)
        if vector.shape!=(len(OPPONENT_FEATURE_NAMES),) or not np.isfinite(vector).all():
            raise ValueError("Opponent strength vector invalid")
        return vector,quality

    def add_day(self,matches):
        """Validate EVERY match then freeze ALL prematch ratings before updates."""
        matches=list(matches)
        if not matches:return
        day=matches[0].day
        if not isinstance(day,date):
            raise ValueError("Invalid UTC fixture date")
        if self.last_ingested_day is not None and day<=self.last_ingested_day:
            raise ValueError("Duplicate/backdated strength ratings")
        keys=set()
        previews=[]
        new_names={}
        for m in matches:
            if m.day!=day:
                raise ValueError("Mixed dates in one atomic opponent-strength batch")
            if not m.key or m.key in keys or m.key in self.seen_ids:
                raise ValueError("Duplicate opponent-strength match")
            if (not isinstance(m.hg,int) or not isinstance(m.ag,int)
                or min(m.hg,m.ag)<0 or max(m.hg,m.ag)>10):
                raise ValueError("Invalid fulltime football goals")
            teams,league,rh,ra,p=self._preview(m)
            for _side, (key,verified,name) in teams.items():
                if verified:
                    if key in new_names and new_names[key]!=name:
                        raise ValueError("Conflicting provider ID within UTC day")
                    new_names[key]=name
            previews.append((m,teams,league,rh,ra,p))
            keys.add(m.key)
        # The data of a prior match is never retroactively recalculated with
        # the stronger/weaker opponent's rating from a later game.
        deltas=defaultdict(float)
        logs=[]
        for m,teams,league,rh,ra,p in previews:
            hm,aw=teams["home"][0],teams["away"][0]
            home_observed=actual_result(m.hg,m.ag)
            # Mild goal-margin effect (bounded, avoids huge updates on outliers).
            multiplier=min(2.5,1.+.25*max(0,abs(m.hg-m.ag)-1))
            correction=ELO_K*multiplier*(home_observed-p)
            deltas[hm]+=correction
            deltas[aw]-=correction
            logs.extend([
                (hm, (day,ra,home_observed-p,float(self.games[aw]),league)),
                (aw, (day,rh,(1-home_observed)-(1-p),float(self.games[hm]),league)),
            ])
        for team_key_value,change in deltas.items():
            self.ratings[team_key_value]=float(np.clip(
                self.ratings.get(team_key_value,ELO_START)+change,700.,2300.))
        for key,entry in logs:
            self.history[key].append(entry)
            self.history[key]=self.history[key][-MAX_HISTORY:]
            self.games[key]+=1
            self.competition_counts[key][entry[4]]+=1
        self.provider_names.update(new_names)
        self.seen_ids.update(keys)
        self.last_ingested_day=day
        self.audit["processed_matches"]+=len(matches)
        self.audit["matches_both_verified_ids"]+=sum(
            x[1]["home"][1] and x[1]["away"][1] for x in previews)
        self.audit["cross_competition_verified_team_games"]+=sum(
            sum(len(self.competition_counts[x[1][side][0]])>1 for side in SIDES)
            for x in previews)

    def audit_summary(self):
        return {
            "version":OPPONENT_VERSION,
            "matches":self.audit["processed_matches"],
            "verified_both_sides":self.audit["matches_both_verified_ids"],
            "verified_teams":len(self.provider_names),
            "teams_total":len(self.games),
            "global_teams_seen_in_multiple_competitions":sum(
                key[0]=="global-provider-id" and len(self.competition_counts[key])>1
                for key in self.games),
            "identity_policy":"global only for matching verified provider ID + normalized club name, else same competition only",
            "intercompetition_limit":"unlinked league ratings are not claimed comparable",
            "updates":"frozen pregame UTC-day ratings, no same-day leakage",
        }
