"""Dixon-Coles (1997): weighted Poisson log-likelihood + four-cell tau correction.

A complete independent mathematical implementation; no imported legacy models.
The attacks are normalized to arithmetic mean 1; beta is *defensive weakness*.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import exp

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln, logsumexp
from scipy.stats import poisson, skellam

from .domain import Match, iso_date, utc_datetime


class ModelError(ValueError):
    pass


@dataclass(frozen=True)
class DCModel:
    teams: tuple[str, ...]
    alpha: dict[str, float]
    beta: dict[str, float]
    gamma: float
    rho: float
    xi: float
    trained_at: datetime
    first_game: datetime
    last_game: datetime
    n_games: int
    log_likelihood: float
    optimizer_message: str

    def expected_goals(self, home_id: str, away_id: str) -> tuple[float,float]:
        if home_id == away_id:
            raise ModelError("Une équipe ne peut pas jouer contre elle-même.")
        if home_id not in self.alpha or away_id not in self.alpha:
            raise ModelError("L'une des équipes est absente de l'historique d'entraînement.")
        lam = self.alpha[home_id] * self.beta[away_id] * self.gamma
        mu = self.alpha[away_id] * self.beta[home_id]
        validate_tau(lam, mu, self.rho)
        return float(lam), float(mu)


def tau(x: int, y: int, lam: float, mu: float, rho: float) -> float:
    if x == 0 and y == 0:
        return 1 - lam * mu * rho
    if x == 0 and y == 1:
        return 1 + lam * rho
    if x == 1 and y == 0:
        return 1 + mu * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def validate_tau(lam: float, mu: float, rho: float) -> None:
    if not (np.isfinite(lam) and np.isfinite(mu) and np.isfinite(rho)) or lam <= 0 or mu <= 0:
        raise ModelError("Intensités de buts non valides.")
    if min(1-lam*mu*rho, 1+lam*rho, 1+mu*rho, 1-rho) <= 0:
        raise ModelError("Paramètre rho hors des bornes admissibles pour cette rencontre.")


def p_score(lam: float, mu: float, rho: float, home: int, away: int) -> float:
    if home < 0 or away < 0:
        return 0.0
    validate_tau(lam, mu, rho)
    return float(poisson.pmf(home, lam) * poisson.pmf(away, mu) * tau(home,away,lam,mu,rho))


def _unpack(theta: np.ndarray, n: int) -> tuple[np.ndarray,np.ndarray,float,float]:
    """Use a safe rho parameter for every possible future matchup among trained teams.

    rho is one common fitted coefficient. Parameterization uses constraints based
    on the maximum expected goals possible among team parameters (not just seen games).
    This makes tau positive for every combination of teams in the trained league.
    """
    a = theta[:n]
    d = theta[n:2*n]
    alpha = np.exp(a - (logsumexp(a) - np.log(n)))
    beta = np.exp(d)
    gamma = float(np.exp(theta[2*n]))
    m = float(np.max(alpha) * np.max(beta))
    max_lam, max_mu = m * gamma, m
    upper = 0.98 * min(1.0, 1.0/(max_lam*max_mu))
    lower_abs = 0.98 / max(max_lam,max_mu)
    rho_raw = float(theta[2*n+1])
    rho = rho_raw * (upper if rho_raw >= 0 else lower_abs)
    return alpha, beta, gamma, rho


def fit(matches: list[Match], *, as_of: datetime, xi: float=0.0065,
        min_games: int=80, regularization: float=0.15, maxiter: int=650) -> DCModel:
    """Fit independent attack, defense, global home advantage, common rho.

    xi is per half-week (3.5 days) as in Dixon-Coles. Never use future results.
    """
    cutoff = utc_datetime(as_of)
    if not (0 <= xi <= 0.3):
        raise ModelError("xi doit être compris entre 0 et 0,3 (par demi-semaine).")
    if not (0 <= regularization <= 10):
        raise ModelError("Régularisation hors limites (0 à 10).")
    rows = sorted((m for m in matches if m.status=='FINISHED' and m.kickoff < cutoff), key=lambda m:m.kickoff)
    if len(rows) < min_games:
        raise ModelError(f"Historique insuffisant : {len(rows)} matchs terminés disponibles (minimum {min_games}).")
    teams = tuple(sorted({t for m in rows for t in (m.home_id,m.away_id)}))
    n = len(teams)
    if n < 4:
        raise ModelError("Au moins quatre équipes distinctes sont nécessaires.")
    # Disconnected sub-leagues cannot be compared on a common strength scale.
    neighbors = {t:set() for t in teams}
    for game in rows:
        neighbors[game.home_id].add(game.away_id)
        neighbors[game.away_id].add(game.home_id)
    visited=set()
    frontier=[teams[0]]
    while frontier:
        team=frontier.pop()
        if team in visited:
            continue
        visited.add(team)
        frontier.extend(neighbors[team] - visited)
    if len(visited)!=len(teams):
        raise ModelError("L'historique contient des groupes d'équipes sans adversaires communs : entraînement non identifiable.")
    idx = {t:i for i,t in enumerate(teams)}
    home_idx = np.asarray([idx[m.home_id] for m in rows],dtype=int)
    away_idx = np.asarray([idx[m.away_id] for m in rows],dtype=int)
    x=np.asarray([m.home_goals for m in rows],dtype=float)
    y=np.asarray([m.away_goals for m in rows],dtype=float)
    ages = np.asarray([(cutoff-m.kickoff).total_seconds()/86400 for m in rows])
    weights = np.exp(-xi * ages/3.5)
    c00=(x==0)&(y==0)
    c01=(x==0)&(y==1)
    c10=(x==1)&(y==0)
    c11=(x==1)&(y==1)
    logs_fact = gammaln(x+1)+gammaln(y+1)

    def objective(par: np.ndarray) -> float:
        alpha,beta,gamma,rho=_unpack(par,n)
        lam=alpha[home_idx]*beta[away_idx]*gamma
        mu=alpha[away_idx]*beta[home_idx]
        cor=np.ones(len(rows), dtype=float)
        cor[c00] = 1 - lam[c00]*mu[c00]*rho
        cor[c01] = 1 + lam[c01]*rho
        cor[c10] = 1 + mu[c10]*rho
        cor[c11] = 1 - rho
        if np.any(cor<=0) or not np.all(np.isfinite(cor)):
            return 1e20
        ll=(-lam-mu + x*np.log(lam) + y*np.log(mu) - logs_fact + np.log(cor))
        # Penalize extreme team strengths, particularly under sparse samples.
        loga=np.log(alpha)
        penalty=regularization*(np.sum(loga**2)+np.sum(np.log(beta)**2))
        return float(-np.dot(weights,ll)+penalty)

    # 2*N log strengths, log gamma and safely parameterized common rho.
    x0=np.zeros(2*n+2)
    mean_home=(x.sum()+0.5)/(len(x)+0.5)
    mean_away=(y.sum()+0.5)/(len(y)+0.5)
    x0[2*n]=np.log(np.clip(mean_home/mean_away,0.75,1.65))
    # Defensive weaknesses can absorb baseline scoring rate.
    x0[n:2*n]=np.log(np.clip(mean_away,0.4,2.4))
    bounds = [(-1.6,1.6)]*n + [(-1.6,1.6)]*n + [(-0.5,0.7),(-0.98,0.98)]
    res=minimize(objective,x0,method="L-BFGS-B",bounds=bounds,
                 options={"maxiter":maxiter,"ftol":1e-10,"gtol":1e-5,"maxls":35})
    if not res.success:
        # A second deterministic start is useful for difficult, sparse samples.
        retry=minimize(objective,res.x,method="L-BFGS-B",bounds=bounds,
                       options={"maxiter":maxiter,"ftol":1e-9,"gtol":2e-5,"maxls":50})
        if retry.success or retry.fun < res.fun:
            res=retry
    if not res.success or not np.isfinite(res.fun):
        raise ModelError(f"L'optimisation n'a pas convergé : {res.message}")
    alpha,beta,gamma,rho=_unpack(res.x,n)
    # The reported likelihood is unpenalized, but uses learned time decay.
    ll = float(-res.fun + regularization*(np.sum(np.log(alpha)**2)+np.sum(np.log(beta)**2)))
    return DCModel(teams=teams, alpha=dict(zip(teams,map(float,alpha))),
                   beta=dict(zip(teams,map(float,beta))), gamma=float(gamma), rho=float(rho),
                   xi=float(xi),trained_at=cutoff,first_game=rows[0].kickoff,
                   last_game=rows[-1].kickoff,n_games=len(rows),log_likelihood=ll,
                   optimizer_message=str(res.message))


def one_x_two(lam: float, mu: float, rho: float) -> dict[str,float]:
    """Exact 1X2 probabilities via Skellam distribution with four DC adjustments."""
    validate_tau(lam,mu,rho)
    base = exp(-lam-mu)
    delta_00 = base * (-lam*mu*rho)
    delta_11 = base * (lam*mu) * (-rho)
    delta_10 = base * lam * (mu*rho)
    delta_01 = base * mu * (lam*rho)
    p1=float(skellam.sf(0,lam,mu)+delta_10)
    px=float(skellam.pmf(0,lam,mu)+delta_00+delta_11)
    p2=float(skellam.cdf(-1,lam,mu)+delta_01)
    return {"home":p1,"draw":px,"away":p2}


def forecast(model: DCModel, home_id: str, away_id: str, *, top_n: int=5) -> dict:
    lam,mu=model.expected_goals(home_id,away_id)
    cap=8
    while cap<30 and float(poisson.cdf(cap,lam)*poisson.cdf(cap,mu))<0.9999999:
        cap+=2
    p_home=poisson.pmf(np.arange(cap+1),lam)
    p_away=poisson.pmf(np.arange(cap+1),mu)
    matrix=np.outer(p_home,p_away)
    for x,y in ((0,0),(0,1),(1,0),(1,1)):
        matrix[x,y]*=tau(x,y,lam,mu,model.rho)
    if np.any(matrix<0):
        raise ModelError("Distribution incorrecte (probabilités négatives).")
    probs=[{"home":i,"away":j,"score":f"{i}-{j}","probability":float(matrix[i,j])}
           for i in range(cap+1) for j in range(cap+1)]
    probs.sort(key=lambda r:(-r["probability"],r["home"],r["away"]))
    p1x2=one_x_two(lam,mu,model.rho)
    return {
        "expected_home_goals":lam, "expected_away_goals":mu,
        "home_attack":model.alpha[home_id],"home_defensive_weakness":model.beta[home_id],
        "away_attack":model.alpha[away_id],"away_defensive_weakness":model.beta[away_id],
        "home_advantage":model.gamma,"rho":model.rho,"xi_per_half_week":model.xi,
        "top_scores":probs[:top_n],"one_x_two":p1x2,
        "matrix_0_6":[[float(matrix[i,j]) for j in range(min(cap,6)+1)] for i in range(min(cap,6)+1)],
        "matrix_orientation":"lignes=buts domicile,colonnes=buts extérieur",
        "probability_covered":float(matrix.sum()),"probability_uncovered":max(0.,1-float(matrix.sum())),
        "computed_goal_limit":cap,
        "training":{"matches":model.n_games,"teams":len(model.teams),
                    "first_game":iso_date(model.first_game),"last_game":iso_date(model.last_game),
                    "cutoff":iso_date(model.trained_at),"weighted_log_likelihood":model.log_likelihood,
                    "optimizer":model.optimizer_message},
        "interpretation":"Un score le plus probable n'est pas une certitude. Toutes les probabilités sont des estimations de modèle."
    }
