"""Leakage-safe 5/10-match form features for ML V2 exact-score research.

Each row: (UTC_day, team_goals, opponent_goals, prior_opponent_strength, venue).
Team histories MUST be league-scoped and committed only after ALL predictions
for that calendar date. Missing form is explicit, never presented as 0% form.
"""
from __future__ import annotations

from datetime import date

WINDOWS = (5, 10)
STATS = (
    "games", "goals_for_avg", "goals_against_avg", "goal_diff_avg",
    "points_per_game", "win_rate", "draw_rate", "loss_rate",
    "clean_sheet_rate", "failed_to_score_rate", "both_score_rate",
    "over25_rate", "rest_days", "missing",
)
SCOPES = ("overall", "venue")
SIDES = ("home", "away")
FORM_FEATURE_NAMES = tuple(
    f"{side}_{scope}_last{window}_{stat}"
    for side in SIDES
    for window in WINDOWS
    for scope in SCOPES
    for stat in STATS
)

def window_features(records, day):
    """Calculate independent statistics; no state updates, no same-day games."""
    if not isinstance(day, date):
        raise TypeError("Expected UTC date for feature cutoff")
    if not records:
        return (0.0,) * (len(STATS) - 1) + (1.0,)
    for entry in records:
        if entry[0] >= day:
            raise ValueError("Current/future match would leak into form features")
        if entry[1] < 0 or entry[2] < 0:
            raise ValueError("Invalid negative goals in team history")
    n = len(records)
    gf = sum(row[1] for row in records)
    ga = sum(row[2] for row in records)
    wins = sum(row[1] > row[2] for row in records)
    draws = sum(row[1] == row[2] for row in records)
    losses = n - wins - draws
    return (
        float(n), gf/n, ga/n, (gf-ga)/n,
        (3*wins+draws)/n, wins/n, draws/n, losses/n,
        sum(row[2] == 0 for row in records)/n,
        sum(row[1] == 0 for row in records)/n,
        sum(row[1] > 0 and row[2] > 0 for row in records)/n,
        sum(row[1]+row[2] >= 3 for row in records)/n,
        float((day-records[-1][0]).days), 0.0,
    )

def team_form(history, target_venue, cutoff):
    """Return overall & target-venue-specific form for last 5 and 10."""
    if target_venue not in ("home", "away"):
        raise ValueError("Target venue must be home/away")
    for rec in history:
        if rec[0] >= cutoff:
            raise ValueError("Same-day or future outcomes in form history")
        if len(rec) < 5 or rec[4] not in ("home", "away"):
            raise ValueError("Incomplete venue information in history")
    # Keep only prior results; history is maintained chronologically by FormState.
    if any(history[i][0] > history[i+1][0] for i in range(len(history)-1)):
        raise ValueError("Nonchronological team history")
    venue_records=[row for row in history if row[4]==target_venue]
    output=[]
    for n in WINDOWS:
        output.extend(window_features(history[-n:],cutoff))
        output.extend(window_features(venue_records[-n:],cutoff))
    return tuple(output)

def form_quality(history, venue, cutoff):
    """Diagnostics, not extra predictive variables."""
    return {
        "overall_last5":min(5,len(history)),
        "overall_last10":min(10,len(history)),
        "venue_last5":min(5,sum(r[4]==venue for r in history)),
        "venue_last10":min(10,sum(r[4]==venue for r in history)),
    }
