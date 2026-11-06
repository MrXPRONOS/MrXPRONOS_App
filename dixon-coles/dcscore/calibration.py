"""Leakage-free tuning of Dixon-Coles time-decay xi on *observed* real scores.

Precommitted candidate grid, fixed chronological validation blocks, identical
scored fixtures for all candidates and strictly proper exact-score log loss.
No optimizer sees the result of a validation fixture while fitting that fold.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from math import isfinite, log

import numpy as np

from .domain import Match, iso_date, utc_datetime
from .model import ModelError, fit, p_score, forecast
from .store import Store

REFERENCE_XI = 0.0065
DEFAULT_CANDIDATES = (0.0, 0.0015, 0.003, 0.0065, 0.010, 0.016, 0.025, 0.040)


class CalibrationError(ValueError):
    pass


def _date(value: str, field: str) -> datetime:
    try:
        dt=datetime.strptime(value,"%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise CalibrationError(f"{field} : date attendue AAAA-MM-JJ.") from exc
    if dt.day != 1:
        raise CalibrationError(f"{field} doit être le premier jour du mois.")
    return dt


def _add_months(dt: datetime, months: int) -> datetime:
    idx=dt.year*12+(dt.month-1)+months
    return dt.replace(year=idx//12,month=idx%12+1)


def data_signature(rows: list[Match]) -> str:
    h=sha256()
    for m in sorted(rows,key=lambda t:t.id):
        data=f"{m.id}|{iso_date(m.kickoff)}|{m.home_id}|{m.away_id}|{m.home_goals}|{m.away_goals}\n"
        h.update(data.encode("utf-8"))
    return h.hexdigest()


def _eligible(rows: list[Match], min_team: int) -> list[Match]:
    count=Counter(t for m in rows for t in (m.home_id,m.away_id))
    return [m for m in rows if count[m.home_id]>=min_team and count[m.away_id]>=min_team]


def validate_candidates(values: tuple[float,...] | list[float]) -> tuple[float,...]:
    if not 2 <= len(values) <= 16:
        raise CalibrationError("La grille doit contenir de 2 à 16 valeurs distinctes.")
    xi=tuple(float(value) for value in values)
    if any(not isfinite(x) or x < 0 or x > 0.3 for x in xi):
        raise CalibrationError("Valeurs xi invalides (0 à 0,3).")
    if len(set(xi)) != len(xi):
        raise CalibrationError("Les valeurs xi doivent être distinctes.")
    if REFERENCE_XI not in xi:
        raise CalibrationError("La grille doit contenir xi=0,0065 comme référence historique.")
    return tuple(sorted(xi))


def evaluate_xi(*, rows: list[Match], eval_start: str, eval_end: str,
                as_of: datetime | None = None,
                candidates: tuple[float,...] = DEFAULT_CANDIDATES,
                block_months: int = 2, min_games: int = 400,
                min_team: int = 5, regularization: float = 0.15,
                min_folds: int = 3, min_scored: int = 100,
                maxiter: int = 450, include_details: bool = False) -> dict:
    """Calibrate on strictly prior matches, evaluate fixed blocks equally.

    The target window is [eval_start, eval_end) by calendar month. The last
    boundary must not exceed as_of's calendar month unless explicitly ending
    at the beginning of the month containing as_of (incomplete current month
    is intentionally excluded). Same-day match results never leak into a fold.
    All candidates use exactly the same validation fixtures.
    """
    cands=validate_candidates(candidates)
    start,end=_date(eval_start,"eval_start"),_date(eval_end,"eval_end")
    now=utc_datetime(as_of or datetime.now(timezone.utc))
    if start>=end:
        raise CalibrationError("La période de validation doit être croissante.")
    if end>datetime(now.year,now.month,1,tzinfo=timezone.utc):
        raise CalibrationError("La validation doit couvrir uniquement des mois entièrement terminés.")
    if not 1<=block_months<=6:
        raise CalibrationError("block_months doit être compris entre 1 et 6.")
    if not 1<=min_team<=100 or not 12<=min_games<=10000:
        raise CalibrationError("Seuils d'historique invalides.")
    if min_folds<1 or min_scored<1:
        raise CalibrationError("Seuils de validation invalides.")
    if not 0<=regularization<=10:
        raise CalibrationError("Régularisation invalide.")
    if not 50<=maxiter<=2000:
        raise CalibrationError("maxiter hors limites.")
    # A mix of demo/manual and real results is not a defensible calibration.
    finished=[m for m in rows if m.status=="FINISHED" and m.kickoff<now]
    if any(m.source in ("demo","manual") or m.competition.startswith("demo:") for m in finished):
        raise CalibrationError("Données fictives ou résultats manuels non admissibles à l'optimisation réelle.")
    if not finished or len({m.competition for m in finished})!=1:
        raise CalibrationError("Une compétition réelle unique et suffisamment renseignée est nécessaire.")
    if len({m.id for m in finished})!=len(finished):
        raise CalibrationError("Identifiants de matchs dupliqués : optimisation refusée.")
    finished.sort(key=lambda m:(m.kickoff,m.id))
    if not any(m.kickoff<start for m in finished):
        raise CalibrationError("Aucune donnée d'apprentissage avant la fenêtre de validation.")
    folds=[]
    boundary=start
    while boundary<end:
        block_end=min(_add_months(boundary,block_months),end)
        previous=[m for m in finished if m.kickoff<boundary]
        targets=[m for m in finished if boundary<=m.kickoff<block_end]
        targets=_eligible_from_train(targets,previous,min_team)
        if len(previous)>=min_games and targets:
            folds.append((boundary,block_end,previous,targets))
        boundary=block_end
    n_scored=sum(len(f[3]) for f in folds)
    if len(folds)<min_folds or n_scored<min_scored:
        raise CalibrationError(f"Validation réelle insuffisante : {len(folds)} blocs et {n_scored} matchs éligibles; minimum {min_folds} blocs / {min_scored} matchs.")
    reports=[]
    # Cached once per fold per xi. Scores in a fold have never entered its fit.
    for xi in cands:
        losses=[]; hits1=0; hits3=0; results=[]
        for boundary,block_end,training,targets in folds:
            try:
                model=fit(training,as_of=boundary,xi=xi,min_games=min_games,
                          regularization=regularization,maxiter=maxiter)
                for match in targets:
                    lam,mu=model.expected_goals(match.home_id,match.away_id)
                    probability=p_score(lam,mu,model.rho,match.home_goals,match.away_goals)
                    if not (0<probability<=1 and isfinite(probability)):
                        raise CalibrationError("Probabilité non finie ou nulle pendant la validation.")
                    loss=-log(max(probability,1e-300))
                    prediction=forecast(model,match.home_id,match.away_id,top_n=3)
                    actual=f"{match.home_goals}-{match.away_goals}"
                    hits1+=int(actual==prediction["top_scores"][0]["score"])
                    hits3+=int(any(actual==p["score"] for p in prediction["top_scores"]))
                    losses.append(loss)
                    if include_details:
                        results.append({"match_id":match.id,"kickoff":iso_date(match.kickoff),
                                        "actual":actual,"log_loss":loss,
                                        "predicted":prediction["top_scores"][0]["score"]})
            except ModelError as exc:
                raise CalibrationError(f"Échec de l'apprentissage xi={xi} pour le bloc {boundary.date()} : {exc}") from exc
        if len(losses)!=n_scored:
            raise CalibrationError("Les candidats n'ont pas été évalués sur le même jeu de validation.")
        summary={"xi":xi,"n_scored":n_scored,"mean_exact_score_log_loss":float(np.mean(losses)),
                 "top1_hit_rate":hits1/n_scored,"top3_hit_rate":hits3/n_scored}
        if include_details:summary["predictions"]=results
        reports.append(summary)
    best=min(reports,key=lambda r:(r["mean_exact_score_log_loss"],abs(r["xi"]-REFERENCE_XI),r["xi"]))
    ref=next(r for r in reports if r["xi"]==REFERENCE_XI)
    fold_summaries=[{"train_before":iso_date(t0),"test_before":iso_date(t1),
                     "train_matches":len(train),"scored_matches":len(targets),
                     "latest_training_match":iso_date(train[-1].kickoff)}
                    for t0,t1,train,targets in folds]
    return {"schema_version":1,"competition":finished[0].competition,"data_source":sorted({m.source for m in finished}),
            "data_signature_sha256":data_signature(finished),"data_latest_result":iso_date(finished[-1].kickoff),
            "generated_at":iso_date(now),"validation_start":eval_start,"validation_end_exclusive":eval_end,
            "block_months":block_months,"min_games":min_games,"min_team_games":min_team,
            "regularization":regularization,"n_all_results":len(finished),"n_folds":len(folds),
            "n_scored":n_scored,"selected_xi":best["xi"],"objective":"mean held-out exact-score negative log likelihood",
            "selected_mean_log_loss":best["mean_exact_score_log_loss"],
            "historical_xi":REFERENCE_XI,"historical_mean_log_loss":ref["mean_exact_score_log_loss"],
            "improvement_vs_historical":ref["mean_exact_score_log_loss"]-best["mean_exact_score_log_loss"],
            "candidate_results":reports,"folds":fold_summaries,
            "notes":["Calibration fondée sur les résultats observés, sans match fictif.",
                     "Chaque bloc ne s'entraîne que sur les résultats des blocs précédents.",
                     "Même ensemble de matchs test pour toutes les valeurs de xi.",
                     "La grille est optimisée sur cette fenêtre : les gains dans cette fenêtre ne sont PAS des performances hors-échantillon finales."]}


def _eligible_from_train(targets: list[Match], historical: list[Match], min_team: int) -> list[Match]:
    count=Counter(t for m in historical for t in (m.home_id,m.away_id))
    return [m for m in targets if count[m.home_id]>=min_team and count[m.away_id]>=min_team]


def tune_xi(store: Store, competition: str, *, save: bool = True, **kwargs) -> dict:
    rows=store.matches(competition,finished=True)
    if not rows:
        raise CalibrationError(f"Aucun résultat disponible : {competition}.")
    result=evaluate_xi(rows=rows,**kwargs)
    if save:
        store.save_xi_calibration(result)
    return result


def holdout_evaluation(rows: list[Match], *, xi: float, eval_start: str, eval_end: str,
                       block_months: int=1, min_games: int=400, min_team: int=5,
                       regularization: float=0.15, as_of: datetime | None=None) -> dict:
    """Independent FINAL test, not used in xi selection, with fixed chosen xi.

    Does not call evaluate_xi, which enforces two-or-more candidate search.
    """
    start,end=_date(eval_start,"holdout_start"),_date(eval_end,"holdout_end")
    now=utc_datetime(as_of or datetime.now(timezone.utc))
    if start>=end or end>datetime(now.year,now.month,1,tzinfo=timezone.utc):
        raise CalibrationError("Période de holdout invalide ou incomplète.")
    if not 0<=xi<=0.3 or not isfinite(xi):
        raise CalibrationError("Xi hors limites.")
    rows=sorted((m for m in rows if m.status=='FINISHED' and m.kickoff<now),key=lambda m:(m.kickoff,m.id))
    totals=[];top1=0;top3=0;blocks=[];b=start
    while b<end:
        e=min(_add_months(b,block_months),end)
        historical=[m for m in rows if m.kickoff<b]
        target=_eligible_from_train([m for m in rows if b<=m.kickoff<e],historical,min_team)
        if len(historical)>=min_games and target:
            model=fit(historical,as_of=b,xi=xi,min_games=min_games,regularization=regularization)
            for m in target:
                lam,mu=model.expected_goals(m.home_id,m.away_id)
                p=p_score(lam,mu,model.rho,m.home_goals,m.away_goals)
                if p<=0 or not isfinite(p):raise CalibrationError("Probabilité holdout invalide.")
                totals.append(-log(p))
                predicted=forecast(model,m.home_id,m.away_id,top_n=3)["top_scores"]
                score=f"{m.home_goals}-{m.away_goals}"
                top1+=int(score==predicted[0]["score"])
                top3+=int(any(score==s["score"] for s in predicted))
            blocks.append({"start":iso_date(b),"end":iso_date(e),"matches":len(target)})
        b=e
    if not totals:
        raise CalibrationError("Aucun match admissible pour l'évaluation finale indépendante.")
    return {"selected_xi":xi,"test_start":eval_start,"test_end_exclusive":eval_end,
            "n_tested":len(totals),"n_blocks":len(blocks),"mean_log_loss":float(np.mean(totals)),
            "top1_hit_rate":top1/len(totals),"top3_hit_rate":top3/len(totals),"blocks":blocks,
            "note":"Évaluation sur période ultérieure à la calibration, non utilisée pour choisir xi."}
