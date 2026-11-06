"""Two nonpublishing selection circuits: reliability and executable value."""
from __future__ import annotations
from math import fsum, sqrt
from .policy import V3Policy, FAMILY_EDGE, classify_fixture, uncertainty_adjustment, label_candidate


def serialize_candidates(candidates, features, quality, quotes, *, policy=V3Policy(),
                         calibrator=None, calibration_active=False,
                         blocked_keys=frozenset(),market_guards=None):
    """Retain all sixteen candidate markets, regardless of thresholds or prices."""
    out=[]
    for c in candidates:
        samples=calibrator.trained if calibrator and calibrator.active else 0
        haircut=uncertainty_adjustment(features,quality,calibration_samples=samples)
        row={"key":c.key, "family":c.family,"market":c.market,
             "outcome":c.outcome,"line":c.line,"market_code":c.market_code,
             "probability":round(c.probability,7),
             "conservative_probability":round(max(.00001,c.probability-haircut),7),
             "haircut":round(haircut,5),"calibration_active":calibration_active,
             "calibration_samples":samples}
        quote=quotes.get(c.market_code)
        row["quote"]=quote
        row["decision"]=label_candidate(row,quality,quote,policy)
        if c.key in (market_guards or {}):
            row["decision"]["pro_vip_shadow"]=False
            row["decision"]["public_preprice"]=False
            row["decision"]["legacy_guard_reason"]=market_guards[c.key]
        if c.key in blocked_keys:
            row["decision"]["pro_vip_shadow"]=False
            row["decision"]["value_shadow"]=False
            row["decision"]["disabled_reason"]="prospective_calibration_drift"
        out.append(row)
    return out

def joint_event_probability(score_matrix, first, second):
    """Compute P(A and B) from joint goal distribution, never from p(A)*p(B)."""
    def matches(candidate, h, a):
        key=candidate["key"]
        if key=="1":return h>a
        if key=="X":return h==a
        if key=="2":return h<a
        if key=="1X":return h>=a
        if key=="X2":return a>=h
        if key=="12":return h!=a
        if key=="BTTS_YES":return h>0 and a>0
        if key=="BTTS_NO":return h==0 or a==0
        if key.startswith("OVER_"):return h+a>candidate["line"]
        if key.startswith("UNDER_"):return h+a<candidate["line"]
        raise ValueError("Unsupported market key")
    return fsum(p for (h,a),p in score_matrix.items()
                if matches(first,h,a) and matches(second,h,a))

def covariance_correlation(score_matrix, first, second):
    pa=first["probability"]
    pb=second["probability"]
    joint=joint_event_probability(score_matrix,first,second)
    denom=sqrt(pa*(1-pa)*pb*(1-pb))
    return (joint-pa*pb)/denom if denom>0 else 1., joint

def select_candidates(rows, score_matrix, policy=V3Policy()):
    """No requirement to fill two places. Distinct families and capped correlation."""
    reliable=sorted((r for r in rows if r["decision"]["pro_vip_shadow"]),
                    key=lambda r:(-r["conservative_probability"],r["key"]))
    value=sorted((r for r in rows if r["decision"]["value_shadow"]),
                 key=lambda r:(-r["decision"]["ev"]["conservative_ev"],r["key"]))
    selected=[]
    for candidate in reliable:
        if any(candidate["family"]==x["family"] for x in selected):
            continue
        if any(abs(covariance_correlation(score_matrix,candidate,x)[0]) >
               policy.max_joint_correlation for x in selected):
            continue
        selected.append(candidate)
        if len(selected)==policy.max_selections:
            break
    return {"pro_vip_shadow": [r["key"] for r in selected],
            "value_shadow": [r["key"] for r in value],
            "no_publication": True}
