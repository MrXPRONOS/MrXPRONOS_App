"""Fully chronological ML training and nested walk-forward tuning (improvement #8).

The only inputs are frozen prematch 130-feature vectors and settled football
results from PREVIOUS UTC dates. Inner folds are fixed before searching. The
outer evaluation day is never in the fitting or parameter-selection data.

The objective is proper exact-score log loss (0..10 by 0..10 normalized
Poisson probability matrix); top-1 exact hit rate is a secondary tie-break.
Changing hyperparameters does NOT guarantee better future hit rates.

No file/network/database access and no use of odds, Supabase or Neon.
"""
from __future__ import annotations
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import date
import math
import numpy as np
from scipy.stats import poisson
from sklearn.ensemble import HistGradientBoostingRegressor

MIN_ROWS = 350
MIN_TUNING_ROWS = 900
SEED = 20261020
GOAL_GRID = np.arange(11)
TUNE_VERSION = "historical_walkforward_grid_v1_20261024"

@dataclass(frozen=True)
class MLConfig:
    learning_rate: float = .055
    max_iter: int = 95
    max_leaf_nodes: int = 18
    l2_regularization: float = 5.
    max_rows: int = 65000
    half_life_days: int | None = None
    retrain_days: int = 30

    def __post_init__(self):
        if (not 0 < self.learning_rate <= 1 or self.max_iter < 1
            or self.max_leaf_nodes < 2 or self.l2_regularization < 0
            or self.max_rows < MIN_ROWS
            or self.half_life_days is not None and self.half_life_days < 1
            or self.retrain_days not in (7,14,30,60)):
            raise ValueError("Invalid ML hyperparameter selection")


BASELINE = MLConfig()
# Pre-registered, reproducible candidate space. Never add candidates after
# examining the OUTER holdout's scores; only prior inner folds select a config.
SEARCH = (
    BASELINE,
    MLConfig(.045, 115, 14, 8., 12000, 180, 14),
    MLConfig(.075, 75, 12, 10., 8000, 90, 7),
    MLConfig(.04, 125, 22, 5., 15000, 365, 30),
    MLConfig(.055, 95, 18, 5., 65000, 180, 60),
)

def _validate_rows(rows, *, asof=None, feature_count=None):
    """Reject unsorted, target-day, invalid score or vector observations."""
    last=None
    nfeatures=feature_count
    for record in rows:
        if len(record)!=4 or not isinstance(record[3],date):
            raise ValueError("Training row must have (vector, home, away, UTC_date)")
        vector, home, away, observed_day=record
        if last is not None and observed_day<last:
            raise ValueError("Nonchronological model training rows")
        if asof is not None and observed_day>=asof:
            raise ValueError("Current/future football results in model training")
        array=np.asarray(vector,dtype=float)
        if array.ndim!=1 or not np.isfinite(array).all() or array.size==0:
            raise ValueError("Invalid frozen prematch feature vector")
        if nfeatures is None:nfeatures=array.size
        if array.size!=nfeatures:raise ValueError("ML feature schema inconsistent")
        for goals in (home,away):
            if (isinstance(goals,bool) or not isinstance(goals,(int,np.integer))
                or not 0<=goals<=10):
                raise ValueError("Unverified fulltime score in ML training")
        last=observed_day
    return nfeatures

def recency_weights(rows, asof, half_life_days):
    """Optional exponential age decay, never measured using a target label."""
    if half_life_days is None:return None
    if not isinstance(asof,date):raise ValueError("asof UTC date is required")
    age=np.asarray([(asof-row[3]).days for row in rows],dtype=float)
    if np.any(age<=0):
        raise ValueError("Recency weighting saw current or future outcomes")
    # Avoid underflow and completely discarding older support.
    w=np.maximum(.025,np.exp2(-age/half_life_days))
    return np.asarray(w/w.mean(),dtype=float)

def fit_histgb(rows, *, config=BASELINE, asof, feature_count=None,
               max_fit_rows=None, minimum=MIN_ROWS):
    """Fit independent Poisson HistGB goal rates on earlier settled days only."""
    if not isinstance(asof,date):raise ValueError("Training cutoff UTC date required")
    if max_fit_rows is not None and max_fit_rows<minimum:
        raise ValueError("Invalid inner-CV fit sample cap")
    cap=min(config.max_rows,max_fit_rows) if max_fit_rows is not None else config.max_rows
    data=list(deque(rows,maxlen=cap))
    if len(data)<minimum:return None
    _validate_rows(data,asof=asof,feature_count=feature_count)
    X=np.asarray([r[0] for r in data],dtype=float)
    weights=recency_weights(data,asof,config.half_life_days)
    outputs=[]
    for side in (1,2):
        y=np.asarray([r[side] for r in data],dtype=float)
        model=HistGradientBoostingRegressor(
            loss="poisson", learning_rate=config.learning_rate,
            max_iter=config.max_iter, max_leaf_nodes=config.max_leaf_nodes,
            l2_regularization=config.l2_regularization,
            early_stopping=False, random_state=SEED)
        if weights is None:model.fit(X,y)
        else:model.fit(X,y,sample_weight=weights)
        outputs.append(model)
    return outputs

