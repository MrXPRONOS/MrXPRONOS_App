"""Estimation BTTS par la probabilite de marquer de CHAQUE equipe.

Pas de xG inventes: seules les frequences avant coup d'envoi sont utilisees.
Utilise en challenger; son melange est choisi sur une validation chronologique.
"""
from __future__ import annotations

from bsd_h2h import _team_id
from bsd_v2_core import fixture_datetime, league_key, outcome_scores
from bsd_v2_btts import _rates


def _clip(p):
    return max(.03, min(.97, p))


def team_scoring_probabilities(event, index, *, min_team=5):
    """Returns P(home scores), P(away scores), P(BTTS) or None.

    League and venue rates are shrunk to recent global team form to avoid
    overfitting to tiny home/away samples. Everything is point-in-time.
    """
    home_id = _team_id(event, "home")
    away_id = _team_id(event, "away")
    if not home_id or not away_id or home_id == away_id:
        return None
    at = fixture_datetime(event)
    home_recent = index.team(home_id, at, limit=14)
    away_recent = index.team(away_id, at, limit=14)
    if min(len(home_recent), len(away_recent)) < min_team:
        return None
    home_venue = index.team(home_id, at, limit=12, venue="home")
    away_venue = index.team(away_id, at, limit=12, venue="away")

    h_score, h_concede, _ = _rates(home_recent, home_id, at)
    a_score, a_concede, _ = _rates(away_recent, away_id, at)
    hv_score, hv_concede, hn = _rates(home_venue, home_id, at)
    av_score, av_concede, an = _rates(away_venue, away_id, at)
    home_w = hn / (hn + 8.)
    away_w = an / (an + 8.)
    hv_score = home_w * hv_score + (1 - home_w) * h_score
    hv_concede = home_w * hv_concede + (1 - home_w) * h_concede
    av_score = away_w * av_score + (1 - away_w) * a_score
    av_concede = away_w * av_concede + (1 - away_w) * a_concede

    # Opponent's clean-sheet rate matters. In particular, whether the
    # away side can score against THIS home defence.
    home_p = .35*h_score + .25*hv_score + .20*a_concede + .20*av_concede
    away_p = .35*a_score + .25*av_score + .20*h_concede + .20*hv_concede

    league_games = index.league(league_key(event), at, limit=300)
    if league_games:
        home_hits = sum(outcome_scores(g)[0] > 0 for g in league_games)
        away_hits = sum(outcome_scores(g)[1] > 0 for g in league_games)
        l_home = (home_hits + 40*.72)/(len(league_games)+40)
        l_away = (away_hits + 40*.68)/(len(league_games)+40)
        league_w = min(.20, len(league_games)/(len(league_games)+180)*.25)
        home_p = (1-league_w)*home_p + league_w*l_home
        away_p = (1-league_w)*away_p + league_w*l_away

    home_p, away_p = _clip(home_p), _clip(away_p)
    return {
        "home_scores": home_p,
        "away_scores": away_p,
        "home_blank": 1-home_p,
        "away_blank": 1-away_p,
        "btts_yes": _clip(home_p*away_p),
        "home_venue_matches": len(home_venue),
        "away_venue_matches": len(away_venue),
        "league_matches": len(league_games),
    }
