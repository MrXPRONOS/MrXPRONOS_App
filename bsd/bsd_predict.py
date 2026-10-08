"""Moteur expérimental BSD : forme, H2H et modèle de Poisson.

Aucune cote de bookmaker, aucun modèle ML entraîné, aucune garantie de réussite.
Toutes les données historiques sont filtrées AVANT le coup d'envoi.
"""
from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from datetime import datetime
from math import exp, factorial
from typing import Any, Dict, List, Optional, Tuple

from bsd_h2h import _team_id, _utc, _valid_score, local_h2h
from bsd_markets import candidates_from_goals, select_best

STATUS_OK = frozenset(("notstarted", "upcoming"))
BASE_GOALS_HOME = 1.43
BASE_GOALS_AWAY = 1.20


def _name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or "").strip()
    return str(value or "").strip()


def _league(event: dict) -> str:
    return _name(event.get("league_name") or event.get("league") or event.get("competition"))


def _goals(event: dict) -> Optional[Tuple[int, int]]:
    home, away = _valid_score(event.get("home_score")), _valid_score(event.get("away_score"))
    return (home, away) if home is not None and away is not None else None


def _mean(values: List[float], default: float) -> float:
    return sum(values) / len(values) if values else default


def _clip(value: float, lo: float, hi: float) -> float:
    return min(max(value, lo), hi)


class HistoryIndex:
    """Indexes created once per run, not 49k full scans per fixture."""

    def __init__(self, matches: List[dict]):
        self.teams = defaultdict(list)
        self.pairs = defaultdict(list)
        seen = set()
        self.eligible = 0
        for match in matches:
            if not isinstance(match, dict) or str(match.get("status") or "").lower() != "finished":
                continue
            mid = match.get("id")
            hid, aid = _team_id(match, "home"), _team_id(match, "away")
            if mid is None or str(mid) in seen or not hid or not aid or hid == aid or _goals(match) is None:
                continue
            try:
                when = _utc(str(match.get("event_date") or "")).timestamp()
            except (ValueError, TypeError):
                continue
            seen.add(str(mid))
            self.teams[hid].append((when, match))
            self.teams[aid].append((when, match))
            self.pairs[tuple(sorted((hid, aid)))].append((when, match))
            self.eligible += 1
        self.team_times = {}
        self.pair_times = {}
        for team_id, items in self.teams.items():
            items.sort(key=lambda pair: pair[0])
            self.team_times[team_id] = [item[0] for item in items]
        for pair, items in self.pairs.items():
            items.sort(key=lambda entry: entry[0])
            self.pair_times[pair] = [item[0] for item in items]

    def _before(self, items, times, timestamp, limit):
        end = bisect_left(times, timestamp)
        return [match for _, match in items[max(0, end - limit):end]][::-1]

    def recent(self, team_id: int, kickoff: str, limit: int = 10, venue: Optional[str] = None):
        stamp = _utc(kickoff).timestamp()
        items = self.teams.get(team_id, [])
        times = self.team_times.get(team_id, [])
        # Scan only the most recent 120 games to find a venue subset.
        fetched = self._before(items, times, stamp, 120 if venue else limit)
        if venue:
            fetched = [m for m in fetched if _team_id(m, venue) == team_id]
        return fetched[:limit]

    def h2h(self, home_id: int, away_id: int, kickoff: str, years: int = 3):
        pair = tuple(sorted((home_id, away_id)))
        items = self.pairs.get(pair, [])
        times = self.pair_times.get(pair, [])
        recent = self._before(items, times, _utc(kickoff).timestamp(), 60)
        return local_h2h(recent, home_id, away_id, kickoff, years=years)


def team_form(team_id: int, matches: List[dict]) -> Dict[str, Any]:
    gf, ga, points = [], [], []
    for match in matches:
        score = _goals(match)
        if score is None:
            continue
        hid = _team_id(match, "home")
        scored, conceded = score if hid == team_id else score[::-1]
        gf.append(scored)
        ga.append(conceded)
        points.append(3 if scored > conceded else 1 if scored == conceded else 0)
    n = len(gf)
    return {
        "played": n,
        "goals_for": round(_mean(gf, 0.0), 3) if n else None,
        "goals_against": round(_mean(ga, 0.0), 3) if n else None,
        "points_per_match": round(_mean(points, 0.0), 3) if n else None,
        "score": round(sum(points) / (3 * n), 4) if n else None,
    }


def poisson_markets(home_xg: float, away_xg: float, max_goals: int = 10) -> Dict[str, float]:
    # Normalize truncated tail before returning any probabilities.
    ph = [exp(-home_xg) * home_xg ** i / factorial(i) for i in range(max_goals + 1)]
    pa = [exp(-away_xg) * away_xg ** i / factorial(i) for i in range(max_goals + 1)]
    p1 = px = p2 = over = total = 0.0
    for h, h_prob in enumerate(ph):
        for a, a_prob in enumerate(pa):
            prob = h_prob * a_prob
            total += prob
            if h > a:
                p1 += prob
            elif h == a:
                px += prob
            else:
                p2 += prob
            if h + a >= 3:
                over += prob
    return {
        "home_win": p1 / total,
        "draw": px / total,
        "away_win": p2 / total,
        "over_25": over / total,
    }


