"""Validation-gated ensemble of LightGBM, bivariate Poisson and ZIP.

The fourth system is itself the ensemble learner: nonnegative weights on the
existing BTTS specialist plus three independent challengers, fitted on
Sep-Dec 2024 Brier loss, and confirmed on Sep-Dec 2025. Strictly no
2026 result is read for selecting weights. With no validated improvement,
new weights are zero; shadow predictions remain auditable.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from bsd_v2_core import fixture_datetime, estimate_goals, score_matrix, markets_from_matrix, outcome_scores
from bsd_v2_btts_bivariate import fit_bivariate
from bsd_v2_btts_zip import fit_zip
from bsd_v2_btts_lgbm import fit_lightgbm


def _clip(p):
    return max(.01,min(.99,float(p)))


def _brier(rows,weights):
    n=len(rows)
    if not n:return float("inf")
    return sum((sum(w*p for w,p in zip(weights,record[:4]))-record[4])**2 for record in rows)/n


@dataclass(frozen=True)
class EnsembleBTTS:
    lightgbm: object
    bivariate: object
    zip_model: object
    weights: tuple
    train_records: int
    validation_records: int
    independent_records: int

    def candidate_probs(self,event,index,expected=None):
        if expected is None:
            expected,_=estimate_goals(event,index)
            if expected is None:return None
        ml=self.lightgbm.predict(event,index,expected) if self.lightgbm else None
        bi=self.bivariate.predict(expected) if self.bivariate else None
        zp=self.zip_model.predict(event,index,expected) if self.zip_model else None
        return {"lightgbm":ml,"bivariate":bi,
                "zero_inflated":zp["btts_yes"] if zp else None}

    def predict(self,event,index,base_probability,expected=None):
        if self.weights[0]>=1.:return base_probability
        p=self.candidate_probs(event,index,expected)
        if p is None or any(p[k] is None and self.weights[j]>0 for j,k in
                            enumerate(("lightgbm","bivariate","zero_inflated"),1)):
            return base_probability
        return _clip(self.weights[0]*base_probability+
                     self.weights[1]*(p["lightgbm"] or 0.)+
                     self.weights[2]*(p["bivariate"] or 0.)+
                     self.weights[3]*(p["zero_inflated"] or 0.))

    def to_dict(self):
        return {"version":"btts-four-model-ensemble-1",
                "weights":dict(zip(("existing_btts","lightgbm","bivariate_poisson","zero_inflated_poisson"),self.weights)),
                "training_records":self.train_records,
                "selection_records":self.validation_records,
                "confirmation_records":self.independent_records,
                "models":{
                  "lightgbm":self.lightgbm.to_dict() if self.lightgbm else None,
                  "bivariate":self.bivariate.to_dict() if self.bivariate else None,
                  "zero_inflated":self.zip_model.to_dict() if self.zip_model else None}}


def fit_ensemble(index,training_fixtures,validation_fixtures,holdout_fixtures,
                 base_model,*,rho=0.,max_train=3200,max_validation=900,max_holdout=1000):
    """Fit all three challengers; the fourth system learns their safe mixture.

    Training: 2024 Jan-Aug. Choice: 2024 Sep-Dec.
    Independent check: 2025 Sep-Dec. Test: 2026, never seen here.
    """
    for events,year,lo,hi in (
        (training_fixtures,2024,1,8),(validation_fixtures,2024,9,12),
        (holdout_fixtures,2025,9,12)):
        for e in events:
            dt=fixture_datetime(e)
            if dt.year!=year or not lo<=dt.month<=hi:
                raise ValueError("Ensemble train/validation split violation")
    def sample(events,n):
        rows=sorted(events,key=lambda e:(e["event_date"],str(e["id"])))
        if len(rows)>n:
            rows=[rows[int(i*len(rows)/n)] for i in range(n)]
        return rows
    training=sample(training_fixtures,max_train)
    validation=sample(validation_fixtures,max_validation)
    holdout=sample(holdout_fixtures,max_holdout)

    lightgbm=fit_lightgbm(index,training)
    bivariate=fit_bivariate(index,training)
    zip_model=fit_zip(index,training)
    shell=EnsembleBTTS(lightgbm,bivariate,zip_model,(1.,0.,0.,0.),
                       len(training),0,0)

    def observations(fixtures):
        rows=[]
        for event in fixtures:
            expected,_=estimate_goals(event,index)
            scores=outcome_scores(event)
            if scores is None or expected is None:continue
            base=markets_from_matrix(score_matrix(expected["home"],expected["away"],rho))
            baseline=next(c.probability for c in base if c.key=="BTTS_YES")
            probability=base_model.predict(event,index,baseline)
            preds=shell.candidate_probs(event,index,expected)
            if preds is None or any(x is None for x in preds.values()):
                continue
            rows.append((probability,preds["lightgbm"],preds["bivariate"],
                         preds["zero_inflated"],int(scores[0]>0 and scores[1]>0)))
        return rows

    selection=observations(validation)
    independent=observations(holdout)
    prior=(1.,0.,0.,0.)
    diagnostic={
        "lightgbm_training":lightgbm.training_matches if lightgbm else 0,
        "bivariate_training":bivariate.trained_fixtures if bivariate else 0,
        "zip_training":zip_model.trained_fixtures if zip_model else 0,
        "selection_count":len(selection),"confirmation_count":len(independent),
        "activated":False,"reason":"insufficient_models_or_observations",
        "baseline_selection_brier":None,"baseline_confirmation_brier":None,
        "single_model_selection_brier":{},"single_model_confirmation_brier":{},
    }
    if selection and independent:
        names=("existing_btts","lightgbm","bivariate","zip")
        for i,name in enumerate(names):
            only=tuple(float(j==i) for j in range(4))
            diagnostic["single_model_selection_brier"][name]=round(_brier(selection,only),6)
            diagnostic["single_model_confirmation_brier"][name]=round(_brier(independent,only),6)
        diagnostic["baseline_selection_brier"]=round(_brier(selection,prior),6)
        diagnostic["baseline_confirmation_brier"]=round(_brier(independent,prior),6)

    if lightgbm and bivariate and zip_model and len(selection)>=200 and len(independent)>=250:
        # The baseline retains at least 40% weight; 3 challenger weights are
        # nonnegative multiples of 10%. No negative leverage or hidden odds.
        grid=(0.,.1,.2,.3,.4,.5,.6)
        choices=[(1-a-b-c,a,b,c) for a,b,c in product(grid,repeat=3)
                 if a+b+c<=.60+1e-9]
        best=min(choices,key=lambda w:_brier(selection,w))
        old_select,proposed_select=_brier(selection,prior),_brier(selection,best)
        old_confirm,proposed_confirm=_brier(independent,prior),_brier(independent,best)
        diagnostic.update({
            "proposed_weights":list(best),
            "proposed_selection_brier":round(proposed_select,6),
            "proposed_confirmation_brier":round(proposed_confirm,6),
        })
        if (best!=prior and proposed_select<=old_select-.0003 and
                proposed_confirm<=old_confirm-.0002):
            prior=best
            diagnostic["activated"]=True
            diagnostic["reason"]="independent_validation_brier_improved"
        else:
            diagnostic["reason"]="no_independent_brier_gain"
    result=EnsembleBTTS(lightgbm,bivariate,zip_model,prior,len(training),len(selection),len(independent))
    diagnostic["selected_weights"]=result.to_dict()["weights"]
    return result,diagnostic
