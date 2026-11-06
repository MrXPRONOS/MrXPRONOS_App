"""Orchestrates training, prediction and leakage-free walk-forward evaluation."""
from __future__ import annotations
from datetime import datetime, timezone
from math import log
from typing import Any

import numpy as np

from .domain import Match, iso_date, utc_datetime
from .model import fit, forecast, p_score, ModelError
from .store import Store
from .sources import download_fd_season
from .openfootball import download_openfootball_season, COMPETITION as OPENFOOTBALL_COMPETITION
from .calibration import data_signature


class ServiceError(ValueError):
    pass


def _training_rows(store: Store, competition: str, cutoff: datetime) -> list[Match]:
    return store.matches(competition,before=cutoff,finished=True)


def _enough_team_history(rows: list[Match], home_id: str, away_id: str, minimum: int=5):
    for team_id in (home_id,away_id):
        count=sum((m.home_id==team_id or m.away_id==team_id) for m in rows)
        if count<minimum:
            raise ServiceError(f"Historique insuffisant pour {team_id} : {count} matchs (minimum {minimum}).")


def predict(store: Store, match_id: str, *, xi: float | None=None,
            model_mode: str='auto', min_games: int=80, min_team: int=5,regularization: float=0.15,
            save: bool=True, now: datetime | None=None) -> dict:
    target=store.get_match(match_id)
    if not target:
        raise ServiceError("Match introuvable.")
    clock=utc_datetime(now or datetime.now(timezone.utc))
    if target.status=="FINISHED":
        raise ServiceError("Ce match est déjà terminé. Utiliser le backtest pour tester le passé.")
    if target.kickoff<=clock:
        raise ServiceError("La rencontre a déjà débuté, la prédiction pré-match est désactivée.")
    rows=_training_rows(store,target.competition,clock)
    _enough_team_history(rows,target.home_id,target.away_id,min_team)
    calibration=store.latest_xi_calibration(target.competition)
    if xi is None and calibration is not None:
        calib_date=utc_datetime(calibration["generated_at"])
        if calib_date > clock:
            raise ServiceError("Calibration produite après la date d'analyse : risque de fuite temporelle.")
        used_xi=calibration["selected_xi"]
        origin="optimized_real_data"
    elif xi is None:
        used_xi=0.0065
        origin="historical_default_not_optimized"
    else:
        used_xi=xi
        origin="manual_override"
    if model_mode not in ('auto','dixon_coles','poisson'):
        raise ServiceError('Mode invalide : auto, dixon_coles ou poisson.')
    selection=store.latest_model_selection(target.competition) if model_mode=='auto' else None
    # A published calibration must have ended before the intended prediction.
    if selection is not None and (
        datetime.strptime(selection['validation_end_exclusive'],'%Y-%m-%d').replace(tzinfo=timezone.utc)>clock
        or (selection.get('generated_at') and utc_datetime(selection['generated_at'])>clock)):
        raise ServiceError('La sélection des modèles provient du futur : prédiction refusée.')
    selected=selection['selected_model'] if selection else ('dixon_coles' if model_mode=='auto' else model_mode)
    model=fit(rows,as_of=clock,xi=used_xi,min_games=min_games,regularization=regularization,
              rho_fixed=0.0 if selected=='poisson' else None)
    result=forecast(model,target.home_id,target.away_id,neutral_venue=target.neutral_venue)
    result['model_selected']=selected
    result['model_selection_mode']=model_mode
    result['model_selection_calibration']=({
        'validation_start':selection['validation_start'],
        'validation_end_exclusive':selection['validation_end_exclusive'],
        'validation_n':selection['n_scored'],
        'dc_log_loss':selection['mean_dc_log_loss'],
        'poisson_log_loss':selection['mean_poisson_log_loss'],
        'gain_ci95':selection['ci95_paired_gain_for_dc'],
        'reason':selection['decision'],
    } if selection is not None else None)
    if selection is None and model_mode=='auto':
        result['model_selection_warning']='Aucune calibration comparative : Dixon-Coles appliqué par défaut.'
    result["data_quality"]={
        "last_finished_game":iso_date(rows[-1].kickoff) if rows else None,
        "days_since_latest_result":round((clock-rows[-1].kickoff).total_seconds()/86400,1) if rows else None,
        "stale_results":(clock-rows[-1].kickoff).total_seconds()>21*86400 if rows else True,
        "result_provenances":{p:sum(m.result_provenance==p for m in rows)
                              for p in sorted({m.result_provenance for m in rows})},
        "neutral_venue_games":sum(m.neutral_venue for m in rows),
        "note":"Les fournisseurs déclarent les scores, mais leur exactitude n'est pas certifiée indépendamment."}
    result["xi_source"]=origin
    result["xi_calibration"]=(
        {"calibration_id":calibration["calibration_id"],
         "selected_xi":calibration["selected_xi"],
         "validation_matches":calibration["n_scored"],
         "validation_mean_log_loss":calibration["selected_mean_log_loss"],
         "validated_through":calibration["validation_end_exclusive"],
         "stale_data":data_signature(rows)!=calibration["data_signature_sha256"]}
        if calibration is not None and origin=="optimized_real_data" else None)
    result.update({"match_id":target.id,"competition":target.competition,
                   "home_team":target.home_name,"away_team":target.away_name,
                   "kickoff":iso_date(target.kickoff),"generated_at":iso_date(clock),
                   "source":target.source,"neutral_venue":target.neutral_venue,"mode":"real" if target.source!="demo" else "DEMO / FICTIF"})
    if save:
        result["prediction_id"]=store.save_prediction(target.id,clock,result)
    return result


