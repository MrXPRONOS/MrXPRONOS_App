"""LightGBM/CatBoost real Poisson candidates for single exact-score ML V2.

Two goal regressors per contender, fit on the same previous-UTC-day frozen
features as HistGradientBoosting, then scored by the same Poisson grid.
Fixed hyperparameters; no silent fallback or retrospective hyperparam search.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import deque
import numpy as np

CANDIDATES = ("lightgbm", "catboost")
CANDIDATE_MODEL_NAMES = {
    "lightgbm": "machine_learning_lightgbm",
    "catboost": "machine_learning_catboost",
}
CANDIDATE_VERSION = "poisson_pair_predeclared_v1_20261024"
MINIMUM = 350
MAX_TRAIN_ROWS = 20000
SEED = 20261024

@dataclass(frozen=True)
class FittedCandidate:
    name: str
    home_model: object
    away_model: object
    feature_count: int
    training_rows: int
    version: str = CANDIDATE_VERSION

def candidate(name, *, seed=SEED):
    if name == "lightgbm":
        from lightgbm import LGBMRegressor
        return LGBMRegressor(
            objective="poisson", n_estimators=120, learning_rate=.045,
            num_leaves=12, min_child_samples=30, reg_lambda=5.,
            n_jobs=2, random_state=seed, verbosity=-1,
            deterministic=True, force_col_wise=True)
    if name == "catboost":
        from catboost import CatBoostRegressor
        return CatBoostRegressor(
            loss_function="Poisson", iterations=120, depth=5,
            learning_rate=.045, l2_leaf_reg=5., random_seed=seed,
            thread_count=2, verbose=False, allow_writing_files=False,
            task_type="CPU")
    raise ValueError("Unknown ML candidate: "+str(name))

def fit_pair(name, records, *, minimum=MINIMUM,
             max_rows=MAX_TRAIN_ROWS, feature_count=None):
    """Fit genuine provider models on chronological PREMATCH feature snapshots."""
    if name not in CANDIDATES: raise ValueError("Unsupported candidate "+str(name))
    if minimum < 2 or max_rows < minimum: raise ValueError("Invalid training caps")
    data=list(deque(records,maxlen=max_rows))
    if len(data)<minimum:return None
    X=np.asarray([row[0] for row in data],dtype=np.float64)
    if X.ndim!=2 or X.shape[1]==0 or not np.isfinite(X).all():
        raise ValueError("Invalid prematch features for ML candidate")
    if feature_count is not None and X.shape[1]!=feature_count:
        raise ValueError("ML feature schema mismatch")
    ys=(np.asarray([r[1] for r in data],dtype=float),
        np.asarray([r[2] for r in data],dtype=float))
    models=[]
    for side,y in enumerate(ys):
        if not np.isfinite(y).all() or (y<0).any() or (y>10).any() or not np.all(y==np.floor(y)):
            raise ValueError("Non-football or invalid goal labels")
        model=candidate(name,seed=SEED+side)
        # Dependency import / native error MUST propagate, not silently fall back.
        model.fit(X,y)
        models.append(model)
    return FittedCandidate(name,models[0],models[1],X.shape[1],len(data))

def predicted_goal_means(fitted,vector):
    if not isinstance(fitted,FittedCandidate):
        raise TypeError("Expected fitted ML candidate")
    arr=np.asarray(vector,dtype=float)
    if arr.ndim!=1 or arr.size!=fitted.feature_count or not np.isfinite(arr).all():
        raise ValueError("Candidate inference feature mismatch")
    X=arr[None,:]
    values=[]
    for model in (fitted.home_model,fitted.away_model):
        if fitted.name=="catboost":
            prediction=model.predict(X,prediction_type="Exponent")
        else:
            prediction=model.predict(X)
        estimate=np.asarray(prediction,dtype=float).reshape(-1)
        if estimate.size!=1 or not np.isfinite(estimate[0]) or estimate[0]<0:
            raise ValueError("Invalid candidate expected goals")
        values.append(float(np.clip(estimate[0],.12,5.)))
    return tuple(values)

def predict_grid(fitted,vector,grid_function):
    if fitted is None:return None
    h,a=predicted_goal_means(fitted,vector)
    return grid_function(h,a)
