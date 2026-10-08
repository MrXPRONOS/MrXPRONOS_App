"""Modèle BTTS Oui/Non spécialisé, sans dépendance ML externe.

Entraînement: janvier-août 2024. Choix du mélange avec Poisson/Dixon-Coles:
septembre-décembre 2024. Calibration: début 2025 (par bsd_v2_policies).
Validation qualité: fin 2025. Backtest 2026 indépendant.

Toutes les variables viennent de matchs terminés au moins quatre heures
avant le coup d'envoi. Aucun corner, tir ou faute.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from math import exp, log
from typing import Iterable, Optional

from bsd_h2h import _team_id
from bsd_v2_core import fixture_datetime, league_key, outcome_scores, estimate_goals, score_matrix, markets_from_matrix

BASE_RATE = 0.50
FEATURE_COUNT = 11
FEATURE_LABELS = ("intercept", "home_scores", "away_scores", "home_concedes",
                  "away_concedes", "home_venue_scores", "away_venue_scores",
                  "home_venue_concedes", "away_venue_concedes",
                  "league_btts", "joint_scoring_strength")


def _clamp(p):
    return max(.01, min(.99, float(p)))


def _sigmoid(z):
    z = max(-30.0, min(30.0, z))
    return 1.0 / (1.0 + exp(-z))


def _rates(games, team_id, kickoff, *, venue=None):
    score_num = concede_num = weight_sum = 0.0
    for match in games:
        scores = outcome_scores(match)
        if scores is None:
            continue
        home = _team_id(match, "home") == team_id
        if venue and home != (venue == "home"):
            continue
        scored, conceded = (scores if home else scores[::-1])
        age = max(0, (kickoff - fixture_datetime(match)).total_seconds()/86400)
        weight = exp(-log(2.0) * age / 90.0)
        weight_sum += weight
        score_num += weight * int(scored > 0)
        concede_num += weight * int(conceded > 0)
    # Beta-like shrinkage towards league-agnostic prior, to control sparse form.
    return ((score_num + 4 * .72)/(weight_sum + 4),
            (concede_num + 4 * .72)/(weight_sum + 4),
            weight_sum)


def _opponent_adjusted_scoring(games,team_id,index,at,league_prior):
    """Each scored-goal occurrence weighted by opponents' past clean-sheet rate."""
    values=[]
    for match in games:
        score=outcome_scores(match)
        if score is None:continue
        home=_team_id(match,"home")==team_id
        scored=score[0 if home else 1]
        opponent=_team_id(match,"away" if home else "home")
        previous=index.team(opponent,at,limit=12) if opponent else []
        conceded_frequency=[]
        for past in previous:
            old=outcome_scores(past)
            if old is None:continue
            opponent_home=_team_id(past,"home")==opponent
            conceded=old[1 if opponent_home else 0]
            conceded_frequency.append(int(conceded>0))
        concede_rate=(sum(conceded_frequency)+6*league_prior)/(len(conceded_frequency)+6)
        strength=max(.80,min(1.20,league_prior/max(.25,concede_rate)))
        age=max(0.,(at-fixture_datetime(match)).total_seconds()/86400)
        values.append((int(scored>0)*strength,exp(-log(2.)*age/90.)))
    weight=sum(w for _v,w in values)
    return min(.99,max(.01,(sum(v*w for v,w in values)+5*league_prior)/(weight+5)))


def btts_features(event, index):
    """Features pre-match only, returns None for teams without enough recent form."""
    hid, aid = _team_id(event, "home"), _team_id(event, "away")
    if not hid or not aid or hid == aid:
        return None
    try:
        at = fixture_datetime(event)
    except (ValueError, TypeError):
        return None
    home_games = index.team(hid, at, limit=14)
    away_games = index.team(aid, at, limit=14)
    if min(len(home_games), len(away_games)) < 5:
        return None
    hgf, hga, _ = _rates(home_games, hid, at)
    agf, aga, _ = _rates(away_games, aid, at)
    home_venue = index.team(hid, at, limit=12, venue="home")
    away_venue = index.team(aid, at, limit=12, venue="away")
    # When venue sample is weak, the general form carries most of the weight.
    hvgf, hvga, hw = _rates(home_venue, hid, at, venue="home")
    avgf, avga, aw = _rates(away_venue, aid, at, venue="away")
    hv_weight = hw / (hw + 6.)
    av_weight = aw / (aw + 6.)
    hvgf = hv_weight*hvgf + (1-hv_weight)*hgf
    hvga = hv_weight*hvga + (1-hv_weight)*hga
    avgf = av_weight*avgf + (1-av_weight)*agf
    avga = av_weight*avga + (1-av_weight)*aga
    games = index.league(league_key(event), at, limit=300)
    btts_wins = sum(int(x["home_score"] > 0 and x["away_score"] > 0)
                    for x in games if outcome_scores(x) is not None)
    league_p = (btts_wins + 35*BASE_RATE)/(len(games) + 35)
    # Strength adjustment: the opponent's tendency to concede matters as
    # much as the team's own tendency to score.
    adjusted_home=_opponent_adjusted_scoring(home_games,hid,index,at,.72)
    adjusted_away=_opponent_adjusted_scoring(away_games,aid,index,at,.72)
    home_scoring = .45*hvgf + .35*avga + .20*adjusted_home
    away_scoring = .45*avgf + .35*hvga + .20*adjusted_away
    return (1.0, hgf-.5, agf-.5, hga-.5, aga-.5,
            hvgf-.5, avgf-.5, hvga-.5, avga-.5,
            league_p-.5, home_scoring*away_scoring-.36)


