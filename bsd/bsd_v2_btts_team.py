"""Modele BTTS par la probabilite que chaque equipe marque.

Les deux evenements (domicile marque, visiteur marque) sont appris
separement sur les scores de 2024. Toutes les features sont disponibles
avant le coup d'envoi et la composante reste un challenger valide hors
echantillon avant activation. Aucun xG ni blessure ne sont inventes.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, log

from bsd_h2h import _team_id
from bsd_v2_core import fixture_datetime, league_key, outcome_scores
from bsd_v2_btts import _rates

FEATURE_NAMES = (
    "intercept", "own_score", "opponent_concedes",
    "own_venue_scores", "opponent_venue_concedes", "league_scores",
    "venue_support",
)


def _clip(p):
    return max(.025, min(.975, float(p)))


def _sigmoid(x):
    return 1. / (1. + exp(-max(-25., min(25., x))))


def _league_rates(event, index, at):
    games = index.league(league_key(event), at, limit=300)
    n = len(games)
    goals_h = sum(outcome_scores(g)[0] > 0 for g in games)
    goals_a = sum(outcome_scores(g)[1] > 0 for g in games)
    # Shrink toward historically typical scoring frequencies.
    return ((goals_h + 50*.75)/(n+50),
            (goals_a + 50*.69)/(n+50), n)


def scoring_features(event, index, *, min_team=5):
    """Pre-match feature rows for home and away scoring indicators."""
    hid, aid = _team_id(event, "home"), _team_id(event, "away")
    if not hid or not aid or hid == aid:
        return None
    at = fixture_datetime(event)
    hg, ag = index.team(hid, at, limit=14), index.team(aid, at, limit=14)
    if min(len(hg), len(ag)) < min_team:
        return None
    hv = index.team(hid, at, limit=12, venue="home")
    av = index.team(aid, at, limit=12, venue="away")
    hgf, hga, _ = _rates(hg, hid, at)
    agf, aga, _ = _rates(ag, aid, at)
    hvgf, hvga, hw = _rates(hv, hid, at, venue="home")
    avgf, avga, aw = _rates(av, aid, at, venue="away")
    wh, wa = hw/(hw+6.), aw/(aw+6.)
    hvgf = wh*hvgf+(1-wh)*hgf
    hvga = wh*hvga+(1-wh)*hga
    avgf = wa*avgf+(1-wa)*agf
    avga = wa*avga+(1-wa)*aga
    lh, la, ln = _league_rates(event, index, at)
    home = (1., hgf-.7, aga-.7, hvgf-.7, avga-.7, lh-.7, min(hw,8.)/8.-.5)
    away = (1., agf-.7, hga-.7, avgf-.7, hvga-.7, la-.7, min(aw,8.)/8.-.5)
    return home, away, {"home_venue_matches":len(hv),
                        "away_venue_matches":len(av),
                        "league_matches":ln}


def _fit_logistic(rows, prior):
    """L2 penalised independent binary scoring regression, stdlib only."""
    if not rows:
        return ()
    p = min(.95, max(.05, prior))
    w = [log(p/(1-p))] + [0.]*(len(FEATURE_NAMES)-1)
    for epoch in range(230):
        grad = [0.]*len(w)
        for x,y in rows:
            delta = _sigmoid(sum(a*b for a,b in zip(w,x)))-y
            for j in range(len(w)):
                grad[j] += delta*x[j]
        rate = 2.0/(1.+epoch/160.)
        for j in range(len(w)):
            penalty = .0025*w[j] if j else 0.
            w[j] -= rate*(grad[j]/len(rows)+penalty)
            w[j] = max(-7., min(7., w[j]))
    return tuple(w)


@dataclass(frozen=True)
class TeamScoringModel:
    home_weights: tuple
    away_weights: tuple
    trained_games: int
    training_year: int = 2024

    def predict(self, home_features, away_features):
        if len(home_features)!=len(self.home_weights) or len(away_features)!=len(self.away_weights):
            raise ValueError("Team-scoring feature length changed")
        return (_clip(_sigmoid(sum(a*b for a,b in zip(self.home_weights, home_features)))),
                _clip(_sigmoid(sum(a*b for a,b in zip(self.away_weights, away_features)))))


def fit_team_scoring_model(index, fixtures, *, max_training=3600):
    """Fit exclusively on supplied 2024 Jan-Aug finished fixtures."""
    rows_h, rows_a = [], []
    selected = sorted(fixtures,key=lambda e:(e["event_date"],str(e["id"])))
    if len(selected)>max_training:
        selected=[selected[int(i*len(selected)/max_training)] for i in range(max_training)]
    for event in selected:
        at=fixture_datetime(event)
        if at.year!=2024 or at.month>8:
            raise ValueError("Team scoring training must stay in 2024 Jan-Aug")
        pair = scoring_features(event,index)
        scores = outcome_scores(event)
        if pair is None or scores is None:
            continue
        fh, fa, _ = pair
        rows_h.append((fh, int(scores[0]>0)))
        rows_a.append((fa, int(scores[1]>0)))
    if len(rows_h)<100:
        return None
    return TeamScoringModel(_fit_logistic(rows_h, .75),
                            _fit_logistic(rows_a, .69), len(rows_h))


def team_scoring_probabilities(event,index,*,model=None,min_team=5):
    """Side-specific scoring probabilities and their independent product.

    The model is trained on past games; the caller selects its mixture on
    the 2024 holdout and verifies it against an untouched 2025 holdout.
    """
    pair=scoring_features(event,index,min_team=min_team)
    if pair is None:return None
    home,away,meta=pair
    if model is None:
        # Safe deterministic fallback for tests / shadow diagnostics.
        hp=_clip(.75 + .9*home[1]+.4*home[2]+.3*home[5])
        ap=_clip(.69 + .9*away[1]+.4*away[2]+.3*away[5])
    else:
        hp,ap=model.predict(home,away)
    return {"home_scores":hp,"away_scores":ap,
            "home_blank":1-hp,"away_blank":1-ap,
            "btts_yes":_clip(hp*ap),**meta}
