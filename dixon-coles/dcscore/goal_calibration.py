"""Time-isolated goal calibration and diagnostics for Dixon-Coles.

Every input score used to fit this calibration predates the forecast cutoff.
A candidate goal multiplier is learned on an older segment and accepted only
if it improves proper log loss on a strictly later, PRE-CUTOFF validation
segment. No October 2026 score is used to tune the October baseline.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from math import isfinite, log
from scipy.optimize import minimize_scalar

from .domain import Match, utc_datetime
from .model import DCModel, ModelError, fit, p_score, one_x_two, validate_tau

LOW, HIGH = 0.85, 1.20

@dataclass(frozen=True)
class GoalCalibration:
    multiplier: float = 1.0
    status: str = "BASELINE_UNVALIDATED"
    train_count: int = 0
    calibration_count: int = 0
    validation_count: int = 0
    validation_baseline_nll: float | None = None
    validation_candidate_nll: float | None = None
    validation_baseline_goal_mae: float | None = None
    validation_candidate_goal_mae: float | None = None
    estimate: float = 1.0
    reason: str = ""

    def as_json(self) -> dict:
        return asdict(self)


def _observations(model: DCModel, rows: list[Match]):
    out = []
    for match in rows:
        if match.status != "FINISHED":
            continue
        if match.home_id not in model.alpha or match.away_id not in model.alpha:
            continue
        try:
            lam, mu = model.expected_goals(match.home_id, match.away_id,
                                            neutral_venue=match.neutral_venue)
        except ModelError:
            continue
        out.append((lam, mu, model.rho, match.home_goals, match.away_goals))
    return out


def _metrics(observations, multiplier: float) -> tuple[float, float]:
    """Mean exact-score negative log likelihood and goal-sum MAE."""
    nll, mae = 0., 0.
    for lam, mu, rho, home, away in observations:
        a, b = lam * multiplier, mu * multiplier
        validate_tau(a, b, rho)
        likelihood = p_score(a, b, rho, home, away)
        if likelihood <= 0 or not isfinite(likelihood):
            raise ModelError("Score likelihood nonpositive or invalid")
        nll -= log(likelihood)
        mae += abs((home + away) - (a + b))
    return nll / len(observations), mae / len(observations)


def select_goal_multiplier(rows: list[Match], *, as_of: datetime,
                           min_training: int = 80, min_calibration: int = 18,
                           min_validation: int = 18,
                           maxiter: int = 350) -> GoalCalibration:
    """Train (-120 days), calibrate (-120 to -60), validate (-60 to cutoff).

    Both calibration and validation predictions are from earlier-time models,
    never from fits containing their own eventual outcomes. The rolling
    production forecast is fitted separately on all pre-cutoff history.
    """
    cutoff = utc_datetime(as_of)
    calibration_start = cutoff - timedelta(days=120)
    validation_start = cutoff - timedelta(days=60)
    previous = sorted((m for m in rows if m.status == "FINISHED"
                       and m.kickoff < cutoff), key=lambda m: (m.kickoff, m.id))
    early = [m for m in previous if m.kickoff < calibration_start]
    calib = [m for m in previous if calibration_start <= m.kickoff < validation_start]
    valid = [m for m in previous if validation_start <= m.kickoff < cutoff]
    if len(early) < min_training or len(calib) < min_calibration or len(valid) < min_validation:
        return GoalCalibration(status="BASELINE_INSUFFICIENT_HISTORY",
            train_count=len(early), calibration_count=len(calib),
            validation_count=len(valid), reason="Insufficient chronological partitions")
    try:
        first = fit(early, as_of=calibration_start, min_games=min_training,
                    regularization=.15, maxiter=maxiter)
        o_cal = _observations(first, calib)
        if len(o_cal) < min_calibration:
            return GoalCalibration(status="BASELINE_UNSEEN_TEAMS",
                train_count=len(early), calibration_count=len(o_cal),
                validation_count=len(valid),
                reason="Insufficient calibrated fixtures with known team IDs")
        # Prior log-scale penalty prevents chasing single unusually high scores.
        def objective(scale):
            return _metrics(o_cal, scale)[0] + .35 * (log(scale) ** 2)
        result = minimize_scalar(objective, bounds=(LOW, HIGH), method="bounded",
                                 options={"xatol": 0.0001})
        if not result.success:
            raise ModelError("Calibration optimizer failed")
        candidate = float(result.x)
        # Learn on an older slice, validate on a later completely disjoint slice.
        intermediate = [m for m in previous if m.kickoff < validation_start]
        fitted = fit(intermediate, as_of=validation_start, min_games=min_training,
                     regularization=.15, maxiter=maxiter)
        o_valid = _observations(fitted, valid)
        if len(o_valid) < min_validation:
            return GoalCalibration(status="BASELINE_INSUFFICIENT_VALIDATION",
                train_count=len(early), calibration_count=len(o_cal),
                validation_count=len(o_valid), estimate=round(candidate, 4))
        base_nll, base_mae = _metrics(o_valid, 1.0)
        new_nll, new_mae = _metrics(o_valid, candidate)
        # The score likelihood must meaningfully improve on true held-out data.
        # Goal MAE cannot substantially degrade. These gates are fixed in advance.
        accept = (new_nll + .005 < base_nll and new_mae <= base_mae + .03
                  and abs(candidate-1.) >= .012)
        return GoalCalibration(
            multiplier=round(candidate, 4) if accept else 1.0,
            estimate=round(candidate, 4),
            status="VALIDATED_ADJUSTMENT" if accept else "BASELINE_VALIDATION_REJECTED",
            train_count=len(early), calibration_count=len(o_cal),
            validation_count=len(o_valid),
            validation_baseline_nll=round(base_nll, 6),
            validation_candidate_nll=round(new_nll, 6),
            validation_baseline_goal_mae=round(base_mae, 6),
            validation_candidate_goal_mae=round(new_mae, 6),
            reason="Independent pre-cutoff validation; no in-sample acceptance",
        )
    except (ModelError, ValueError, FloatingPointError) as exc:
        return GoalCalibration(status="BASELINE_CALIBRATION_ERROR",
            train_count=len(early), calibration_count=len(calib),
            validation_count=len(valid), reason=f"{type(exc).__name__}: {str(exc)[:130]}")