def _estimated_goals(form_all: dict, form_venue: dict, opponent: dict, baseline: float) -> float:
    # Prior explicit, no fabricated match statistics. Smoothed over short samples.
    att = (form_all["goals_for"] * form_all["played"] + 4 * baseline) / (form_all["played"] + 4)
    opp = (opponent["goals_against"] * opponent["played"] + 4 * baseline) / (opponent["played"] + 4)
    estimate = .57 * att + .43 * opp
    if form_venue["played"] >= 3:
        venue_goals = (form_venue["goals_for"] * form_venue["played"] + 3 * baseline) / (form_venue["played"] + 3)
        estimate = .75 * estimate + .25 * venue_goals
    return _clip(estimate, 0.35, 3.5)


def predict_fixture(
    fixture: dict,
    index: HistoryIndex,
    *,
    min_games: int = 3,
    min_double_chance: float = 0.67,
    clock: Optional[datetime] = None,
    calibration=None,
) -> Tuple[Optional[dict], str]:
    """Returns (derived prediction, reason); never uses post-kickoff evidence."""
    status = str(fixture.get("status") or "").lower()
    if status not in STATUS_OK:
        return None, "not_upcoming"
    hid, aid = _team_id(fixture, "home"), _team_id(fixture, "away")
    if not hid or not aid or hid == aid:
        return None, "team_ids_missing"
    if fixture.get("id") is None:
        return None, "event_id_missing"
    try:
        kickoff = _utc(str(fixture.get("event_date") or ""))
    except (ValueError, TypeError):
        return None, "invalid_kickoff"
    if clock is not None and kickoff <= clock:
        return None, "already_started"
    kickoff_str = kickoff.isoformat()
    home_games = index.recent(hid, kickoff_str)
    away_games = index.recent(aid, kickoff_str)
    if len(home_games) < min_games or len(away_games) < min_games:
        return None, "insufficient_form"
    hf = team_form(hid, home_games)
    af = team_form(aid, away_games)
    home_venue = team_form(hid, index.recent(hid, kickoff_str, venue="home"))
    away_venue = team_form(aid, index.recent(aid, kickoff_str, venue="away"))

    xg_h = _estimated_goals(hf, home_venue, af, BASE_GOALS_HOME)
    xg_a = _estimated_goals(af, away_venue, hf, BASE_GOALS_AWAY)
    probs = poisson_markets(xg_h, xg_a)
    h2h = index.h2h(hid, aid, kickoff_str)
    # Le marché est sélectionné parmi tous les résultats et totals de buts.
    # H2H disponible à titre informatif; ne pas déformer la distribution de scores.
    choice, ranking = select_best(candidates_from_goals(xg_h, xg_a), calibration=calibration)
    if choice is None:
        return None, "no_reliable_market"
    selected = choice["candidate"]
    dc_prob = choice["calibrated_probability"]
    quality = round(100 * min(1, (min(hf["played"], af["played"]) / 10)))
    category = "vip" if choice["conservative_probability"] >= .80 and quality >= 90 and choice["calibration_samples"] >= 100 else "pro" if choice["conservative_probability"] >= .73 and quality >= 60 else "simple"
    confidence = round(100 * dc_prob, 1)
    # These categories are experimental and not claims of real-world hit rate.
    prediction = {
        "id": "bsd:" + str(fixture["id"]),
        "source": "bsd",
        "source_event_id": fixture["id"],
        "date": kickoff.date().isoformat(),
        "event_date": kickoff_str,
        "home_team": _name(fixture.get("home_team")) or ("Equipe " + str(hid)),
        "away_team": _name(fixture.get("away_team")) or ("Equipe " + str(aid)),
        "home_team_id": hid,
        "away_team_id": aid,
        "league": _league(fixture),
        "home_score": None,
        "away_score": None,
        "status": "notstarted",
        "is_finished": False,
        "verified_double": False,
        "verified_over": False,
        "prediction": {
            "double_chance": selected.outcome if selected.market == "double_chance" else None,
            "type": selected.label,
            "market": selected.market,
            "outcome": selected.outcome,
            "line": selected.line,
            "market_code": selected.market_code,
            "selection_key": selected.key,
            "confidence": confidence,
            "conservative_confidence": round(100 * choice["conservative_probability"], 1),
            "fair_odds": choice["model_fair_odds"],
            "calibration_samples": choice["calibration_samples"],
            "over_25": probs["over_25"] >= .5,
            "over_25_probability": round(probs["over_25"], 4),
        },
        "market_ranking": [{"market_code": x["candidate"].market_code, "label": x["candidate"].label,
                            "conservative_probability": x["conservative_probability"],
                            "calibrated_probability": x["calibrated_probability"]} for x in ranking[:5]],
        "home_form": hf,
        "away_form": af,
        "h2h_analysis": h2h,
        "estimated_goals": {"home": round(xg_h, 3), "away": round(xg_a, 3)},
        "probabilities": {k: round(v, 4) for k, v in probs.items()},
        "xpronos_score": confidence,
        "ml_score": None,
        "final_score": confidence,
        "quality_score": quality,
        "category": category,
        "badge": "TEST BSD - NON VALIDE",
        "model_version": "bsd-markets-v1-calibration-optional",
    }
    return prediction, "ok"
