"""Production-grade BSD V2 additional markets.

Only six *binary full-time* markets can be chosen for site publication:
team goals +/- and Asian handicap +1.5. They require separate chronological
2025 calibration AND holdout validation. DNB requires void-aware return
calibration, and half-time needs genuine period scores. Both remain visible
in diagnostics but are never advertised as finished binary predictions.

No 2026 outcomes are used for fitting or selecting publication thresholds.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import replace
from math import isfinite

from bsd_markets import Candidate
from bsd_v2_core import estimate_goals, fixture_datetime, score_matrix, outcome_scores
from bsd_v2_policies import V2Calibration
from bsd_v2_market_expansion import candidates as extra_options, outcome, first_half_scores, half_time_share, ALL_KEYS

PUBLISHABLE_KEYS=frozenset({
    "HOME_OVER_05","AWAY_OVER_05","HOME_UNDER_15","AWAY_UNDER_15",
    "AH_HOME_PLUS_15","AH_AWAY_PLUS_15",
})
RESEARCH_ONLY_KEYS=frozenset(ALL_KEYS)-PUBLISHABLE_KEYS
MIN_VALIDATION_OBSERVATIONS=100
MIN_HIGH_CONF_VALIDATION_OBSERVATIONS=35
MAX_HOLDOUT_OPTIMISM=.06
MARKET_META={
    "HOME_OVER_05":("team_goals","home_over_05","over","Équipe à domicile marque au moins 1 but",0.5),
    "AWAY_OVER_05":("team_goals","away_over_05","over","Équipe à l'extérieur marque au moins 1 but",0.5),
    "HOME_UNDER_15":("team_goals","home_under_15","under","Équipe à domicile : moins de 1,5 but",1.5),
    "AWAY_UNDER_15":("team_goals","away_under_15","under","Équipe à l'extérieur : moins de 1,5 but",1.5),
    "AH_HOME_PLUS_15":("asian_handicap","ah_home_plus_15","home","Handicap domicile +1,5",1.5),
    "AH_AWAY_PLUS_15":("asian_handicap","ah_away_plus_15","away","Handicap extérieur +1,5",1.5),
}

def to_candidate(option):
    metadata=MARKET_META.get(option.key)
    if not metadata or option.probability is None:
        return None
    family,market,side,label,line=metadata
    if not 0 < float(option.probability) < 1:
        return None
    return Candidate(option.key,market,side,label,family,
                     float(option.probability),line,option.market_code)

def settlement_candidates():
    """Use the SAME canonical market identities for feed and immutable ledger."""
    return {
        key:Candidate(key,m[1],m[2],m[3],m[0],.5,m[4],
                      {
                          "HOME_OVER_05":"HOME_TEAM_OVER_0.5_FT",
                          "AWAY_OVER_05":"AWAY_TEAM_OVER_0.5_FT",
                          "HOME_UNDER_15":"HOME_TEAM_UNDER_1.5_FT",
                          "AWAY_UNDER_15":"AWAY_TEAM_UNDER_1.5_FT",
                          "AH_HOME_PLUS_15":"ASIAN_HANDICAP_HOME_+1.5_FT",
                          "AH_AWAY_PLUS_15":"ASIAN_HANDICAP_AWAY_+1.5_FT",
                      }[key])
        for key,m in MARKET_META.items()
    }

def _sample(rows,cap):
    rows.sort(key=lambda item:(str(item.get("event_date")),str(item.get("id"))))
    if len(rows)>cap:
        return [rows[int(i*len(rows)/cap)] for i in range(cap)]
    return rows

class ExtraMarketModel:
    def __init__(self,calibrator,validated_keys,diagnostics,ht_ratio=None):
        self.calibrator=calibrator
        self.validated_keys=frozenset(validated_keys)&PUBLISHABLE_KEYS
        self.diagnostics=diagnostics
        self.ht_ratio=ht_ratio

    def candidates(self,fixture,features,score_probs):
        options=extra_options(score_probs,home_xg=features["home"],
                              away_xg=features["away"],halftime_share=self.ht_ratio)
        result=[]
        for market in options:
            if market.key not in self.validated_keys:
                continue
            item=to_candidate(market)
            if item is None:continue
            # Calibrate with 2025 Jan-Aug results only. The ranking then
            # applies its existing uncertainty and publication controls.
            _lower, calibrated, _n=self.calibrator.score(item)
            if not 0 < calibrated < 1:continue
            result.append(replace(item,probability=calibrated))
        return result

    def to_dict(self):
        return dict(self.diagnostics,enabled_for_publication=sorted(self.validated_keys),
                    excluded_refund_or_halftime=sorted(RESEARCH_ONLY_KEYS))


def fit_extra_market_model(index,*,rho,max_training=2800,max_validation=1500):
    train=[];validate=[]
    for _,event in index.global_games:
        date=fixture_datetime(event)
        if date.year!=2025:continue
        if date.month<=8:train.append(event)
        else:validate.append(event)
    train=_sample(train,max_training)
    validate=_sample(validate,max_validation)
    calibrated=V2Calibration()
    trained=0
    for e in train:
        feat,reason=estimate_goals(e,index)
        scores=outcome_scores(e)
        if feat is None or scores is None:continue
        matrix=score_matrix(feat["home"],feat["away"],rho)
        for candidate in extra_options(matrix,home_xg=feat["home"],away_xg=feat["away"]):
            base=to_candidate(candidate)
            if base is None:continue
            label=outcome(candidate.key,*scores)
            calibrated.observe(base,label)
        trained+=1
    rows=defaultdict(lambda:{"n":0,"wins":0,"sum_p":0.,"high_n":0,"high_wins":0,"high_sum_p":0.})
    validated=0
    for e in validate:
        feat,reason=estimate_goals(e,index)
        scores=outcome_scores(e)
        if feat is None or scores is None:continue
        matrix=score_matrix(feat["home"],feat["away"],rho)
        for candidate in extra_options(matrix,home_xg=feat["home"],away_xg=feat["away"]):
            base=to_candidate(candidate)
            if base is None:continue
            _lower,p,_n=calibrated.score(base)
            observed=outcome(candidate.key,*scores)
            bucket=rows[candidate.key]
            bucket["n"]+=1
            bucket["wins"]+=int(observed)
            bucket["sum_p"]+=p
            if p>=.79:
                bucket["high_n"]+=1
                bucket["high_wins"]+=int(observed)
                bucket["high_sum_p"]+=p
        validated+=1
    accepted=set()
    report={}
    for key in sorted(PUBLISHABLE_KEYS):
        row=rows[key]
        n=row["n"]
        optimism=(row["sum_p"]-row["wins"])/n if n else None
        # Reject overconfidence even if the old overall 2026 test looks good.
        high_n=row["high_n"]
        high_optimism=(row["high_sum_p"]-row["high_wins"])/high_n if high_n else None
        passed=(n>=MIN_VALIDATION_OBSERVATIONS and
                optimism is not None and optimism<=MAX_HOLDOUT_OPTIMISM and
                high_n>=MIN_HIGH_CONF_VALIDATION_OBSERVATIONS and
                high_optimism is not None and high_optimism<=MAX_HOLDOUT_OPTIMISM)
        report[key]={"holdout_n":n,
                     "holdout_hit_rate":round(row["wins"]/n,6) if n else None,
                     "holdout_average_probability":round(row["sum_p"]/n,6) if n else None,
                     "holdout_optimism":round(optimism,6) if optimism is not None else None,
                     "high_confidence_n":high_n,
                     "high_confidence_hit_rate":round(row["high_wins"]/high_n,6) if high_n else None,
                     "high_confidence_mean_forecast":round(row["high_sum_p"]/high_n,6) if high_n else None,
                     "high_confidence_optimism":round(high_optimism,6) if high_optimism is not None else None,
                     "approved_for_publication":passed}
        if passed:accepted.add(key)
    ht_share,ht_info=half_time_share(
        [e for _,e in index.global_games if fixture_datetime(e).year==2024])
    diag={"version":"extra-markets-2025-train-and-holdout-1",
          "train_2025_jan_aug_games":trained,
          "validation_2025_sep_dec_games":validated,
          "approval_threshold":{"min_n":MIN_VALIDATION_OBSERVATIONS,
                                "high_confidence_min_n":MIN_HIGH_CONF_VALIDATION_OBSERVATIONS,
                                "max_optimism":MAX_HOLDOUT_OPTIMISM},
          "per_market":report,
          "period_scores":ht_info,
          "research_only_excluded":sorted(RESEARCH_ONLY_KEYS)}
    return ExtraMarketModel(calibrated,accepted,diag,ht_share)