def sync_seasons(store: Store,code: str,seasons: list[int]) -> dict:
    results=[]
    saved=0
    for season in sorted(set(seasons)):
        try:
            rows=download_fd_season(code,season)
            saved+=store.upsert_matches(rows)
            results.append({"season":season,"imported":len(rows),"success":True})
        except ValueError as exc:
            results.append({"season":season,"imported":0,"success":False,"error":str(exc)})
    return {"competition":"fd:"+code.upper(),"rows_imported_or_updated":saved,
            "seasons":results,"all_successful":all(x["success"] for x in results)}


def _confidence_buckets(rows: list[dict], n_bins: int=5) -> list[dict]:
    """Equal-frequency bins diagnose calibration of chosen top-one score."""
    if not rows:
        return []
    ordered=sorted(rows,key=lambda r:r["top_one_probability"])
    output=[]
    for i in range(n_bins):
        part=ordered[i*len(rows)//n_bins:(i+1)*len(rows)//n_bins]
        if part:
            output.append({"n":len(part),
                           "mean_confidence":float(np.mean([x["top_one_probability"] for x in part])),
                           "observed_top1_frequency":float(np.mean([x["top1_hit"] for x in part]))})
    return output


def backtest(store: Store, competition: str, *, n_samples: int=100,
             min_games: int=80, min_team: int=5, xi: float=0.0065,
             regularization: float=0.15) -> dict:
    """Walk-forward monthly refits, same dated fixtures for independent models.

    No outcomes from the target month or any later month enter its training.
    Dixon-Coles and Poisson have SEPARATE MLE estimates (rho fixed to zero
    during the Poisson optimization). Unlike the old version, this is not a
    comparison using identical fitted attack/defense rates.
    """
    if not 1<=n_samples<=3000:
        raise ServiceError("Échantillon entre 1 et 3000 matchs requis.")
    if not 0<=xi<=0.3:
        raise ServiceError("ξ hors limites.")
    all_matches=sorted(store.matches(competition,finished=True),key=lambda m:(m.kickoff,m.id))
    if len(all_matches)<min_games+1:
        raise ServiceError("Pas assez de matchs historiques pour effectuer un backtest.")
    dates=[m.kickoff.date() for m in all_matches]
    # Eligibility checks are performed on the month training boundary below.
    # Starting with only completed historical outcomes, never inspect results
    # of the validation month while fitting its parameters.
    possible=[m for m in all_matches if sum(d<m.kickoff.date() for d in dates)>=min_games]
    targets=list(reversed(possible))[:n_samples]
    targets.sort(key=lambda m:(m.kickoff,m.id))
    buckets={}
    for m in targets:
        boundary=datetime(m.kickoff.year,m.kickoff.month,1,tzinfo=timezone.utc)
        buckets.setdefault(boundary,[]).append(m)
    detailed=[];skipped=[];folds=[]
    for cutoff,batch in sorted(buckets.items()):
        history=[m for m in all_matches if m.kickoff<cutoff]
        if len(history)<min_games:
            skipped.extend({"match_id":m.id,"reason":"Historique mensuel insuffisant."} for m in batch)
            continue
        try:
            dc=fit(history,as_of=cutoff,xi=xi,min_games=min_games,
                   regularization=regularization,maxiter=450)
            independent=fit(history,as_of=cutoff,xi=xi,min_games=min_games,
                            regularization=regularization,maxiter=450,rho_fixed=0.)
            folds.append({"start":iso_date(cutoff),"train_matches":len(history),
                          "last_training_match":iso_date(max(m.kickoff for m in history)),
                          "matches_targeted":len(batch)})
        except (ModelError,ServiceError,ValueError) as exc:
            skipped.extend({"match_id":m.id,"reason":str(exc)} for m in batch)
            continue
        for target in batch:
            try:
                _enough_team_history(history,target.home_id,target.away_id,min_team)
                result=forecast(dc,target.home_id,target.away_id,top_n=3,
                                neutral_venue=target.neutral_venue)
                benchmark=forecast(independent,target.home_id,target.away_id,top_n=3,
                                   neutral_venue=target.neutral_venue)
                exact=p_score(result["expected_home_goals"],result["expected_away_goals"],
                              dc.rho,target.home_goals,target.away_goals)
                poisson=p_score(benchmark["expected_home_goals"],benchmark["expected_away_goals"],
                                0.,target.home_goals,target.away_goals)
                same_means_poisson=p_score(result['expected_home_goals'],result['expected_away_goals'],
                                           0.,target.home_goals,target.away_goals)
                actual=f"{target.home_goals}-{target.away_goals}"
                actual_1x2=("home" if target.home_goals>target.away_goals else
                            "away" if target.home_goals<target.away_goals else "draw")
                brier=sum((result["one_x_two"][key]-int(key==actual_1x2))**2
                          for key in ("home","draw","away"))
                detailed.append({"match_id":target.id,
                    "match":f"{target.home_name} - {target.away_name}",
                    "kickoff":iso_date(target.kickoff),"actual":actual,
                    "best":result["top_scores"][0]["score"],
                    "top_three":[r["score"] for r in result["top_scores"]],
                    "top_one_probability":result["top_scores"][0]["probability"],
                    "top1_hit":actual==result["top_scores"][0]["score"],
                    "top3_hit":any(actual==r["score"] for r in result["top_scores"]),
                    "dc_log_loss":-log(max(exact,1e-300)),
                    "poisson_independent_log_loss":-log(max(poisson,1e-300)),
                    "poisson_same_intensities_log_loss":-log(max(same_means_poisson,1e-300)),
                    "poisson_best_score":benchmark['top_scores'][0]['score'],
                    "poisson_top_three":[x['score'] for x in benchmark['top_scores']],
                    "poisson_top_one_probability":benchmark['top_scores'][0]['probability'],
                    "best_score_margin_pp":result['score_top1_gap_percentage_points'],
                    "rho_effect_on_p_1_1_percent":result['rho_effect_on_p_1_1_percent'],
                    "one_x_two_brier":brier,
                    "training_matches":len(history),
                    "result_provenance":target.result_provenance,
                    "neutral_venue":target.neutral_venue})
            except (ModelError,ServiceError,ValueError) as exc:
                skipped.append({"match_id":target.id,"reason":str(exc)})
    if not detailed:
        raise ServiceError("Aucun backtest valide : données manquantes ou convergence impossible.")
    detailed.sort(key=lambda r:(r["kickoff"],r["match_id"]))
    bmark=float(np.mean([r["poisson_independent_log_loss"] for r in detailed]))
    return {"competition":competition,"n_evaluated":len(detailed),
        "n_requested":n_samples,"n_skipped":len(skipped),"n_folds":len(folds),
        "folds":folds,"top1_hit_rate":sum(r["top1_hit"] for r in detailed)/len(detailed),
        "top3_hit_rate":sum(r["top3_hit"] for r in detailed)/len(detailed),
        "mean_top1_probability":float(np.mean([r["top_one_probability"] for r in detailed])),
        "mean_dc_log_loss":float(np.mean([r["dc_log_loss"] for r in detailed])),
        "mean_poisson_independent_log_loss":bmark,
        "mean_poisson_same_intensities_log_loss":float(np.mean([r['poisson_same_intensities_log_loss'] for r in detailed])),
        "poisson_top1_hit_rate":sum(r['poisson_best_score']==r['actual'] for r in detailed)/len(detailed),
        "dc_top1_score_1_1_count":sum(r['best']=='1-1' for r in detailed),
        "poisson_top1_score_1_1_count":sum(r['poisson_best_score']=='1-1' for r in detailed),
        "mean_poisson_baseline_log_loss":bmark,
        "mean_one_x_two_brier":float(np.mean([r["one_x_two_brier"] for r in detailed])),
        "top1_confidence_buckets":_confidence_buckets(detailed),
        "baseline_note":"Poisson est réentraîné indépendamment avec rho fixé à zéro ; mêmes rencontres et mêmes coupures chronologiques que Dixon-Coles.",
        "granularity":"Réentraînement au premier jour de chaque mois de test ; aucun résultat du mois en cours utilisé.",
        "detailed":detailed,"skipped":skipped}


def sync_openfootball_seasons(store: Store, seasons: list[str], *, as_of: datetime | None = None) -> dict:
    """Import CC0 public real scores, not data from previous Mr XPRONOS systems."""
    if not seasons or len(set(seasons))>8:
        raise ServiceError("Une à huit saisons OpenFootball sont requises.")
    result=[]
    total=0
    for season in sorted(set(seasons)):
        try:
            rows,meta=download_openfootball_season(season,as_of=as_of)
            total+=store.upsert_matches(rows)
            result.append({"ok":True,**meta})
        except ValueError as exc:
            result.append({"ok":False,"season":season,"error":str(exc)})
    return {"competition":OPENFOOTBALL_COMPETITION,"source":"openfootball/football.json",
            "license":"CC0-1.0","imported_or_updated":total,"seasons":result,
            "all_successful":all(x["ok"] for x in result)}
