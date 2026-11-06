"""Generate coherent multi-market probabilities from a single joint score distribution.

Validated V2 specialized models are retained as shadow challengers; experimental
probability projection is OFF by default and must pass independent backtesting.
"""
from __future__ import annotations

from dataclasses import replace
from math import fsum
from .legacy import score_matrix, markets_from_matrix


def normalized(matrix):
    if not matrix or any(v < 0 for v in matrix.values()):
        raise ValueError("Invalid joint goal distribution")
    total = fsum(matrix.values())
    if total <= 0:
        raise ValueError("Empty joint score distribution")
    return {score: p / total for score, p in matrix.items()}


def tilt_event(matrix, predicate, target, strength=1.0):
    """Reweight an event while preserving a single coherent joint distribution."""
    if not 0 < target < 1 or not 0 <= strength <= 1:
        raise ValueError("Invalid projection target")
    current = fsum(p for score, p in matrix.items() if predicate(score))
    if not 0 < current < 1:
        return normalized(matrix)
    desired = current + strength * (target - current)
    in_scale = desired / current
    out_scale = (1 - desired) / (1 - current)
    return normalized({score: p * (in_scale if predicate(score) else out_scale)
                       for score, p in matrix.items()})


def tilt_result(matrix, target):
    if len(target) != 3 or any(p <= 0 for p in target):
        raise ValueError("Invalid 1X2 target")
    total = fsum(target)
    target = [p / total for p in target]
    current = [fsum(p for (h, a), p in matrix.items() if (h > a, h == a, h < a)[i])
               for i in range(3)]
    scales = [target[i] / current[i] if current[i] else 1 for i in range(3)]
    return normalized({(h, a): p * scales[0 if h > a else 1 if h == a else 2]
                       for (h, a), p in matrix.items()})


def coherent_candidates(expected, rho=0.0, *, outcome_target=None,
                        over_targets=None, btts_target=None, challenger_enabled=False):
    """All markets derive from one joint PMF, so probability laws are guaranteed."""
    matrix = score_matrix(expected["home"], expected["away"], rho)
    if challenger_enabled:
        if outcome_target is not None:
            matrix = tilt_result(matrix, outcome_target)
        # Alternating small projections, shadow-only; not a proof of calibration.
        for _ in range(3):
            for line, target in sorted((over_targets or {}).items()):
                if 0 < target < 1:
                    matrix = tilt_event(matrix, lambda score, n=line: sum(score) > n,
                                        target, strength=.25)
            if btts_target is not None and 0 < btts_target < 1:
                matrix = tilt_event(matrix, lambda score: score[0] > 0 and score[1] > 0,
                                    btts_target, strength=.25)
    return matrix, markets_from_matrix(matrix)


def prove_coherence(rows):
    p = {row.key: row.probability for row in rows}
    eps = 1e-8
    def close(a, b):
        return abs(a - b) < eps
    if not (close(p["1"]+p["X"]+p["2"], 1) and
            close(p["1X"], p["1"]+p["X"]) and
            close(p["X2"], p["X"]+p["2"]) and
            close(p["12"], p["1"]+p["2"]) and
            close(p["BTTS_YES"]+p["BTTS_NO"], 1)):
        raise AssertionError("Broken 1X2/DC/BTTS probability coherence")
    previous = 1.0
    for line in ("15", "25", "35", "45"):
        over = p["OVER_"+line]
        if over > previous + eps or not close(over+p["UNDER_"+line], 1):
            raise AssertionError("Broken goal threshold monotonicity")
        previous = over
    if p["BTTS_YES"] > p["OVER_15"] + eps:
        raise AssertionError("BTTS yes must imply Over 1.5")
    return True
