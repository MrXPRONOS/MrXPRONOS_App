#!/usr/bin/env python3
"""ONE 65,000-row real estimator-fit capacity check with SYNTHETIC data only.

The exact V3 HistGB and V3 Direct configurations are used, no reduced trees,
fitting on earlier synthetic dates with a fixed 160-dim-style FEATURE_NAMES
schema. Measures wall time, CPU and process peak RSS on GitHub runner.
NO historical backtest and NO private source dataset reads.
"""
from __future__ import annotations
import argparse
import json
import os
import resource
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from ml_v2_topk import _safe_output
from single_ml_v2 import FEATURE_NAMES, poisson_grid
from single_ml_v3 import HIST_CONFIG, DIRECT_CONFIG, fit_hist_v3, fit_direct_v3, direct_v3_grid

TARGET_ROWS=65000
SEED=20261029


def measure():
    n=TARGET_ROWS
    rng=np.random.default_rng(SEED)
    start=date(2024,1,1)
    n_features=len(FEATURE_NAMES)
    if n_features<100:
        raise ValueError("Unexpected prematch feature schema, capacity check invalid")
    # Different synthetic match features, outcomes, and Poisson baselines;
    # all training fixture dates are prior to the evaluation cutoff.
    X=rng.normal(0.,.7,size=(n,n_features)).astype(np.float64)
    X[:,0]=rng.uniform(.7,2.6,size=n)
    X[:,1]=rng.uniform(.7,2.2,size=n)
    X[:,2]=rng.integers(0,15,size=n)
    X[:,3]=rng.integers(0,15,size=n)
    base=[poisson_grid(0.9+i*.12,0.7+(i%7)*.12) for i in range(21)]
    h=rng.poisson(1.35,size=n).clip(0,10)
    a=rng.poisson(1.1,size=n).clip(0,10)
    # Distinct dates with monotonic chronology, fitted 1 day after last result.
    days=[start+timedelta(days=int(i//245)) for i in range(n)]
    cutoff=days[-1]+timedelta(days=1)
    hist=[(X[i],int(h[i]),int(a[i]),days[i]) for i in range(n)]
    direct=[(X[i],base[i%len(base)],int(h[i]),int(a[i])) for i in range(n)]
    summary={
        "synthetic_only":True,"history_downloaded":False,"target_rows":TARGET_ROWS,
        "n_features":n_features,
        "hist_config":{k:getattr(HIST_CONFIG,k) for k in (
            "learning_rate","max_iter","max_leaf_nodes","l2_regularization",
            "max_rows","half_life_days","retrain_days")},
        "direct_config":DIRECT_CONFIG,
        "cutoff":str(cutoff),
    }
    t=time.perf_counter()
    hm=fit_hist_v3(hist,asof=cutoff,feature_count=n_features)
    if hm is None or len(hm)!=2:
        raise RuntimeError("V3 HistGB failed 65,000-row training")
    summary["histgb_fit_elapsed_seconds"]=round(time.perf_counter()-t,2)
    t=time.perf_counter()
    dm=fit_direct_v3(direct)
    if dm is None or dm.samples!=n or dm.prior_weight!=0.:
        raise RuntimeError("Direct V3 did not train on all 65,000 rows")
    summary["direct_fit_elapsed_seconds"]=round(time.perf_counter()-t,2)
    if len(dm.label_counts)<15:
        raise RuntimeError("Synthetic test covered too few distinct score classes")
    summary["direct_trained_classes"]=len(dm.label_counts)
    if len(hm)!=2 or any(not np.isfinite(m.predict(X[:1])).all() for m in hm):
        raise RuntimeError("Invalid 65,000-row HistGB predictions")
    grid=direct_v3_grid(dm,X[0],base[0],prior_weight=.2)
    if grid.shape!=(11,11) or not np.isfinite(grid).all() or (grid<0).any() or abs(grid.sum()-1)>1e-8:
        raise RuntimeError("Invalid 65,000-row Direct V3 score grid")
    summary["direct_output_shape"]=list(grid.shape)
    summary["peak_process_rss_mib"]=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024.,2)
    summary["runtime_total_seconds"]=round(summary["histgb_fit_elapsed_seconds"]+summary["direct_fit_elapsed_seconds"],2)
    summary["result"]="PASS"
    if summary["peak_process_rss_mib"]>5700:
        raise RuntimeError("GitHub runner resource safety limit exceeded: 5.7 GiB")
    return summary


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    summary=measure()
    _safe_output(args.out).write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf8")
    print("V3_65000_SYNTHETIC_CAPACITY_AUDIT",json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
