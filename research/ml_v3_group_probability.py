#!/usr/bin/env python3
"""Pure, PREMATCH group-mass feature for research B; never inspects full-time scores.

The five experimental groups are immutable and must agree with the earlier
research. They are NOT guaranteed actual 1xBet offered markets.
"""
from __future__ import annotations
import math
import numpy as np

FROZEN_GROUPS = {
    "H_LOW": ("1:0", "2:0", "2:1"),
    "H_HIGH": ("3:0", "3:1", "3:2"),
    "A_LOW": ("0:1", "0:2", "1:2"),
    "A_HIGH": ("0:3", "1:3", "2:3"),
    "DRAW_LOW": ("0:0", "1:1", "2:2"),
}
SCORE_TO_GROUP = {s: group for group, scores in FROZEN_GROUPS.items() for s in scores}
assert len(SCORE_TO_GROUP) == len(FROZEN_GROUPS) * 3


def grid_group_mass(grid, modal_score):
    """Return only group of the original modal score and PREMATCH grid mass.

    Does not choose a different group or access outcomes. Uses the native
    normalized 11x11 grid with no rounding before summing three cells.
    """
    p = np.asarray(grid, dtype=float)
    if p.shape != (11, 11) or not np.isfinite(p).all() or (p < 0).any():
        raise ValueError("Invalid prematch Hybrid V3 probability grid")
    if not math.isclose(float(p.sum()), 1., abs_tol=2e-5, rel_tol=0):
        raise ValueError("Probability grid must be normalized")
    if (not isinstance(modal_score, str) or modal_score.count(":") != 1):
        raise ValueError("Invalid modal exact score")
    try:
        h, a = (int(v) for v in modal_score.split(":"))
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid modal score coordinates") from exc
    if (not (0 <= h <= 10 and 0 <= a <= 10)
            or modal_score != f"{h}:{a}"):
        raise ValueError("Invalid modal score coordinates")
    # Tie resolution must match np.argmax in single_ml_v2.
    i, j = np.unravel_index(int(np.argmax(p)), p.shape)
    if (i, j) != (h, a):
        raise ValueError("Modal score disagrees with original ML V3 grid")
    group = SCORE_TO_GROUP.get(modal_score)
    confidence = float(p[h, a])
    if group is None:
        return {"group": "", "group_probability": 0.0,
                "modal_probability": confidence}
    score_mass = float(sum(p[tuple(map(int, s.split(":")))] for s in FROZEN_GROUPS[group]))
    if (not 0 <= confidence <= score_mass + 1e-12
            or score_mass > 1 + 1e-12):
        raise ValueError("Group probability violates score inclusion")
    return {"group": group, "group_probability": score_mass,
            "modal_probability": confidence}