@dataclass(frozen=True)
class BTTSModel:
    weights: tuple
    blend: float = 0.0
    train_count: int = 0
    validation_count: int = 0

    def predict_specialized(self, features):
        if features is None:
            return None
        if len(features) != len(self.weights):
            raise ValueError("BTTS feature dimensionality changed")
        return _clamp(_sigmoid(sum(w*x for w,x in zip(self.weights,features))))

    def predict(self, event, index, baseline_probability):
        features = btts_features(event,index)
        p = self.predict_specialized(features)
        if p is None:
            return baseline_probability
        return _clamp((1.0-self.blend)*baseline_probability + self.blend*p)

    def to_dict(self):
        return {"version":"btts-model-1","weights":list(self.weights),
                "blend":self.blend,"train_count":self.train_count,
                "validation_count":self.validation_count}


def btts_candidates(event, index, candidates, model=None):
    """Override ONLY BTTS_YES/BTTS_NO with complementary estimated probabilities."""
    if model is None:
        return candidates
    original = next((c.probability for c in candidates if c.key=="BTTS_YES"),None)
    if original is None:
        return candidates
    p = model.predict(event,index,original)
    return [replace(c,probability=p if c.key=="BTTS_YES" else 1.-p)
            if c.key in ("BTTS_YES","BTTS_NO") else c for c in candidates]


def _train_logistic(rows, epochs=220):
    # Deterministic full-batch gradient descent with mild L2 penalty.
    weights = [0.0]*FEATURE_COUNT
    if not rows:
        return tuple(weights)
    for iteration in range(epochs):
        gradient = [0.0]*FEATURE_COUNT
        for x,y in rows:
            diff = _sigmoid(sum(a*b for a,b in zip(weights,x))) - y
            for j in range(FEATURE_COUNT):
                gradient[j] += diff*x[j]
        eta = 2.0/(1.0 + iteration/220)
        for j in range(FEATURE_COUNT):
            reg = .003*weights[j] if j>0 else 0.0
            weights[j] -= eta*(gradient[j]/len(rows) + reg)
            weights[j] = max(-8.0,min(8.0,weights[j]))
    return tuple(weights)


def fit_btts_model(index, *, rho=0.0, max_training=1800, max_validation=450):
    """2024 time-split fit and validation; V2 keeps Poisson if BTTS model worse."""
    training, validation = [], []
    for _timestamp,event in index.global_games:
        try:
            at = fixture_datetime(event)
            if at.year != 2024:
                continue
            feat = btts_features(event,index)
            if feat is None:
                continue
            scores = outcome_scores(event)
            y = int(scores[0]>0 and scores[1]>0)
            if at.month<=8:
                training.append((at,feat,y))
            else:
                validation.append((at,event,feat,y))
        except (TypeError,ValueError,KeyError):
            continue
    training.sort(key=lambda t:t[0])
    validation.sort(key=lambda t:t[0])
    def sample(items, n):
        if len(items) <= n:
            return items
        return [items[int(i*len(items)/n)] for i in range(n)]
    training=sample(training,max_training)
    validation=sample(validation,max_validation)
    weights=_train_logistic([(features,y) for _,features,y in training])
    provisional=BTTSModel(weights,1.0,len(training),len(validation))
    observed=[]
    for _at,event,features,y in validation:
        expected,reason=estimate_goals(event,index)
        if expected is None:
            continue
        p0=next(c.probability for c in markets_from_matrix(
            score_matrix(expected["home"],expected["away"],rho)) if c.key=="BTTS_YES")
        p1=provisional.predict_specialized(features)
        observed.append((p0,p1,y))
    def loss(blend):
        return sum(((1-blend)*p0+blend*p1-y)**2 for p0,p1,y in observed)/len(observed)
    if len(training)<100 or len(observed)<50:
        chosen=0.0
        stats={"reason":"insufficient_2024_training_or_validation"}
    else:
        candidates=(0.0,.25,.50,.75,1.0)
        best=min(candidates,key=loss)
        chosen=best if loss(best) <= loss(0.0)-.001 else 0.0
        stats={"poisson_validation_brier":round(loss(0.0),6),
               "specialized_validation_brier":round(loss(1.0),6),
               "chosen_validation_brier":round(loss(chosen),6),
               "validation_observations":len(observed)}
    return BTTSModel(weights,chosen,len(training),len(observed)),{
        "training_period":"2024-01 to 2024-08",
        "validation_period":"2024-09 to 2024-12",
        "trained":len(training),"validated":len(observed),
        "blend":chosen,**stats,
    }
