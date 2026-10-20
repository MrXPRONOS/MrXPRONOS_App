"""Phase 3 — coherent Under 2.5 + BTTS fusion, score ranking and abstention.
Research-only; no market odds, no automatic publishing.
"""
from math import isfinite
from exact_scores import top_scores
from exact_scores_under25 import probability_under25

def btts_probability(matrix):
    return sum(p for (h,a),p in matrix.items() if h>0 and a>0)

def coherent_fusion(matrix,under25,btts=None,iterations=32):
    """Iterative proportional fitting of joint Under 2.5 and BTTS marginals.

    No independent multiplication of correlated model confidences.
    Strictly positive matrix support and numerical mass normalization.
    """
    if not all(isfinite(v) and v>=0 for v in matrix.values()) or sum(matrix.values())<=0:
        raise ValueError("Invalid exact-score probability matrix")
    targets=[(lambda h,a:h+a<=2,max(.01,min(.99,float(under25))))]
    if btts is not None:
        targets.append((lambda h,a:h>0 and a>0,max(.01,min(.99,float(btts)))))
    out={k:max(1e-18,v) for k,v in matrix.items()}
    total=sum(out.values());out={k:v/total for k,v in out.items()}
    for _ in range(iterations):
        for condition,target in targets:
            old=sum(p for (h,a),p in out.items() if condition(h,a))
            if not 0<old<1:raise ValueError("Impossible conditioning event")
            low=target/old;high=(1-target)/(1-old)
            out={(h,a):p*(low if condition(h,a) else high) for (h,a),p in out.items()}
    total=sum(out.values())
    return {k:v/total for k,v in out.items()}

def decision(matrix,*,under_v1,under_v2,h2h_prioritized,
             min_under=.62,max_disagreement=.14,min_top3_mass=.32):
    """Conservative screening; selection thresholds are hypotheses, not trained claims."""
    if not 0<=under_v1<=1 or not 0<=under_v2<=1:
        raise ValueError("Invalid model probability")
    distribution=coherent_fusion(matrix,under_v2)
    best=top_scores(distribution)
    concentration=sum(p for _,p in best)
    reasons=[]
    if not h2h_prioritized:reasons.append("h2h_not_stable")
    if under_v2<min_under:reasons.append("under25_below_threshold")
    if abs(under_v1-under_v2)>max_disagreement:reasons.append("model_disagreement")
    if concentration<min_top3_mass:reasons.append("top3_not_concentrated")
    return {"selected":not reasons,"reasons":reasons,
            "under25_probability":under_v2,
            "under25_disagreement":abs(under_v1-under_v2),
            "top3_mass":concentration,
            "top3":[{"score":list(score),"p":p} for score,p in best],
            "matrix":distribution}
