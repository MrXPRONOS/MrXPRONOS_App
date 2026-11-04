"""Modèle BTTS Oui/Non spécialisé, sans dépendance ML externe.

Entraînement: janvier-août 2024. Choix du mélange avec Poisson/Dixon-Coles:
septembre-décembre 2024. Calibration: début 2025 (par bsd_v2_policies).
Validation qualité: fin 2025. Backtest 2026 indépendant.

Toutes les variables viennent de matchs terminés au moins quatre heures
avant le coup d'envoi. Aucun corner, tir ou faute.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from math import exp, log
from typing import Iterable, Optional

from bsd_h2h import _team_id
from bsd_v2_core import fixture_datetime, league_key, outcome_scores, estimate_goals, score_matrix, markets_from_matrix

BASE_RATE = 0.50
FEATURE_COUNT = 11
FEATURE_LABELS = ("intercept", "home_scores", "away_scores", "home_concedes",
                  "away_concedes", "home_venue_scores", "away_venue_scores",
                  "home_venue_concedes", "away_venue_concedes",
                  "league_btts", "joint_scoring_strength")


def _clamp(p):
    return max(.01, min(.99, float(p)))


def _sigmoid(z):
    z = max(-30.0, min(30.0, z))
    return 1.0 / (1.0 + exp(-z))


def _rates(games, team_id, kickoff, *, venue=None):
    score_num = concede_num = weight_sum = 0.0
    for match in games:
        scores = outcome_scores(match)
        if scores is None:
            continue
        home = _team_id(match, "home") == team_id
        if venue and home != (venue == "home"):
            continue
        scored, conceded = (scores if home else scores[::-1])
        age = max(0, (kickoff - fixture_datetime(match)).total_seconds()/86400)
        weight = exp(-log(2.0) * age / 90.0)
        weight_sum += weight
        score_num += weight * int(scored > 0)
        concede_num += weight * int(conceded > 0)
    # Beta-like shrinkage towards league-agnostic prior, to control sparse form.
    return ((score_num + 4 * .72)/(weight_sum + 4),
            (concede_num + 4 * .72)/(weight_sum + 4),
            weight_sum)


def _opponent_adjusted_scoring(games,team_id,index,at,league_prior):
    """Each scored-goal occurrence weighted by opponents' past clean-sheet rate."""
    values=[]
    for match in games:
        score=outcome_scores(match)
        if score is None:continue
        home=_team_id(match,"home")==team_id
        scored=score[0 if home else 1]
        opponent=_team_id(match,"away" if home else "home")
        previous=index.team(opponent,at,limit=12) if opponent else []
        conceded_frequency=[]
        for past in previous:
            old=outcome_scores(past)
            if old is None:continue
            opponent_home=_team_id(past,"home")==opponent
            conceded=old[1 if opponent_home else 0]
            conceded_frequency.append(int(conceded>0))
        concede_rate=(sum(conceded_frequency)+6*league_prior)/(len(conceded_frequency)+6)
        strength=max(.80,min(1.20,league_prior/max(.25,concede_rate)))
        age=max(0.,(at-fixture_datetime(match)).total_seconds()/86400)
        values.append((int(scored>0)*strength,exp(-log(2.)*age/90.)))
    weight=sum(w for _v,w in values)
    return min(.99,max(.01,(sum(v*w for v,w in values)+5*league_prior)/(weight+5)))


def btts_features(event, index):
    """Features pre-match only, returns None for teams without enough recent form."""
    hid, aid = _team_id(event, "home"), _team_id(event, "away")
    if not hid or not aid or hid == aid:
        return None
    try:
        at = fixture_datetime(event)
    except (ValueError, TypeError):
        return None
    home_games = index.team(hid, at, limit=14)
    away_games = index.team(aid, at, limit=14)
    if min(len(home_games), len(away_games)) < 5:
        return None
    hgf, hga, _ = _rates(home_games, hid, at)
    agf, aga, _ = _rates(away_games, aid, at)
    home_venue = index.team(hid, at, limit=12, venue="home")
    away_venue = index.team(aid, at, limit=12, venue="away")
    # When venue sample is weak, the general form carries most of the weight.
    hvgf, hvga, hw = _rates(home_venue, hid, at, venue="home")
    avgf, avga, aw = _rates(away_venue, aid, at, venue="away")
    hv_weight = hw / (hw + 6.)
    av_weight = aw / (aw + 6.)
    hvgf = hv_weight*hvgf + (1-hv_weight)*hgf
    hvga = hv_weight*hvga + (1-hv_weight)*hga
    avgf = av_weight*avgf + (1-av_weight)*agf
    avga = av_weight*avga + (1-av_weight)*aga
    games = index.league(league_key(event), at, limit=300)
    btts_wins = sum(int(x["home_score"] > 0 and x["away_score"] > 0)
                    for x in games if outcome_scores(x) is not None)
    league_p = (btts_wins + 35*BASE_RATE)/(len(games) + 35)
    # Strength adjustment: the opponent's tendency to concede matters as
    # much as the team's own tendency to score.
    adjusted_home=_opponent_adjusted_scoring(home_games,hid,index,at,.72)
    adjusted_away=_opponent_adjusted_scoring(away_games,aid,index,at,.72)
    home_scoring = .45*hvgf + .35*avga + .20*adjusted_home
    away_scoring = .45*avgf + .35*hvga + .20*adjusted_away
    return (1.0, hgf-.5, agf-.5, hga-.5, aga-.5,
            hvgf-.5, avgf-.5, hvga-.5, avga-.5,
            league_p-.5, home_scoring*away_scoring-.36)


