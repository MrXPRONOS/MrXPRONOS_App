"""Opt-in research ML V3: three independent upgrades, V2 remains untouched.

All tunable constants are frozen in source before the V3 holdout:
- weighted HistGB on prior-day data, conservative uncertainty shrinkage;
- past-only empirical 1:1 cell calibration with fixed bounded adjustment;
- disagreement-aware, past-OOS-calibrated HistGB V3 + independent DC pool;
- direct 37-class HistGB with longer window, modest class reweighting,
  plus past-OOS-calibrated Poisson prior.
No odds, network, storage, or final-score features at prediction time.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
import numpy as np

from single_ml_v2_tune import MLConfig, fit_histgb
from single_ml_v2_direct import train_direct_score, direct_grid
from single_ml_v2_hybrid import DEFAULT_DC_WEIGHT, blend, calibrate, PastHybridForecast
from single_ml_v2_selection import prematch_quality

VERSION="ml_v3_frozen_experimental_20261029"
HIST_NAME="machine_learning_v3_histgb"
HYBRID_NAME="machine_learning_v3_hybrid"
DIRECT_NAME="machine_learning_v3_direct"
V3_MODELS=(HIST_NAME,HYBRID_NAME,DIRECT_NAME)

# Never tuned on the prospective comparison; fixed upfront research candidates.
HIST_CONFIG=MLConfig(learning_rate=.055,max_iter=95,max_leaf_nodes=18,
                     l2_regularization=5.,max_rows=65000,
                     half_life_days=180,retrain_days=30)
DIRECT_CONFIG=dict(max_rows=65000,max_iter=90,max_leaf_nodes=16,
                   learning_rate=.045,l2_regularization=15.,
                   prior_weight=0.0,class_weight_power=.25)
DIRECT_PRIOR_DEFAULT=.20


def fit_hist_v3(dated_training, *, asof, feature_count):
    """Dated training enforced by fit_histgb; no present-day label."""
    return fit_histgb(dated_training,config=HIST_CONFIG,
                      asof=asof,feature_count=feature_count)


def fit_direct_v3(prior_direct_training):
    """Same frozen previous-day input format as V2; separately fitted model."""
    return train_direct_score(prior_direct_training,**DIRECT_CONFIG)


@dataclass(frozen=True)
class PastEleven:
    day:date
    match_id:str
    probability:float
    actual:int


def eleven_multiplier(previous, *, asof, min_matches=180, min_days=14,
                      max_rows=3000, smooth=50.):
    """Compare previously forecast P(1:1) against previously settled 1:1.

    Raw OOS HistGB V3 probabilities must be frozen BEFORE their outcomes
    are appended; current UTC date cannot be included. Fallback to factor=1.
    """
    if not isinstance(asof,date):
        raise ValueError("Historical 1:1 calibration requires cutoff")
    observations=list(previous)
    last=None;ids=set()
    for row in observations:
        if (not isinstance(row,PastEleven) or not isinstance(row.day,date)
            or row.day>=asof or not row.match_id or row.actual not in (0,1)
            or not np.isfinite(row.probability)
            or not 0<row.probability<1):
            raise ValueError("Invalid or current-day 1:1 calibration history")
        if last is not None and row.day<last:
            raise ValueError("Unsorted 1:1 predictions")
        if (row.day,row.match_id) in ids:
            raise ValueError("Duplicate 1:1 calibration fixture")
        ids.add((row.day,row.match_id));last=row.day
    eligible=observations[-max_rows:]
    if len(eligible)<min_matches or len({r.day for r in eligible})<min_days:
        return 1.
    expected=sum(r.probability for r in eligible)
    observed=sum(r.actual for r in eligible)
    # Smoothed reliability ratio (50 prior pseudo-matches) protects rare scores.
    baseline=expected/len(eligible)
    adjusted=(observed+smooth*baseline)/(expected+smooth*baseline)
    return float(np.clip(adjusted,.75,1.25))


def calibrate_eleven_cell(grid, factor):
    """Bounded, exactly normalized probability calibration, not hard 1-1 ban."""
    p=np.asarray(grid,dtype=float)
    if p.shape!=(11,11) or not np.isfinite(p).all() or np.any(p<0) or p.sum()<=0:
        raise ValueError("Invalid exact-score grid")
    if not np.isfinite(factor) or not .75<=factor<=1.25:
        raise ValueError("Unvalidated 1:1 factor")
    out=p/p.sum()
    out[1,1]*=factor
    out/=out.sum()
    return out


def hist_v3_grid(models, vector, baseline, *, form_samples, p11_factor=1.):
    """Conservative prior mixing when recent venue/team form lacks coverage."""
    if models is None:return None
    f=np.asarray(vector,dtype=float)
    if f.ndim!=1 or not np.isfinite(f).all():
        raise ValueError("Hist V3 requires frozen prematch vector")
    b=np.asarray(baseline,dtype=float)
    if b.shape!=(11,11) or not np.isfinite(b).all() or (b<0).any() or b.sum()<=0:
        raise ValueError("Hist V3 baseline grid invalid")
    from scipy.stats import poisson
    goals=[float(np.clip(model.predict(f[None,:])[0],.12,5.))
           for model in models]
    raw=np.outer(poisson.pmf(np.arange(11),goals[0]),
                 poisson.pmf(np.arange(11),goals[1]))
    raw/=raw.sum()
    # When full recent form exists, use raw ML; otherwise regularize towards
    # a strictly prematch baseline (at most 20% weight).
    quality=prematch_quality(form_samples)
    prior_weight=min(.20, .40*(1.-quality))
    merged=(1.-prior_weight)*raw+prior_weight*(b/b.sum())
    return calibrate_eleven_cell(merged,p11_factor)


def hybrid_v3_weight(prior_forecasts, *, asof, previous=DEFAULT_DC_WEIGHT):
    """Use prior *V3* forecasts, not past V2 forecasts, to set DC weight."""
    setting=calibrate(prior_forecasts,asof=asof,base_weight=DEFAULT_DC_WEIGHT)
    if not setting.calibrated:return DEFAULT_DC_WEIGHT,setting
    if not np.isfinite(previous) or not 0<=previous<=1:
        raise ValueError("Invalid previous hybrid weight")
    # Avoid large jumps between monthly refits on small samples.
    weight=float(np.clip(setting.dc_weight,previous-.12,previous+.12))
    return float(np.clip(weight,.10,.65)),setting


def hybrid_v3_grid(hist_grid, dc_grid, *, dc_weight):
    """Reduce influence of DC on highly contradictory probability matrices."""
    p=np.asarray(hist_grid,dtype=float)
    q=np.asarray(dc_grid,dtype=float)
    if p.shape!=(11,11) or q.shape!=(11,11):
        raise ValueError("Hybrid V3 requires full 11x11 forecasts")
    if not np.isfinite(dc_weight) or not 0<=dc_weight<=1:
        raise ValueError("Invalid DC weight")
    if not (np.isfinite(p).all() and np.isfinite(q).all()
            and (p>=0).all() and (q>=0).all() and p.sum()>0 and q.sum()>0):
        raise ValueError("Invalid hybrid probability mass")
    a=p/p.sum();b=q/q.sum()
    # Total variation disagreement (0..1), available pre-match.
    divergence=.5*float(np.abs(a-b).sum())
    effective=dc_weight*(1.-.5*divergence)
    return blend(a,b,effective)


def direct_v3_grid(fitted, vector, baseline, *, prior_weight):
    """Reweight unseen classes with a past-only fitted prior mix."""
    if fitted is None:return None
    if not np.isfinite(prior_weight) or not 0<=prior_weight<=.8:
        raise ValueError("Invalid prematch prior weight")
    raw=direct_grid(fitted,vector,baseline)
    return blend(raw,baseline,prior_weight)


def direct_v3_prior(previous, *, asof):
    """Optimize baseline Poisson prior exclusively on previous-day OOS grids."""
    setting=calibrate(previous,asof=asof,base_weight=DIRECT_PRIOR_DEFAULT)
    if not setting.calibrated:
        return DIRECT_PRIOR_DEFAULT,setting
    return float(np.clip(setting.dc_weight,.05,.65)),setting


def freeze_blend(day,key,unblended,reference,hg,ag):
    """Used for both V3 hybrid and V3 direct Poisson-prior fitting."""
    return PastHybridForecast(day,key,unblended,reference,hg,ag)
