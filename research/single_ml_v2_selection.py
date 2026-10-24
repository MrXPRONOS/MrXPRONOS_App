"""Research-only exact-score reliability gate (#9): SELECTED or ABSTAIN.

Every reliability training observation comes from a PREQUEL prediction saved
before the match result. Refitting uses only older UTC days. A separate later
calibration slice sets the coverage threshold; no evaluation-day labels enter
fitting, thresholding or selection. Model output is an estimate, NOT a promise.

No bookmaker odds, stakes, database, network or plaintext persistence.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from collections import defaultdict
import math
import numpy as np
from sklearn.linear_model import LogisticRegression

VERSION = "prequential_selective_exact_score_v1_20261024"
SELECTABLE_MODELS = (
    "machine_learning", "machine_learning_direct",
    "machine_learning_lightgbm", "machine_learning_catboost",
)
MIN_OBSERVATIONS = 240
MIN_CALIBRATION = 60
MIN_SELECTED_CALIBRATION = 15
VALID_COVERAGE = (0.15, 0.25, 0.40, 0.60)
MIN_DATA_QUALITY = .5

def prematch_quality(form_samples):
    """0..1 from both clubs' last-5 overall AND venue samples."""
    try:
        x = [
            min(1., float(form_samples[side][field])/need)
            for side in ("home","away")
            for field, need in (("overall_last5",5),("venue_last5",5))
        ]
    except (TypeError,KeyError,ValueError,ZeroDivisionError) as exc:
        raise ValueError("Missing prematch form quality") from exc
    quality=float(np.mean(x))
    if not np.isfinite(quality) or not 0 <= quality <= 1:
        raise ValueError("Invalid prematch quality")
    return quality

def prediction_features(grid, quality):
    """Features immutable at prediction time; never use the true score."""
    p=np.asarray(grid,dtype=float)
    if p.ndim!=2 or p.shape[0]!=p.shape[1] or p.size<4:
        raise ValueError("Invalid score grid")
    if not np.isfinite(p).all() or np.any(p<0) or p.sum()<=0:
        raise ValueError("Invalid score mass")
    if not np.isfinite(quality) or not 0<=quality<=1:
        raise ValueError("Invalid form quality")
    p=p/p.sum()
    vals=np.sort(p.ravel())
    ix=np.unravel_index(np.argmax(p),p.shape)
    entropy=float(-np.sum(p*np.log(np.maximum(p,1.e-15))))/math.log(p.size)
    return np.array([
        float(vals[-1]),float(vals[-1]-vals[-2]),
        entropy,float(quality),float(ix[0])/10.,float(ix[1])/10.,
        float(p[1,1]) if p.shape[0]>1 else 0.,
    ],dtype=float)

@dataclass(frozen=True)
class PastForecast:
    day: date
    vector: np.ndarray
    hit: int

@dataclass(frozen=True)
class ReliabilityFitted:
    estimator: object
    threshold: float
    target_coverage: float
    fit_rows: int
    calibration_rows: int
    calibration_selected: int
    calibration_selected_hit_rate: float
    calibration_all_hit_rate: float
    calibration_coverage: float
    trained_before: date
    schema_size: int

def _validate_records(records, asof):
    if not isinstance(asof,date):raise ValueError("asof date required")
    last=None
    dim=None
    for r in records:
        if not isinstance(r,PastForecast) or not isinstance(r.day,date) or r.day>=asof:
            raise ValueError("Only prior-day PREQUEL forecasts can train gate")
        if last is not None and r.day<last:
            raise ValueError("Historical predictions out of chronological order")
        v=np.asarray(r.vector,dtype=float)
        if v.ndim!=1 or not np.isfinite(v).all() or v.size!=7:
            raise ValueError("Invalid frozen forecast features")
        if r.hit not in (0,1):
            raise ValueError("Unverified hit label")
        if dim is None:dim=v.size
        if dim!=v.size:raise ValueError("Reliability feature schema drift")
        last=r.day