@dataclass(frozen=True)
class BTTSModel:
    weights: tuple
    blend: float = 0.0
    train_count: int = 0
    validation_count: int = 0
    team_blend: float = 0.0
    league_blend: float = 0.0
    team_model: object = None
    league_model: object = None
    zero_blend: float = 0.0
    zero_model: object = None
    ensemble_model: object = None

    def predict_specialized(self, features):
        if features is None:
            return None
        if len(features) != len(self.weights):
            raise ValueError("BTTS feature dimensionality changed")
        return _clamp(_sigmoid(sum(w*x for w,x in zip(self.weights,features))))

    def predict(self, event, index, baseline_probability):
        if (self.blend<=0 and self.team_blend<=0 and self.league_blend<=0 and self.zero_blend<=0
                and (self.ensemble_model is None or self.ensemble_model.weights[0]>=1.)):
            return baseline_probability
        features = btts_features(event,index)
        p = self.predict_specialized(features)
        if p is None:
            return baseline_probability
        combined = (1.0-self.blend)*baseline_probability + self.blend*p
        if self.team_blend>0:
            from bsd_v2_btts_team import team_scoring_probabilities
            team = team_scoring_probabilities(event,index,model=self.team_model)
            if team is not None:
                combined=(1.0-self.team_blend)*combined + self.team_blend*team['btts_yes']
        if self.league_blend>0:
            from bsd_v2_btts_league import league_btts_deviation
            deviation=(self.league_model.deviation(event) if self.league_model is not None
                       else league_btts_deviation(event,index))
            combined+=self.league_blend*deviation
        if self.zero_blend>0 and self.zero_model is not None:
            zero=self.zero_model.predict(event,index)
            if zero is not None:
                combined=(1.0-self.zero_blend)*combined+self.zero_blend*zero['btts_yes']
        if self.ensemble_model is not None and self.ensemble_model.weights[0]<1.:
            combined=self.ensemble_model.predict(event,index,combined)
        return _clamp(combined)

    def to_dict(self):
        return {"version":"btts-model-1","weights":list(self.weights),
                "blend":self.blend,"team_blend":self.team_blend,
                "league_blend":self.league_blend,
                "zero_blend":self.zero_blend,
                "zero_model":self.zero_model.to_dict() if self.zero_model else None,
                "ensemble_model":self.ensemble_model.to_dict() if self.ensemble_model else None,
                "team_model":({"trained_games":self.team_model.trained_games,
                  "home_weights":list(self.team_model.home_weights),
                  "away_weights":list(self.team_model.away_weights)} if self.team_model else None),
                "league_model":self.league_model.to_dict() if self.league_model else None,
                "train_count":self.train_count,
                "validation_count":self.validation_count}


def btts_candidates(event, index, candidates, model=None):
    """Override ONLY BTTS_YES/BTTS_NO with complementary estimated probabilities."""
    if model is None:
        return candidates
    original = next((c.probability for c in candidates if c.key=="BTTS_YES"),None)
    if original is None:
        return candidates
    p = model.predict(event,index,original)
    return [replace(c,probability=p if c.key=="BTTS_YES" else 1.-p)
            if c.key in ("BTTS_YES","BTTS_NO") else c for c in candidates]



