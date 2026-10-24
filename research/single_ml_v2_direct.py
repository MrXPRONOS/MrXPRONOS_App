#!/usr/bin/env python3
"""Direct EXACT-SCORE multiclass classifier for Mr XPRONOS ML V2.

Unlike the goal-rate regressors, this learns P(full-time score | PREMATCH data)
directly from previously completed football matches. 0..5 goals on each side
form 36 distinct score classes; an overflow class covers all other scores.
It emits the full 0..10 score grid: overflow probability is distributed using
the prematch Poisson tail, NEVER a postmatch/target feature.

No Supabase, Neon, network, bookmaker odds, or data storage here.
This is a research-only model with no promised hit-rate uplift.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

DEFAULT_MAX_GOALS = 5
DEFAULT_MIN_SAMPLES = 800
DEFAULT_MAX_ROWS = 20000
DEFAULT_PRIOR_WEIGHT = 0.15
DIRECT_MODEL_ID = "machine_learning_direct"
DIRECT_MODEL_VERSION = "exact_score_multiclass_hgb_v1_20261024"


def _validate_baseline(baseline, max_goals):
    p = np.asarray(baseline, dtype=float)
    if p.ndim != 2 or p.shape[0] != p.shape[1] or p.shape[0] <= max_goals:
        raise ValueError("Prematch score grid must be square and include tail cells")
    if not np.isfinite(p).all() or np.any(p < 0) or p.sum() <= 0:
        raise ValueError("Invalid prematch score probabilities")
    return p / p.sum()


def direct_score_features(x, base_grid, max_goals=DEFAULT_MAX_GOALS):
    """Return fixed-length classification input and explicit class mapping."""
    p = _validate_baseline(base_grid, max_goals)
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or not np.isfinite(x).all():
        raise ValueError("Direct ML requires a finite one-dimensional prematch vector")
    scores = [(h, a) for h in range(max_goals + 1)
             for a in range(max_goals + 1)] + [(-1, -1)]
    known = p[:max_goals+1, :max_goals+1].reshape(-1)
    tail = max(0., 1. - float(known.sum()))
    return np.concatenate((x, known, np.asarray([tail]))), scores


def exact_score_class(home_goals, away_goals, max_goals=DEFAULT_MAX_GOALS):
    if (not isinstance(home_goals, (int, np.integer))
        or not isinstance(away_goals, (int, np.integer))
        or min(home_goals, away_goals) < 0):
        raise ValueError("Only final nonnegative integral scores are valid labels")
    if home_goals > max_goals or away_goals > max_goals:
        return (max_goals+1)**2
    return home_goals*(max_goals+1)+away_goals


@dataclass(frozen=True)
class DirectScoreFitted:
    estimator: object
    max_goals: int
    samples: int
    label_counts: dict[int, int]
    max_iter: int
    prior_weight: float
    feature_count: int


def train_direct_score(rows, *, min_samples=DEFAULT_MIN_SAMPLES,
                       max_rows=DEFAULT_MAX_ROWS,
                       max_goals=DEFAULT_MAX_GOALS, max_iter=60,
                       max_leaf_nodes=12, learning_rate=.045,
                       l2_regularization=12., prior_weight=DEFAULT_PRIOR_WEIGHT):
    """Rows MUST be (frozen prematch features, frozen prematch score grid,
    final home goals, final away goals), provided in chronological order.

    The calling walk-forward engine holds out the entire prediction day;
    this method NEVER accesses target-day records or fetches data.
    """
    if not isinstance(max_goals, int) or not 1 <= max_goals <= 8:
        raise ValueError("max_goals must be between 1 and 8")
    if max_rows < min_samples or min_samples < 2 or max_iter < 1:
        raise ValueError("Invalid direct classifier training configuration")
    if not 0. <= prior_weight < 1.:
        raise ValueError("prior_weight must be between zero and one")
    # The bounded research history is strictly a trailing training window.
    from collections import deque
    subset = list(deque(rows, maxlen=max_rows))
    if len(subset) < min_samples:
        return None
    vectors, labels = [], []
    expected_features = None
    for vector, base, gh, ga in subset:
        features, _ = direct_score_features(vector, base, max_goals=max_goals)
        if expected_features is None:
            expected_features = len(features)
        if len(features) != expected_features:
            raise ValueError("Inconsistent prematch feature schema in training")
        vectors.append(features)
        labels.append(exact_score_class(gh, ga, max_goals=max_goals))
    classes, counts = np.unique(np.asarray(labels, dtype=int), return_counts=True)
    if len(classes) < 2:
        # Abstain; do not make up a classifier or post-hoc predictions.
        return None
    clf = HistGradientBoostingClassifier(
        loss="log_loss", max_iter=max_iter, max_leaf_nodes=max_leaf_nodes,
        learning_rate=learning_rate, l2_regularization=l2_regularization,
        early_stopping=False, random_state=20261024,
    )
    clf.fit(np.asarray(vectors, dtype=np.float64), np.asarray(labels, dtype=int))
    return DirectScoreFitted(
        estimator=clf, max_goals=max_goals, samples=len(subset),
        label_counts={int(k):int(v) for k, v in zip(classes, counts)},
        max_iter=max_iter, prior_weight=prior_weight,
        feature_count=expected_features,
    )


def direct_grid(fitted, vector, baseline, *, max_goals=None):
    """Full score grid (0..10), normalized and finite; None if untrained.

    Absent score classes are handled via a PRESPECIFIED small prematch
    prior blend, preserving probability mass and avoiding zero log loss.
    """
    if fitted is None:
        return None
    if not isinstance(fitted, DirectScoreFitted):
        raise TypeError("Expected a fitted direct-score classifier")
    cap = fitted.max_goals
    if max_goals is not None and max_goals != cap:
        raise ValueError("Classifier/score cap mismatch")
    base = _validate_baseline(baseline, cap)
    features, _ = direct_score_features(vector, base, max_goals=cap)
    if features.size != fitted.feature_count:
        raise ValueError("Training and prediction feature schema mismatch")
    probs = np.asarray(fitted.estimator.predict_proba(features[None, :])[0], dtype=float)
    labels = np.asarray(fitted.estimator.classes_, dtype=int)
    if (len(probs) != len(labels) or not np.isfinite(probs).all()
        or (probs < 0).any() or probs.sum() <= 0):
        raise ValueError("Direct classifier returned invalid probabilities")
    probs /= probs.sum()
    result = np.zeros_like(base, dtype=float)
    rare = 0.
    max_cls = (cap+1)**2
    for category, probability in zip(labels, probs):
        if int(category) == max_cls:
            rare += float(probability)
        elif 0 <= int(category) < max_cls:
            h, a = divmod(int(category), cap+1)
            result[h, a] = float(probability)
        else:
            raise ValueError("Unexpected label in classifier")
    tail = base.copy()
    tail[:cap+1, :cap+1] = 0.
    if rare:
        total = float(tail.sum())
        if total <= 0:
            raise ValueError("Cannot distribute rare score probability")
        result += rare * tail/total
    # Regularize multiclass estimates with an explicit prematch prior.
    blend = (1. - fitted.prior_weight)*result + fitted.prior_weight*base
    blend = np.maximum(0., blend)
    total = float(blend.sum())
    if not math.isfinite(total) or total <= 0:
        raise ValueError("Invalid predicted exact-score distribution")
    return blend/total
