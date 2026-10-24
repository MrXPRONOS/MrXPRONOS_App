"""Prequential calibration of independent ML and Dixon-Coles score forecasts.

The independent Dixon-Coles model uses team form + an earlier-day fitted rho;
the goal-rate ML uses its own learned goal intensities. Both 11x11 grids are
frozen before the match, and their AFTER-match outcomes only calibrate a
future date's blend. No outcomes from the target day, invented odds or xG.

The weight specifies contribution of the independent DC probability grid.
An uncalibrated 35% reference is explicitly marked as a fallback.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from datetime import date
import math
import numpy as np

HYBRID_VERSION = "independent_ml_dc_walkforward_linear_pool_v1"
DEFAULT_DC_WEIGHT = .35
WEIGHT_GRID = tuple(round(i / 20., 2) for i in range(21))
MIN_CALIBRATION_MATCHES = 80
MIN_CALIBRATION_DAYS = 12
MAX_CALIBRATION_MATCHES = 3000
HALF_LIFE_DAYS = 180

def valid_grid(grid):
    p = np.asarray(grid, dtype=float)
    if p.shape != (11, 11) or not np.isfinite(p).all() or (p < 0).any():
        raise ValueError("Hybrid requires a finite nonnegative 11x11 score grid")
    mass = float(p.sum())
    if not np.isfinite(mass) or mass <= 0 or abs(mass - 1.) > 1e-4:
        raise ValueError("Unnormalized/invalid hybrid probability mass")
    return p / mass

def blend(ml_grid, dc_grid, dc_weight):
    """Linear probability pool: both forecast distributions are independent."""
    if not np.isfinite(dc_weight) or not 0 <= dc_weight <= 1:
        raise ValueError("DC blend weight outside [0,1]")
    a, b = valid_grid(ml_grid), valid_grid(dc_grid)
    result = (1. - dc_weight) * a + dc_weight * b
    return result / result.sum()

@dataclass(frozen=True)
class PastHybridForecast:
    day: date
    match_id: str
    ml_grid: np.ndarray
    dc_grid: np.ndarray
    home_goals: int
    away_goals: int

    def __post_init__(self):
        if not isinstance(self.day, date) or not str(self.match_id):
            raise ValueError("Historical hybrid needs UTC day and match identity")
        if (not isinstance(self.home_goals, int) or
            not isinstance(self.away_goals, int) or
            not (0 <= self.home_goals <= 10 and 0 <= self.away_goals <= 10)):
            raise ValueError("Historical hybrid outcome outside 0..10")
        a, b = valid_grid(self.ml_grid), valid_grid(self.dc_grid)
        # Frozen copies: never allow mutation after creating pregame snapshots.
        a = a.copy()
        b = b.copy()
        a.flags.writeable = False
        b.flags.writeable = False
        object.__setattr__(self, "ml_grid", a)
        object.__setattr__(self, "dc_grid", b)

@dataclass(frozen=True)
class CalibratedHybrid:
    dc_weight: float
    calibrated: bool
    asof: date
    training_games: int
    training_days: int
    candidate_metrics: tuple[dict, ...]
    note: str
    version: str = HYBRID_VERSION

def calibrate(history, *, asof, min_matches=MIN_CALIBRATION_MATCHES,
              min_days=MIN_CALIBRATION_DAYS, max_games=MAX_CALIBRATION_MATCHES,
              half_life_days=HALF_LIFE_DAYS):
    """Optimize only past OUT-OF-SAMPLE predictions. No historical label reuse.

    Chronological records are validated, including same-day result isolation.
    A dated forecast is not eligible until the day AFTER it was settled.
    """
    if not isinstance(asof, date):
        raise ValueError("Hybrid needs as-of UTC date")
    if min_matches < 1 or min_days < 1 or max_games < min_matches or half_life_days < 1:
        raise ValueError("Invalid calibration configuration")
    previous = list(history)
    last_day = None
    seen = set()
    for row in previous:
        if not isinstance(row, PastHybridForecast) or row.day >= asof:
            raise ValueError("Future/current-day scores leaked into hybrid calibration")
        if last_day is not None and row.day < last_day:
            raise ValueError("Hybrid calibration observations are nonchronological")
        key = (row.day, row.match_id)
        if key in seen:
            raise ValueError("Repeated historical match in hybrid calibration")
        seen.add(key)
        last_day = row.day
    recent = previous[-max_games:]
    days = len({r.day for r in recent})
    if len(recent) < min_matches or days < min_days:
        return CalibratedHybrid(DEFAULT_DC_WEIGHT, False, asof, len(recent),
                                days, (), "insufficient_prior_out_of_sample_forecasts")
    y_ml = np.array([r.ml_grid[r.home_goals, r.away_goals] for r in recent])
    y_dc = np.array([r.dc_grid[r.home_goals, r.away_goals] for r in recent])
    if not np.isfinite(y_ml).all() or not np.isfinite(y_dc).all():
        raise ValueError("Invalid previous-day score probabilities")
    ages = np.array([(asof-r.day).days for r in recent], dtype=float)
    if not (ages >= 1).all():
        raise ValueError("Same-day hybrid historical leak")
    importance = np.maximum(.05, np.exp2(-ages / half_life_days))
    importance /= importance.sum()
    candidates = []
    for weight in WEIGHT_GRID:
        actual_probs = (1-weight)*y_ml + weight*y_dc
        score = float(np.dot(importance, -np.log(np.maximum(actual_probs, 1e-15))))
        # Shrink the learned weight gently toward the predeclared baseline.
        # The penalty vanishes with more independent settled forecasts.
        penalty = (2. / (len(recent)+20.)) * (weight-DEFAULT_DC_WEIGHT)**2
        candidates.append({"dc_weight":weight,"past_log_loss":round(score,8),
                           "regularized_objective":round(score+penalty,8)})
    selected = min(candidates, key=lambda v:
                   (v["regularized_objective"],
                    abs(v["dc_weight"]-DEFAULT_DC_WEIGHT),v["dc_weight"]))
    return CalibratedHybrid(float(selected["dc_weight"]), True, asof,
                            len(recent), days, tuple(candidates),
                            "optimized_only_from_earlier_oos_fulltime_outcomes")

def comparison_metrics(rows, names):
    """Paired-cohort digest for the fixed and optimized hybrids."""
    keys = [{(x["date"],x["id"]) for x in rows.get(name,[])} for name in names]
    shared = set.intersection(*keys) if keys else set()
    report = {"common_match_count":len(shared),"models":{}}
    for name in names:
        subset = [x for x in rows.get(name,[]) if (x["date"],x["id"]) in shared]
        n=len(subset)
        report["models"][name] = ({
            "n":n,"exact_hits":sum(int(x["hit"]) for x in subset),
            "exact_hit_rate_pct":round(100*sum(int(x["hit"]) for x in subset)/n,3),
            "log_loss":round(sum(float(x["log_loss"]) for x in subset)/n,6),
            "predicted_1_1_share_pct":round(100*sum(x["predicted_score"]=="1:1" for x in subset)/n,3),
        } if n else {"n":0,"status":"NOT_EVALUABLE"})
    return report