def btts_quality_rejection(expected, model, poisson_p, specialized_p):
    """Pre-price BTTS veto for new production selections only.

    This is not an 80% guarantee; it prevents misleading confidence from a
    sparse-history Poisson fallback and requires home/away evidence.
    """
    if model is None or not (model.blend>0 or model.team_blend>0 or model.league_blend>0 or model.zero_blend>0 or
            (model.ensemble_model is not None and model.ensemble_model.weights[0]<1.)):
        return "btts_no_active_specialist"
    if min(expected["home_recent_matches"], expected["away_recent_matches"]) < 8:
        return "btts_insufficient_team_form"
    if min(expected["home_venue_matches"], expected["away_venue_matches"]) < 3:
        return "btts_insufficient_venue_form"
    if expected["league_samples"] < 40:
        return "btts_insufficient_league_form"
    if expected["max_last_match_age_days"] > 60:
        return "btts_stale_form"
    if abs(specialized_p-poisson_p) > .15:
        return "btts_models_disagree"
    return None


def _train_logistic(rows, epochs=220):
    # Deterministic full-batch gradient descent with mild L2 penalty.
    weights = [0.0]*FEATURE_COUNT
    if not rows:
        return tuple(weights)
    for iteration in range(epochs):
        gradient = [0.0]*FEATURE_COUNT
        for x,y in rows:
            diff = _sigmoid(sum(a*b for a,b in zip(weights,x))) - y
            for j in range(FEATURE_COUNT):
                gradient[j] += diff*x[j]
        eta = 2.0/(1.0 + iteration/220)
        for j in range(FEATURE_COUNT):
            reg = .003*weights[j] if j>0 else 0.0
            weights[j] -= eta*(gradient[j]/len(rows) + reg)
            weights[j] = max(-8.0,min(8.0,weights[j]))
    return tuple(weights)