def fit_reliability(records, *, asof, target_coverage=.25,
                    min_observations=MIN_OBSERVATIONS, max_rows=12000):
    """Chronological 65% fitting / later 35% threshold validation.

    A fixed coverage policy is NOT optimized against validation-day accuracy.
    Quantile is computed from held-out historical scores before future games.
    """
    if target_coverage not in VALID_COVERAGE:
        raise ValueError("Coverage must be prespecified: "+str(VALID_COVERAGE))
    if min_observations<40 or max_rows<min_observations:
        raise ValueError("Invalid historical gates")
    observations=list(records)[-max_rows:]
    _validate_records(observations,asof)
    if len(observations)<min_observations:
        return None
    n=int(len(observations)*.65)
    # Do not split any same-day results across training and threshold cohort.
    cutoff=observations[n].day
    fit_rows=[r for r in observations if r.day<cutoff]
    val_rows=[r for r in observations if r.day>=cutoff]
    if len(fit_rows)<120 or len(val_rows)<MIN_CALIBRATION:
        return None
    outcomes={r.hit for r in fit_rows}
    if len(outcomes)<2:
        return None
    X=np.asarray([r.vector for r in fit_rows])
    y=np.asarray([r.hit for r in fit_rows],dtype=int)
    estimator=LogisticRegression(max_iter=800,C=.3,random_state=20261024)
    estimator.fit(X,y)
    probs=estimator.predict_proba(np.asarray([r.vector for r in val_rows]))[:,1]
    # Approximate target selection share from held-out scores; threshold
    # always computed on PRIOR forecasts only, no outer-match outcomes.
    q=float(np.quantile(probs,1.-target_coverage))
    selected_mask=probs>=q
    selected=int(selected_mask.sum())
    if selected<MIN_SELECTED_CALIBRATION:
        return None
    yval=np.asarray([r.hit for r in val_rows])
    return ReliabilityFitted(
        estimator=estimator,threshold=q,target_coverage=target_coverage,
        fit_rows=len(fit_rows),calibration_rows=len(val_rows),
        calibration_selected=selected,
        calibration_selected_hit_rate=float(yval[selected_mask].mean()),
        calibration_all_hit_rate=float(yval.mean()),
        calibration_coverage=selected/len(val_rows),
        trained_before=asof,schema_size=X.shape[1],
    )

def decide(fitted, grid, *, form_samples):
    """Return only genuine SELECTED or ABSTAIN decision, no invented hits."""
    quality=prematch_quality(form_samples)
    vector=prediction_features(grid,quality)
    if fitted is None:
        return {"status":"ABSTAIN","reason":"insufficient_prior_forecast_reliability",
                "estimated_hit_probability":None,"threshold":None,
                "quality":quality}
    if vector.size!=fitted.schema_size:
        raise ValueError("Selection schema mismatch")
    p=float(fitted.estimator.predict_proba(vector[None,:])[0,1])
    if not np.isfinite(p):
        raise ValueError("Nonfinite reliability estimate")
    reasons=[]
    if quality<MIN_DATA_QUALITY:reasons.append("insufficient_team_form")
    if p<fitted.threshold:reasons.append("below_past_calibrated_selection_threshold")
    if reasons:
        return {"status":"ABSTAIN","reason":";".join(reasons),
                "estimated_hit_probability":p,"threshold":fitted.threshold,
                "quality":quality}
    h,a=np.unravel_index(np.argmax(np.asarray(grid)),np.asarray(grid).shape)
    return {"status":"SELECTED","reason":None,
            "score":[int(h),int(a)],"estimated_hit_probability":p,
            "threshold":fitted.threshold,"quality":quality}

def report_selections(records, *, total_matches, policy_coverage):
    """Conditional hit rate AND coverage. Denominator counts all matches."""
    result={}
    for model,rows in records.items():
        count=len(rows)
        selected=[x for x in rows if x["status"]=="SELECTED"]
        hits=sum(int(x["hit"]) for x in selected)
        predicted=[x for x in rows if x.get("underlying_available",True)]
        full_hits=sum(int(x["hit"]) for x in predicted)
        reasons={}
        for r in rows:
            if r["status"]=="ABSTAIN":
                reason=r.get("reason") or "unknown"
                reasons[reason]=reasons.get(reason,0)+1
        result[model]={
            "eligible_model_forecasts":len(predicted),
            "all_evaluation_matches":int(total_matches),
            "selected":len(selected),"abstained":count-len(selected),
            "unavailable_underlying_model":max(0,total_matches-len(predicted)),
            "coverage_of_all_matches_pct":round(100*len(selected)/total_matches,3) if total_matches else None,
            "coverage_of_model_forecasts_pct":round(100*len(selected)/len(predicted),3) if predicted else None,
            "selected_exact_hits":hits,
            "selected_hit_rate_pct":round(100*hits/len(selected),3) if selected else None,
            "unfiltered_hit_rate_pct":round(100*full_hits/len(predicted),3) if predicted else None,
            "policy_target_coverage_pct":round(100*policy_coverage,1),
            "abstention_reasons":reasons,
            "status":"EVALUATED" if selected else "ABSTAIN_ALL",
            "roi_pct":None,
        }
    return result