def _grid(goals_home,goals_away):
    means=np.clip((goals_home,goals_away),.12,5.)
    p=np.outer(poisson.pmf(GOAL_GRID,means[0]),
               poisson.pmf(GOAL_GRID,means[1]))
    p=p/max(float(p.sum()),1e-15)
    return p

def _predict_pair(models,vector):
    X=np.asarray(vector,dtype=float)[None,:]
    return _grid(float(models[0].predict(X)[0]),float(models[1].predict(X)[0]))

def inner_folds(rows, *, asof, folds=2, validation_days=21,
                min_training=MIN_ROWS):
    """Purged-by-day, disjoint *calendar-day* folds, oldest to newest.

    If date gaps exist, the fold spans real dates, not fabricated fixture days.
    Entire same-UTC-day groups stay together. A fold uses only earlier results
    to initialize its first fitted model.
    """
    if folds<1 or validation_days<7:raise ValueError("Invalid inner folds")
    _validate_rows(rows,asof=asof)
    if not rows:return []
    unique=sorted({r[3] for r in rows})
    end=unique[-1]
    from datetime import timedelta
    blocks=[]
    for i in reversed(range(folds)):
        stop=end-timedelta(days=i*validation_days)
        start=stop-timedelta(days=validation_days-1)
        train=[r for r in rows if r[3]<start]
        validation=[r for r in rows if start<=r[3]<=stop]
        if len(train)<min_training or not validation:
            return []
        blocks.append((start,stop,train,validation))
    return blocks

def _score_config(config, blocks, *, feature_count, max_fit_rows=2500):
    losses=[]; hits=0; total=0; refits=0
    boundaries=[]
    for start,stop,train,validation in blocks:
        history=list(train)
        by_date=defaultdict(list)
        for row in validation:by_date[row[3]].append(row)
        last_fit=None
        models=None
        for day in sorted(by_date):
            if models is None or (day-last_fit).days>=config.retrain_days:
                models=fit_histgb(history,config=config,asof=day,
                                  feature_count=feature_count,
                                  max_fit_rows=max_fit_rows)
                if models is None:return None
                last_fit=day
                refits+=1
            # Strictly PREMATCH predictions. Add *all* actual scores after
            # the date, including multiple games on the same UTC date.
            for feature,gh,ga,_ in by_date[day]:
                p=_predict_pair(models,feature)
                losses.append(-math.log(max(float(p[gh,ga]),1e-15)))
                hits+=int(tuple(np.unravel_index(np.argmax(p),p.shape))==(gh,ga))
                total+=1
            history.extend(by_date[day])
        boundaries.append({
            "validation_start":str(start),"validation_end":str(stop),
            "initial_train_n":len(train),"validation_n":len(validation),
        })
    return {
        "loss":float(np.mean(losses)),"hit_rate":hits/total,
        "hits":hits,"n":total,"fits":refits,
        "folds":boundaries,
    }

def select_hyperparameters(rows, *, asof, feature_count, min_rows=MIN_TUNING_ROWS,
                           configs=SEARCH, folds=2, validation_days=21,
                           inner_max_fit_rows=2500):
    """Nested chronological configuration selection; NO target-day access.

    Insufficient prior fixtures -> documented conservative baseline, not a
    training-time error or an invented validation win.
    """
    rows=list(rows)
    _validate_rows(rows,asof=asof,feature_count=feature_count)
    if not configs:raise ValueError("Empty candidate space")
    report={
        "version":TUNE_VERSION,"asof_date":str(asof),"available_past_rows":len(rows),
        "candidate_count":len(configs),"objective":"mean exact-score negative log likelihood",
        "secondary":"exact top-1 hit rate","validation_days":validation_days,
        "fold_count_requested":folds,"only_prior_utc_dates":True,
        "inner_max_fit_rows":inner_max_fit_rows,
    }
    if len(rows)<min_rows:
        report.update({"status":"insufficient_history","selected":asdict(configs[0]),
                       "results":[],"folds_used":0})
        return configs[0],report
    blocks=inner_folds(rows,asof=asof,folds=folds,
                       validation_days=validation_days)
    if not blocks:
        report.update({"status":"insufficient_chronological_folds",
                       "selected":asdict(configs[0]),"results":[],"folds_used":0})
        return configs[0],report
    scores=[]
    for index,cfg in enumerate(configs):
        score=_score_config(cfg,blocks,feature_count=feature_count,
                            max_fit_rows=inner_max_fit_rows)
        if score is None:
            raise RuntimeError("Unexpected insufficient prior data in inner fold")
        scores.append({"candidate_index":index,"params":asdict(cfg),**score})
    # Log-loss wins. Hit rate only breaks near-ties, then fewer fitted trees.
    best=min(scores,key=lambda r:(round(r["loss"],6),-r["hit_rate"],
                                  r["params"]["max_iter"],r["candidate_index"]))
    config=configs[best["candidate_index"]]
    report.update({
        "status":"selected_by_prior_folds","selected":asdict(config),
        "folds_used":len(blocks),"selection_metric":best["loss"],
        "selected_prior_fold_hit_rate":best["hit_rate"],
        "results":scores,
    })
    return config,report