def fit_btts_model(index, *, rho=0.0, max_training=3600, max_validation=900):
    """Two-stage BTTS with independent team scorer and league calibration.

    Supervised BTTS/side-goal fit: Jan-Aug 2024.
    Mixture choice: Sep-Dec 2024.
    League residual fit: Jan-Jun 2025.
    League coefficient selection: Jul-Aug 2025.
    Independent acceptance: Sep-Dec 2025 (also used as existing quality fold).
    Final untouched test: all of 2026. NEVER fit to 2026 outcomes.
    """
    from bsd_v2_btts_team import fit_team_scoring_model, team_scoring_probabilities
    from bsd_v2_btts_league import fit_league_residual_model
    from bsd_v2_btts_zero import fit_zero_goal_model
    from bsd_v2_btts_ensemble import fit_ensemble

    training, validation = [], []
    for _stamp,event in index.global_games:
        at=fixture_datetime(event)
        if at.year!=2024:
            continue
        try:
            feat=btts_features(event,index)
            if feat is None:continue
            scored=outcome_scores(event)
            if scored is None:continue
            row=(at,event,feat,int(scored[0]>0 and scored[1]>0))
            if at.month<=8:
                training.append(row)
            else:
                validation.append(row)
        except (TypeError,ValueError,KeyError):
            continue

    def sample(items,n):
        ordered=sorted(items,key=lambda item:(item[0],str(item[1]["id"])))
        if len(ordered)<=n:return ordered
        return [ordered[int(i*len(ordered)/n)] for i in range(n)]

    available_training,available_validation=len(training),len(validation)
    training=sample(training,max_training)
    validation=sample(validation,max_validation)
    weights=_train_logistic([(feat,y) for _at,_event,feat,y in training])
    team_model=fit_team_scoring_model(index,[event for _at,event,_feat,_y in training])
    zero_model=fit_zero_goal_model(index,[event for _at,event,_feat,_y in training])
    provisional=BTTSModel(weights,1.0,len(training),len(validation),team_model=team_model)

    def fixture_forecast(event,features=None):
        expected,reason=estimate_goals(event,index)
        if expected is None:
            return None
        original=markets_from_matrix(score_matrix(expected["home"],expected["away"],rho))
        p0=next(c.probability for c in original if c.key=="BTTS_YES")
        feats=features if features is not None else btts_features(event,index)
        if feats is None:
            return None
        p1=provisional.predict_specialized(feats)
        side=team_scoring_probabilities(event,index,model=team_model)
        if side is None:
            return None
        return p0,p1,side["btts_yes"]

    observed=[]
    for _at,event,features,y in validation:
        forecast=fixture_forecast(event,features)
        if forecast is not None:
            observed.append((*forecast,y))

    def mixed(p0,p1,pt,blend,team_blend):
        value=(1-blend)*p0+blend*p1
        return _clamp((1-team_blend)*value+team_blend*pt)

    def score(rows,blend,team_blend,league_model=None,league_blend=0.):
        if not rows:return float("inf")
        total=0.
        for event,p0,p1,pt,y in rows:
            p=mixed(p0,p1,pt,blend,team_blend)
            if league_model is not None and league_blend:
                p=_clamp(p+league_blend*league_model.deviation(event))
            total+=(p-y)**2
        return total/len(rows)

    rows_2024=[(None,*r) for r in observed]
    enough_training=len(training)>=100 and len(rows_2024)>=50
    chosen=chosen_team=chosen_league=chosen_zero=0.
    league_model=None
    stages={"team_candidate_brier":None,"league_candidate_brier":None,
             "zero_2024_validation":None,"zero_2025_holdout":None,
             "zero_activated":False,
            "team_holdout_2025_brier":None,"league_holdout_2025_brier":None,
            "team_activated":False,"league_activated":False}

    if enough_training:
        blends=(0.,.25,.5,.75,1.)
        best_blend=min(blends,key=lambda b:score(rows_2024,b,0.))
        if score(rows_2024,best_blend,0.)<=score(rows_2024,0.,0.)-.001:
            chosen=best_blend

        # Model 1: independent home/away goal-scoring probabilities.
        # 2024 chooses the candidate. A separate late-2025 fold can veto it.
        team_grid=(0.,.15,.30,.45,.60,.75,1.)
        team_option=min(team_grid,key=lambda b:score(rows_2024,chosen,b))
        if (team_option>0 and
            score(rows_2024,chosen,team_option)<=score(rows_2024,chosen,0.)-.0003):
            chosen_team=team_option
        stages["team_candidate_brier"]={
            "baseline":round(score(rows_2024,chosen,0.),6),
            "challenger":round(score(rows_2024,chosen,team_option),6),
            "proposed_blend":team_option}

        # 2025 is split into distinct, chronologically fixed folds.
        folds={"league_train":[], "league_tune":[], "final_holdout":[]}
        for _stamp,event in index.global_games:
            at=fixture_datetime(event)
            if at.year!=2025:continue
            if at.month<=6:
                key="league_train"
            elif at.month<=8:
                key="league_tune"
            else:
                key="final_holdout"
            folds[key].append((at,event))
        cap={"league_train":1500,"league_tune":550,"final_holdout":1000}
        for name in folds:
            rows=[]
            for _at,event,_unused1,_unused2 in sample([(at,e,None,None) for at,e in folds[name]],cap[name]):
                try:
                    forecast=fixture_forecast(event)
                    scores=outcome_scores(event)
                    if forecast is None or scores is None:continue
                    y=int(scores[0]>0 and scores[1]>0)
                    rows.append((event,*forecast,y))
                except (KeyError,TypeError,ValueError,OverflowError):
                    continue
            folds[name]=rows

        holdout=folds["final_holdout"]
        stages["holdout_2025_observations"]=len(holdout)
        if chosen_team and len(holdout)>=250:
            base=score(holdout,chosen,0.)
            trial=score(holdout,chosen,chosen_team)
            stages["team_holdout_2025_brier"]={
                "baseline":round(base,6),"challenger":round(trial,6)}
            if trial>base-.0001:
                chosen_team=0.
        elif chosen_team:
            chosen_team=0.

        # Model 2: empirical-Bayes correction of systematic per-league errors.
        # The correction is fit only on Jan-Jun 2025, not on 2026 fixtures.
        learn_rows=[(event,mixed(p0,p1,pt,chosen,chosen_team),y)
                    for event,p0,p1,pt,y in folds["league_train"]]
        league_model=fit_league_residual_model(learn_rows)
        tune=folds["league_tune"]
        gamma_grid=(0.,.25,.5,.75,1.)
        if len(tune)>=150 and len(holdout)>=250:
            best_gamma=min(gamma_grid,key=lambda g:score(
                tune,chosen,chosen_team,league_model,g))
            base_tune=score(tune,chosen,chosen_team)
            trial_tune=score(tune,chosen,chosen_team,league_model,best_gamma)
            base_hold=score(holdout,chosen,chosen_team)
            trial_hold=score(holdout,chosen,chosen_team,league_model,best_gamma)
            stages["league_candidate_brier"]={
                "baseline":round(base_tune,6),
                "challenger":round(trial_tune,6),
                "proposed_blend":best_gamma}
            stages["league_holdout_2025_brier"]={
                "baseline":round(base_hold,6),
                "challenger":round(trial_hold,6)}
            if (best_gamma>0 and trial_tune<=base_tune-.0001
                and trial_hold<=base_hold-.0001):
                chosen_league=best_gamma
        stages["league_offsets"]=league_model.to_dict()

        # Independent scoreless-hazard candidate trained only in Jan-Aug 2024.
        # 2024 Q4 selects its blend; late 2025 vetoes false improvement.
        def zero_rows(source, include_league):
            values=[]
            if zero_model is None:return values
            for event,p0,p1,pt,y in source:
                p_base=mixed(p0,p1,pt,chosen,chosen_team)
                if include_league and chosen_league and league_model is not None:
                    p_base=_clamp(p_base+chosen_league*league_model.deviation(event))
                predicted=zero_model.predict(event,index)
                p_zero=predicted["btts_yes"] if predicted else p_base
                values.append((p_base,p_zero,y))
            return values

        zero_val=[]
        for _at,event,feat,y in validation:
            base=fixture_forecast(event,feat)
            if base is not None:
                zero_val.append((event,*base,y))
        zero_train_rows=zero_rows(zero_val,False)
        zero_hold_rows=zero_rows(holdout,True)

        def zero_brier(rows,coef):
            return (sum(((1-coef)*p0+coef*pz-y)**2 for p0,pz,y in rows)/len(rows)
                    if rows else float("inf"))

        if (len(zero_train_rows)>=100 and len(zero_hold_rows)>=250
                and zero_model is not None):
            zero_grid=(0.,.1,.2,.3,.4,.5,.65,.8,1.)
            best_zero=min(zero_grid,key=lambda alpha:zero_brier(zero_train_rows,alpha))
            base_train=zero_brier(zero_train_rows,0.)
            trial_train=zero_brier(zero_train_rows,best_zero)
            base_hold=zero_brier(zero_hold_rows,0.)
            trial_hold=zero_brier(zero_hold_rows,best_zero)
            stages["zero_2024_validation"]={
                "n":len(zero_train_rows),"baseline":round(base_train,6),
                "candidate":round(trial_train,6),"proposed_blend":best_zero}
            stages["zero_2025_holdout"]={
                "n":len(zero_hold_rows),"baseline":round(base_hold,6),
                "candidate":round(trial_hold,6)}
            if (best_zero>0 and trial_train<=base_train-.00020
                    and trial_hold<=base_hold-.00015):
                chosen_zero=best_zero
        stages["zero_model_training"]=zero_model.training_matches if zero_model else 0
    else:
        stages["reason"]="insufficient_2024_training_or_validation"

    # Fit all challengers with 2024-only training, and independently verify
    # any ensemble improvement in late 2025. No 2026 result can tune weights.
    baseline_model=BTTSModel(weights,chosen,len(training),len(observed),
                             chosen_team,chosen_league,team_model,league_model,
                             chosen_zero,zero_model)
    ensemble,ensemble_info=fit_ensemble(
        index,
        [event for _at,event,_feat,_y in training],
        [event for _at,event,_feat,_y in validation],
        [event for event,*_unused in folds["final_holdout"]] if enough_training else [],
        baseline_model,rho=rho)
    stages["four_model_suite"]=ensemble_info
    stages["zero_activated"]=chosen_zero>0
    stages["team_activated"]=chosen_team>0
    stages["league_activated"]=chosen_league>0
    diag={
        "training_period":"2024-01 to 2024-08",
        "validation_period":"2024-09 to 2024-12",
        "league_fit_period":"2025-01 to 2025-06",
        "league_tune_period":"2025-07 to 2025-08",
        "independent_guard_period":"2025-09 to 2025-12",
        "trained":len(training),"validated":len(observed),
        "available_training":available_training,
        "available_validation":available_validation,
        "train_vs_validation_leakage":False,
        "blend":chosen,"team_blend":chosen_team,"league_blend":chosen_league,
        "zero_blend":chosen_zero,
        "poisson_validation_brier":round(score(rows_2024,0.,0.),6) if observed else None,
        "specialized_validation_brier":round(score(rows_2024,1.,0.),6) if observed else None,
        "selected_validation_brier":round(score(rows_2024,chosen,chosen_team),6) if observed else None,
        "team_scoring_training":team_model.trained_games if team_model else 0,
        **stages
    }
    return BTTSModel(weights,chosen,len(training),len(observed),chosen_team,
                     chosen_league,team_model,league_model,chosen_zero,zero_model,
                     ensemble),diag
