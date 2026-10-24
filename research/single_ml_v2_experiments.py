"""Independent chronological exact-score ML research. Never used for publication."""
from __future__ import annotations
import math
import numpy as np
from scipy.special import softmax
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression

def direct_score_features(x, base_grid, max_goals=5):
    scores = [(h,a) for h in range(max_goals+1) for a in range(max_goals+1)]
    scores.append((-1,-1))  # all rare scorelines outside 0..max_goals
    probs = [float(base_grid[h,a]) for h,a in scores[:-1]]
    probs.append(max(0., 1.-sum(probs)))
    return np.concatenate([np.asarray(x,float), np.array(probs)]), scores

def train_direct_score(rows, *, min_samples=800, max_goals=5):
    """Rows are (prematch_vector, prematch_base_grid, fulltime_h, fulltime_a)."""
    if len(rows) < min_samples:
        return None
    X=[]; y=[]; scores=None
    for features, base, gh, ga in rows:
        xx, scores = direct_score_features(features, base, max_goals)
        X.append(xx)
        y.append(gh*(max_goals+1)+ga if gh<=max_goals and ga<=max_goals
                 else (max_goals+1)**2)
    # One class only -> abstain. Never use future matches.
    if len(set(y)) < 2:
        return None
    model = HistGradientBoostingClassifier(max_iter=90, learning_rate=.045,
                 max_leaf_nodes=12, l2_regularization=10, random_state=20261024)
    model.fit(np.asarray(X), np.asarray(y))
    return model

def direct_grid(model, vector, baseline, *, max_goals=5):
    if model is None: return None
    features,scores=direct_score_features(vector,baseline,max_goals)
    predictions=model.predict_proba(features.reshape(1,-1))[0]
    grid=np.zeros_like(baseline,dtype=float)
    rare=0.
    for cls,p in zip(model.classes_,predictions):
        if int(cls)==(max_goals+1)**2:
            rare += float(p)
        else:
            h,a=divmod(int(cls),max_goals+1)
            grid[h,a]=float(p)
    # Never invent a distribution for rare scores; add rare probability
    # by proportionally distributing over the baseline tail.
    tail=baseline.copy().astype(float)
    tail[:max_goals+1,:max_goals+1]=0.
    if tail.sum()>0: grid+=rare*tail/tail.sum()
    elif rare>0: return None
    return grid / grid.sum()

def train_reliability(rows, *, min_samples=200):
    """Rows: (prematch selection features, was_hit); fit on prior days only."""
    if len(rows)<min_samples or len(set(y for x,y in rows))<2:
        return None
    X=np.array([x for x,y in rows],float)
    y=np.array([y for x,y in rows],int)
    m=LogisticRegression(C=.1,max_iter=600,random_state=20261024)
    m.fit(X,y)
    return m

def selection_features(grid, data_quality):
    vals=np.sort(np.asarray(grid).ravel())
    return np.array([float(vals[-1]),float(vals[-1]-vals[-2]),
                      float(-np.sum(grid*np.log(np.maximum(grid,1.e-15)))),
                      float(data_quality)],float)

def select_forecast(grid, reliability_model, data_quality, threshold):
    if reliability_model is None:
        return {"status":"ABSTAIN","reason":"untrained_reliability"}
    f=selection_features(grid,data_quality)
    p=float(reliability_model.predict_proba(f.reshape(1,-1))[0,1])
    if p<threshold:
        return {"status":"ABSTAIN","calibrated_probability":p}
    h,a=np.unravel_index(np.argmax(grid),grid.shape)
    return {"status":"SELECTED","score":[int(h),int(a)],
            "calibrated_probability":p}

def flat_roi(hit, odds):
    if odds is None: return None
    odds=float(odds)
    if not math.isfinite(odds) or odds<=1: return None
    return float(odds-1 if hit else -1)
