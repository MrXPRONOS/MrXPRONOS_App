"""Second-pass Dixon-Coles/Poisson cold-start estimates for real fixtures.

A trained team-strength estimate is preferred. When too little pre-cutoff
history exists, rho=0 is the independent-Poisson boundary of Dixon-Coles;
the prior is deliberately labelled *untrained*, never claimed to be a
team-specific, calibrated forecast. Match identities and dates come solely
from the fixture provider; no fixture or final result is synthesised.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import datetime
from math import isfinite
from statistics import mean

from .daily_rank import RankedFixture
from .domain import Match, utc_datetime
from .model import DCModel, ModelError, fit


def _bounded(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


def cold_start_model(
    fixture: RankedFixture, history: list[Match], *, as_of: datetime,
    xi: float = .0065, trained_model: DCModel | None = None,
) -> tuple[DCModel, dict]:
    """Forecast all source-identified teams; expose when there is no evidence.

    Never use a final score at or after 'as_of'. If Dixon-Coles is fitted,
    preserve that fit for known clubs and use neutral regularized league priors
    for truly new clubs (rho=0 conservatively). Otherwise estimate a shrunk
    league/team goal-rate prior using earlier results. The final fallback when
    no results exist is a public, static assumption, *not a fitted model*.
    """
    cutoff = utc_datetime(as_of)
    rows = sorted((
        m for m in history if m.status == "FINISHED" and m.kickoff < cutoff
        and m.competition == fixture.competition
    ), key=lambda m: (m.kickoff, m.id))
    counts: dict[str, int] = defaultdict(int)
    for game in rows:
        counts[game.home_id] += 1
        counts[game.away_id] += 1
    home_n, away_n = counts[fixture.home_id], counts[fixture.away_id]
    model = trained_model
    if model is None and len(rows) >= 40:
        try:
            model = fit(rows, as_of=cutoff, xi=xi, min_games=40,
                        regularization=.15, maxiter=400)
        except (ModelError, ValueError, OverflowError):
            model = None
    if model is not None:
        if fixture.home_id in model.alpha and fixture.away_id in model.alpha:
            return model, {
                "basis":"RELAXED_DIXON_COLES_FITTED",
                "n_games":len(rows),"home_team_games":home_n,
                "away_team_games":away_n,"uses_generic_assumption":False,
                "explanation":"Modèle Dixon-Coles ajusté, règles d'éligibilité assouplies.",
            }
        # New, untrained club: avoid pretending its strength was estimated.
        alpha=dict(model.alpha)
        beta=dict(model.beta)
        beta_prior=_bounded(mean(model.beta.values()),.40,2.50)
        for team in (fixture.home_id,fixture.away_id):
            alpha.setdefault(team,1.0)
            beta.setdefault(team,beta_prior)
        return replace(model,alpha=alpha,beta=beta,rho=0.0), {
            "basis":"COLD_START_ON_FITTED_LEAGUE",
            "n_games":len(rows),"home_team_games":home_n,
            "away_team_games":away_n,"uses_generic_assumption":True,
            "explanation":"Équipe absente du modèle : force neutre de championnat, rho=0.",
        }

    # Mean goals are shrunk strongly toward an explicitly fixed football prior.
    # As data accumulate, the *same league's past results* dominate.
    n=len(rows)
    rate_h=_bounded((sum(m.home_goals for m in rows)+16*1.45)/(n+16),.55,2.7)
    rate_a=_bounded((sum(m.away_goals for m in rows)+16*1.15)/(n+16),.45,2.5)
    rate=(rate_h+rate_a)/2
    scored: dict[str, int] = defaultdict(int)
    conceded: dict[str, int] = defaultdict(int)
    for m in rows:
        scored[m.home_id] += m.home_goals
        scored[m.away_id] += m.away_goals
        conceded[m.home_id] += m.away_goals
        conceded[m.away_id] += m.home_goals
    attack={}
    defence={}
    for t in (fixture.home_id,fixture.away_id):
        games=counts[t]
        # Eight virtual matches regularize tiny samples to the league average.
        attack[t]=_bounded(
            (scored[t]/max(rate,.25)+8)/(games+8),.65,1.55)
        defence[t]=rate_a*_bounded(
            (conceded[t]/max(rate,.25)+8)/(games+8),.65,1.55)
    if any(not isfinite(v) for v in (*attack.values(),*defence.values())):
        raise ModelError("Paramètres du modèle de secours invalides.")
    first=rows[0].kickoff if rows else cutoff
    last=rows[-1].kickoff if rows else cutoff
    result=DCModel(
        teams=tuple(sorted(attack)),alpha=attack,beta=defence,
        gamma=_bounded(rate_h/rate_a,.80,1.65),rho=0.,xi=xi,
        trained_at=cutoff,first_game=first,last_game=last,
        n_games=n,log_likelihood=0.,
        optimizer_message=("EMPIRICAL_SHRUNK_GOAL_PRIOR" if n else
                           "NO_HISTORY_GENERIC_PRIOR_NOT_TRAINED"),
    )
    basis=("EMPIRICAL_POISSON_PRIOR" if n else
           "GENERIC_POISSON_PRIOR_NO_HISTORY")
    return result, {
        "basis":basis,"n_games":n,"home_team_games":home_n,
        "away_team_games":away_n,"uses_generic_assumption":True,
        "explanation":("Estimation de buts régularisée ; rho=0, "
                       "pas un ajustement Dixon-Coles complet." if n else
                       "Aucun historique : hypothèse générique 1,45/1,15 but, "
                       "pas de force d'équipe entraînée."),
    }
