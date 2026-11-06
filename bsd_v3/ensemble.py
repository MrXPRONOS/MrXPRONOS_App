"""2024-trained specialist challengers, 2025 train/gate, coherent score projection.

All three existing V2 model families are reused without modifying their source.
No challenger is activated solely because it produces a more attractive pick.
"""
from __future__ import annotations
from collections import defaultdict
from math import fsum
from .legacy import fixture_datetime,estimate_goals,outcome_scores,score_matrix,markets_from_matrix,realized
from .probabilities import normalized,tilt_result,tilt_event,prove_coherence

FAMILIES=("result","goals","btts")
WEIGHTS=(0.,.20,.40,.60)

def fit_models(index,rho):
    from bsd_v2_double_chance import fit_model as fit_result
    from bsd_v2_over_under import fit_total_model
    from bsd_v2_btts import fit_btts_model
    models,diagnostics={},{}
    for family,fit in (("result",fit_result),("goals",fit_total_model),
                       ("btts",fit_btts_model)):
        model,diag=fit(index,rho=rho)
        models[family]=model
        diagnostics[family]=diag
    return models,diagnostics

def projected_matrix(event,index,matrix,models,weights):
    """Challenger outputs become coherent joint probabilities, not edited margins."""
    matrix=normalized(matrix)
    if weights.get("result",0)>0 and models.get("result") is not None:
        from bsd_v2_double_chance import adjust_candidates
        old=markets_from_matrix(matrix)
        changed=adjust_candidates(event,index,old,models["result"])
        target={c.key:c.probability for c in changed}
        original={c.key:c.probability for c in old}
        weight=weights["result"]
        desired=[original[key]+weight*(target[key]-original[key]) for key in ("1","X","2")]
        matrix=tilt_result(matrix,desired)
    if weights.get("goals",0)>0 and models.get("goals") is not None:
        from bsd_v2_over_under import adjust_candidates
        old=markets_from_matrix(matrix)
        changed=adjust_candidates(event,index,old,models["goals"])
        target={c.key:c.probability for c in changed}
        original={c.key:c.probability for c in old}
        weight=weights["goals"]
        # A single joint PMF is retained throughout: Under = 1 - Over.
        for _ in range(2):
            for line in (1.5,2.5,3.5,4.5):
                key="OVER_"+str(line).replace(".","")
                desired=original[key]+weight*(target[key]-original[key])
                if 0 < desired < 1:
                    matrix=tilt_event(matrix,lambda score,limit=line:sum(score)>limit,
                                      desired,strength=.30)
    if weights.get("btts",0)>0 and models.get("btts") is not None:
        from bsd_v2_btts import btts_candidates
        old=markets_from_matrix(matrix)
        changed=btts_candidates(event,index,old,models["btts"])
        target={c.key:c.probability for c in changed}
        original={c.key:c.probability for c in old}
        weight=weights["btts"]
        desired=original["BTTS_YES"]+weight*(target["BTTS_YES"]-original["BTTS_YES"])
        matrix=tilt_event(matrix,lambda score:score[0]>0 and score[1]>0,desired,
                          strength=.65)
    prove_coherence(markets_from_matrix(matrix))
    return matrix

def fit_gate(index,rho,models,*,max_train=500,max_validation=300,
             min_train=80,min_validation=50,min_improvement=.0001):
    records=[e for _,e in index.global_games if fixture_datetime(e).year==2025]
    records.sort(key=lambda x:(fixture_datetime(x),str(x.get("id"))))
    train=[e for e in records if fixture_datetime(e).month<=8][:max_train]
    val=[e for e in records if fixture_datetime(e).month>=9][:max_validation]
    active={}
    diagnostics={}
    for family in FAMILIES:
        results={"train":{},"validation":{}}
        for split,events in (("train",train),("validation",val)):
            totals={w:0. for w in WEIGHTS}
            count=0
            failures=0
            for event in events:
                estimated,_=estimate_goals(event,index)
                if estimated is None:continue
                actual=outcome_scores(event)
                base=score_matrix(estimated["home"],estimated["away"],rho)
                try:
                    for weight in WEIGHTS:
                        prediction=projected_matrix(event,index,base,models,{family:weight})
                        relevant=[c for c in markets_from_matrix(prediction)
                                  if c.family==family]
                        totals[weight]+=fsum((c.probability-realized(c,*actual))**2
                                             for c in relevant)/len(relevant)
                    count+=1
                except (ValueError,TypeError,KeyError,ArithmeticError):
                    failures+=1
            results[split]={"n":count,"failures":failures,
                            "brier":{w:totals[w]/count if count else None for w in WEIGHTS}}
        tr=results["train"];va=results["validation"]
        chosen=0.
        accepted=False
        if tr["n"]>=min_train and va["n"]>=min_validation:
            chosen=min(WEIGHTS,key=lambda w:tr["brier"][w])
            if (chosen and tr["brier"][chosen]+min_improvement<tr["brier"][0.]
                    and va["brier"][chosen]+min_improvement<va["brier"][0.]):
                accepted=True
        active[family]=chosen if accepted else 0.
        diagnostics[family]={"train_n":tr["n"],"validation_n":va["n"],
                             "failed_train":tr["failures"],"failed_validation":va["failures"],
                             "chosen_weight":chosen,"active_weight":active[family],
                             "validated":accepted,
                             "base_validation_brier":va["brier"][0.],
                             "challenger_validation_brier":va["brier"].get(chosen),
                             "train_period":"2025-01 to 2025-08",
                             "validation_period":"2025-09 to 2025-12"}
    return active,diagnostics
