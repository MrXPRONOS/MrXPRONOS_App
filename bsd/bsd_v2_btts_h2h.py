"""Strict BTTS last head-to-head rule, evaluated exclusively before kickoff.

BTTS YES is eligible only when both teams scored in their latest completed
meeting; BTTS NO only when at least one failed to score. Missing H2H means
no BTTS pick. Reverse home/away order is accepted. This is a selection
filter, NOT a predictor or a claimed performance improvement.

Use only the local V2History archive, never an API 'current H2H' summary:
future results could leak into historical backtests.
"""
from __future__ import annotations

from bisect import bisect_right

from bsd_h2h import _team_id
from bsd_v2_core import fixture_datetime, outcome_scores


BTTS_KEYS = frozenset(("BTTS_YES", "BTTS_NO"))


def last_completed_h2h(event, index):
    """Return latest valid, settled H2H in the point-in-time index, or None.

    V2History exposes team matches indexed by *availability* timestamp
    (kickoff + settlement delay) rather than just by match kickoff.
    We search ALL earlier matches for the team, not just its last 12.
    """
    home, away = _team_id(event, "home"), _team_id(event, "away")
    if home is None or away is None or home == away:
        return None
    kickoff = fixture_datetime(event)
    games = index.teams.get(home, ())
    times = index.team_times.get(home, ())
    i = bisect_right(times, kickoff.timestamp()) - 1
    while i >= 0:
        _, previous = games[i]
        i -= 1
        h, a = _team_id(previous, "home"), _team_id(previous, "away")
        if not ((h == home and a == away) or (h == away and a == home)):
            continue
        # Strictly earlier, even in the presence of delayed/odd timestamps.
        if fixture_datetime(previous) >= kickoff:
            continue
        scores = outcome_scores(previous)
        if scores is None:
            continue
        return {
            "event_id": previous["id"],
            "event_date": fixture_datetime(previous).isoformat(),
            "home_team_id": h,
            "away_team_id": a,
            "home_score": scores[0],
            "away_score": scores[1],
            "btts_yes": scores[0] > 0 and scores[1] > 0,
        }
    return None


def btts_h2h_decision(event, index, selection_key):
    """Return (passed, reason, last_match) for an individual BTTS market."""
    if selection_key not in BTTS_KEYS:
        return True, "not_btts", None
    previous = last_completed_h2h(event, index)
    if previous is None:
        return False, "btts_last_h2h_missing", None
    wanted_yes = selection_key == "BTTS_YES"
    if previous["btts_yes"] != wanted_yes:
        return False, "btts_last_h2h_lost", previous
    return True, "btts_last_h2h_won", previous


def filter_candidates_by_last_h2h(event, index, candidates, market_audit=None):
    """Remove BTTS candidates that lost the last prior H2H; leave all others."""
    previous = last_completed_h2h(event, index)
    remaining = []
    for c in candidates:
        if c.key not in BTTS_KEYS:
            remaining.append(c)
            continue
        if previous is None:
            reason = "btts_last_h2h_missing"
        elif previous["btts_yes"] != (c.key == "BTTS_YES"):
            reason = "btts_last_h2h_lost"
        else:
            remaining.append(c)
            continue
        if market_audit is not None:
            market_audit.append({
                "key": c.key,
                "family": "btts",
                "result": reason,
                "last_h2h": previous,
            })
    return remaining, previous
