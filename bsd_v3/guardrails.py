"""Selection guardrails inherited from V2 are audited explicitly, not silently hidden.

V3 evaluates *all* markets. A legacy BTTS veto blocks the Pro/VIP shadow
circuit, while Value Shadow can still observe the rejected candidate to test
whether the rule is over-conservative. No publication is permitted.
"""
from __future__ import annotations
from .legacy import markets_from_matrix

def family_guards(event,index,baseline,models=None,*,btts_quality_gate=None):
    models=models or {}
    guards={}
    evidence={}
    from bsd_v2_btts_h2h import btts_h2h_decision
    for key in ("BTTS_YES","BTTS_NO"):
        passed,reason,previous=btts_h2h_decision(event,index,key)
        evidence[key]={"v2_last_h2h_passed":passed,"v2_reason":reason,
                       "v2_last_h2h_event_id":previous.get("event_id") if previous else None}
        if not passed:
            guards[key]=reason
    # V3 BTTS YES gate: the market represents TWO scoring events, so both
    # sides must independently be strong enough and the competition must
    # historically support BTTS. This veto was selected before the October test.
    from .btts_quality import evaluate_btts_yes_quality
    passed_v3,v3_btts=evaluate_btts_yes_quality(event,index,btts_quality_gate)
    evidence.setdefault("BTTS_YES",{})["v3_side_league_gate"]=v3_btts
    if not passed_v3 and "BTTS_YES" not in guards:
        guards["BTTS_YES"]=v3_btts["reason"]

    # The specialized V2 BTTS reliability gate is historically more restrictive
    # than a simple Poisson probability. Preserve that prior to any public
    # migration, but allow independent research on candidates it rejects.
    model=models.get("btts")
    if model is not None:
        from bsd_v2_btts import btts_candidates,btts_quality_rejection
        original=markets_from_matrix(baseline)
        p0=next(c.probability for c in original if c.key=="BTTS_YES")
        try:
            changed=btts_candidates(event,index,original,model)
            p1=next(c.probability for c in changed if c.key=="BTTS_YES")
            from .legacy import estimate_goals
            expected,_=estimate_goals(event,index)
            why=btts_quality_rejection(expected,model,p0,p1) if expected else "btts_no_features"
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
            why="btts_specialist_error_"+type(exc).__name__
        for key in ("BTTS_YES","BTTS_NO"):
            evidence[key]["v2_specialist_reason"]=why or "pass"
            if why:
                guards[key]=why
    # V3 Over 2.5 gate: a preferred Over 2.5 requires a competition
    # whose point-in-time Over 2.5 rate is at least 58%.
    from .over25_quality import evaluate_over25_quality
    passed_over25,over25_evidence=evaluate_over25_quality(event,index)
    evidence["OVER_25"]={"v3_over25_gate":over25_evidence}
    if not passed_over25:
        guards["OVER_25"]=over25_evidence["reason"]

    total=models.get("goals")
    if total is not None:
        from bsd_v2_over_under import adjust_candidates
        raw=markets_from_matrix(baseline)
        try:
            tuned=adjust_candidates(event,index,raw,total)
            p0=next(c.probability for c in raw if c.key=="OVER_15")
            p1=next(c.probability for c in tuned if c.key=="OVER_15")
            gap=abs(p1-p0)
            evidence["OVER_15"]={"v2_specialist_gap":round(gap,6),
                                  "v2_specialist_max_gap":.07}
            if gap>.07:
                guards["OVER_15"]="v2_over15_models_disagree"
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
            evidence["OVER_15"]={"v2_specialist_error":type(exc).__name__}
    return guards,evidence
