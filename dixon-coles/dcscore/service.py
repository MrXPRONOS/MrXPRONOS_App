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
            min_games: int=80, min_team: int=5,regularization: float=0.15,
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
    model=fit(rows,as_of=clock,xi=used_xi,min_games=min_games,regularization=regularization)
    result=forecast(model,target.home_id,target.away_id)
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
                   "source":target.source,"mode":"real" if target.source!="demo" else "DEMO / FICTIF"})
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


def backtest(store: Store,competition: str, *, n_samples: int=12,
             min_games: int=80,min_team: int=5,xi: float=0.0065,
             regularization:float=0.15) -> dict:
    """Truly out-of-sample chronological refits before each target date.

    Targets are selected among the newest eligible played games. A game on the
    same date never enters the training set at its kickoff or later.
    """
    all_matches=store.matches(competition,finished=True)
    if len(all_matches)<min_games+1:
        raise ServiceError("Pas assez de matchs historiques pour effectuer un backtest.")
    if not 1<=n_samples<=30:
        raise ServiceError("Échantillon entre 1 et 30 matchs requis.")
    # Exclude same calendar day (even for matches with no actual kick-off time).
    dates=[m.kickoff.date() for m in all_matches]
    possible=[m for m in all_matches if sum(d < m.kickoff.date() for d in dates)>=min_games]
    selected=list(reversed(possible))
    detailed=[]
    skipped=[]
    for target in selected:
        if len(detailed)>=n_samples:
            break
        cutoff=datetime.combine(target.kickoff.date(),datetime.min.time(),tzinfo=timezone.utc)
        historical=[m for m in all_matches if m.kickoff < cutoff]
        try:
            _enough_team_history(historical,target.home_id,target.away_id,min_team)
            model=fit(historical,as_of=cutoff,xi=xi,min_games=min_games,
                      regularization=regularization,maxiter=450)
            result=forecast(model,target.home_id,target.away_id,top_n=3)
            exact=p_score(result["expected_home_goals"],result["expected_away_goals"],
                          result["rho"],target.home_goals,target.away_goals)
            poisson_baseline=p_score(result["expected_home_goals"],result["expected_away_goals"],
                                     0.,target.home_goals,target.away_goals)
            actual=f"{target.home_goals}-{target.away_goals}"
            detailed.append({"match_id":target.id,"match":f"{target.home_name} - {target.away_name}",
                            "kickoff":iso_date(target.kickoff),"actual":actual,
                            "best":result["top_scores"][0]["score"],
                            "top_three":[r["score"] for r in result["top_scores"]],
                            "top_one_probability":result["top_scores"][0]["probability"],
                            "top1_hit":actual==result["top_scores"][0]["score"],
                            "top3_hit":actual in [s["score"] for s in result["top_scores"]],
                            "dc_log_loss":-log(max(exact,1e-300)),
                            "poisson_same_intensities_log_loss":-log(max(poisson_baseline,1e-300)),
                            "training_matches":len(historical)})
        except (ModelError,ServiceError,ValueError) as exc:
            skipped.append({"match_id":target.id,"reason":str(exc)})
    if not detailed:
        raise ServiceError("Aucun backtest valide : données manquantes ou convergence impossible.")
    detailed.sort(key=lambda r:r["kickoff"])
    return {"competition":competition,"n_evaluated":len(detailed),
            "n_skipped":len(skipped),"top1_hit_rate":sum(r["top1_hit"] for r in detailed)/len(detailed),
            "top3_hit_rate":sum(r["top3_hit"] for r in detailed)/len(detailed),
            "mean_top1_probability":float(np.mean([r["top_one_probability"] for r in detailed])),
            "mean_dc_log_loss":float(np.mean([r["dc_log_loss"] for r in detailed])),
            "mean_poisson_baseline_log_loss":float(np.mean([r["poisson_same_intensities_log_loss"] for r in detailed])),
            "baseline_note":"Poisson utilise les mêmes intensités apprises par Dixon-Coles, rho=0 : comparaison de la correction, pas un recalibrage indépendant.",
            "detailed":detailed,"skipped":skipped[:30]}


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
