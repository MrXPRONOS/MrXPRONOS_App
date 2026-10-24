#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mr XPRONOS - experimental football-only ML V2 exact-score benchmark.

8 approaches:
  poisson, dixon_coles, bivariate_poisson, xg_poisson,
  bayesian_gamma, machine_learning, monte_carlo, market_adjusted.
Chronology: predictions for a UTC day use completed games from earlier days ONLY.
No final-score-derived feature, xG of the target match, or unverified post-kickoff
odds is ever passed as an input to a prediction.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, date
from itertools import groupby
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import gammaln
from scipy.stats import poisson
from sklearn.ensemble import HistGradientBoostingRegressor

MAX_GOALS = 10
GOALS = np.arange(MAX_GOALS + 1)
MODELS = ("poisson", "dixon_coles", "bivariate_poisson", "xg_poisson",
          "bayesian_gamma", "machine_learning", "monte_carlo", "market_adjusted")
SEED = 20261020


def number(value):
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError, OverflowError):
        return None


def utc_day(value):
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)) or str(value).strip().isdigit():
            v = float(value)
            if v > 1e11:
                v /= 1000.0
            return datetime.fromtimestamp(v, timezone.utc).date()
        value = str(value).strip()
        if len(value) == 10:
            return date.fromisoformat(value)
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).date()
    except (ValueError, TypeError, OverflowError):
        return None


def utc_instant(value):
    """UTC datetime; date-only strings cannot certify same-day pre-kickoff odds."""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)) or str(value).strip().isdigit():
            x = float(value)
            if x > 1e11:
                x /= 1000.0
            return datetime.fromtimestamp(x, timezone.utc)
        string = str(value).strip()
        if len(string) == 10:
            return datetime.fromisoformat(string).replace(tzinfo=timezone.utc)
        result = datetime.fromisoformat(string.replace("Z", "+00:00"))
        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)
        return result.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def normalize_odds(raw):
    """Only certified pre-kickoff odds are eligible; absent timestamp => skip."""
    value = raw.get("prematch_odds") or raw.get("odds") or raw.get("odds_1x2")
    if not isinstance(value, dict):
        return None
    stamp = (raw.get("odds_timestamp") or raw.get("odds_updated_at")
             or value.get("timestamp") or value.get("updated_at"))
    kickoff = utc_instant(raw.get("start_time") or raw.get("event_date") or raw.get("startTime"))
    quoted_at = utc_instant(stamp)
    # Reject at- or post-kickoff prices. Date-only quotes require a prior day.
    if kickoff is None or quoted_at is None or quoted_at >= kickoff:
        return None
    pair = value.get("1x2") or value.get("match_winner") or value
    if isinstance(pair, dict):
        home = number(pair.get("home") or pair.get("1"))
        draw = number(pair.get("draw") or pair.get("X"))
        away = number(pair.get("away") or pair.get("2"))
    else:
        return None
    exact = value.get("correct_score") or value.get("correct_scores") or {}
    exact = {str(k).replace("-", ":"): float(v) for k, v in exact.items()
             if number(v) is not None and number(v) > 1.0} if isinstance(exact, dict) else {}
    valid_1x2 = all(v is not None and v > 1.0 for v in (home, draw, away))
    if not valid_1x2 and not exact:
        return None
    return {"1x2": [home, draw, away] if valid_1x2 else None, "exact": exact}


@dataclass(frozen=True)
class Match:
    key: str
    day: date
    league: str
    home: str
    away: str
    hg: int
    ag: int
    xgh: float | None = None
    xga: float | None = None
    odds: dict | None = None


def load_matches(path: str, end: date):
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    entries = doc if isinstance(doc, list) else doc.get("games", doc.get("matches", []))
    if not isinstance(entries, list):
        raise ValueError("Expected a list of matches in source JSON")
    by_key = {}
    errors = Counter()
    xg_found = 0
    odds_found = 0
    for raw in entries:
        if not isinstance(raw, dict):
            errors["non_object"] += 1
            continue
        # The football-named allscores endpoint also serves other sports.
        # Unknown sport IDs are NOT inferred from league names or goal-shaped scores.
        sport = raw.get("sportId", raw.get("sport_id"))
        if str(sport) != "1":
            errors["non_football_or_uncertified_sport"] += 1
            continue
        day = utc_day(raw.get("start_time") or raw.get("event_date") or raw.get("startTime") or raw.get("date"))
        if not day or day > end:
            errors["invalid_or_future_date"] += 1
            continue
        home_obj = raw.get("homeCompetitor") or {}
        away_obj = raw.get("awayCompetitor") or {}
        home = (raw.get("home_team") or home_obj.get("name") or "").strip()
        away = (raw.get("away_team") or away_obj.get("name") or "").strip()
        league = (raw.get("competition") or raw.get("league")
                  or raw.get("competitionDisplayName") or "").strip()
        h = raw.get("home_score", home_obj.get("score"))
        a = raw.get("away_score", away_obj.get("score"))
        hv, av = number(h), number(a)
        ended = (raw.get("is_finished") is True or str(raw.get("status_group", raw.get("statusGroup"))) == "4"
                 or str(raw.get("status", "")).lower() in ("ended", "finished", "ft"))
        if not ended or not home or not away or not league or hv is None or av is None:
            errors["unfinished_or_missing"] += 1
            continue
        if (int(hv) != hv or int(av) != av or min(hv, av) < 0
                or max(hv, av) > MAX_GOALS):
            errors["out_of_goal_range"] += 1
            continue
        xg = raw.get("xg") or raw.get("expected_goals") or {}
        if not isinstance(xg, dict):
            xg = {}
        xgh = number(raw.get("home_xg", xg.get("home")))
        xga = number(raw.get("away_xg", xg.get("away")))
        if xgh is not None and xga is not None and min(xgh, xga) >= 0:
            xg_found += 1
        else:
            xgh = xga = None
        odds = normalize_odds(raw)
        if odds:
            odds_found += 1
        key = str(raw.get("id") or raw.get("game_id") or (str(day) + ":" + league + ":" + home + ":" + away))
        candidate = Match(key, day, league, home, away, int(hv), int(av), xgh, xga, odds)
        if key in by_key:
            previous = by_key[key]
            if (previous.day, previous.league, previous.home, previous.away,
                    previous.hg, previous.ag) != (candidate.day, candidate.league,
                    candidate.home, candidate.away, candidate.hg, candidate.ag):
                raise ValueError("Conflicting match ID in certified football source: " + key)
            errors["identical_duplicate"] += 1
            continue
        by_key[key] = candidate
    matches = sorted(by_key.values(), key=lambda m: (m.day, m.key))
    print("SOURCE_AUDIT", json.dumps({
        "raw_rows": len(entries), "valid_unique_matches": len(matches),
        "earliest": str(matches[0].day) if matches else None,
        "latest": str(matches[-1].day) if matches else None,
        "xg_rows_seen": xg_found, "verified_prematch_odds_rows_seen": odds_found,
        "skips": dict(errors)}, ensure_ascii=False), flush=True)
    return matches


class Decayed:
    """Exponentially discounted sufficient statistics; only updated after the match."""
    __slots__ = ("last", "values")
    def __init__(self):
        self.last = None
        self.values = np.zeros(6)  # matches, goals for/against, xG for/against, xG sample count

    def at(self, d):
        if self.last is None:
            return self.values.copy()
        days = max(0, (d - self.last).days)
        return self.values * (2.0 ** (-days / 240.0))

    def add(self, d, scored, conceded, xgf=None, xga=None):
        arr = self.at(d)
        arr[:3] += (1, scored, conceded)
        if xgf is not None and xga is not None:
            arr[3:6] += (xgf, xga, 1)
        self.values = arr
        self.last = d


class FormState:
    def __init__(self):
        self.league_h = defaultdict(Decayed)
        self.league_a = defaultdict(Decayed)
        self.home = defaultdict(Decayed)
        self.away = defaultdict(Decayed)

    def features(self, m):
        lh = self.league_h[m.league].at(m.day)
        la = self.league_a[m.league].at(m.day)
        hs = self.home[(m.league, m.home)].at(m.day)
        as_ = self.away[(m.league, m.away)].at(m.day)
        # League-level shrinkage prevents unstable estimates in low-volume leagues.
        mu_h = (lh[1] + 35 * 1.42) / (lh[0] + 35)
        mu_a = (la[1] + 35 * 1.14) / (la[0] + 35)
        k = 8.0
        for_h = (hs[1] + k * mu_h) / (hs[0] + k)
        against_a = (as_[2] + k * mu_h) / (as_[0] + k)
        for_a = (as_[1] + k * mu_a) / (as_[0] + k)
        against_h = (hs[2] + k * mu_a) / (hs[0] + k)
        lam_h = float(np.clip(for_h * against_a / mu_h, .12, 4.5))
        lam_a = float(np.clip(for_a * against_h / mu_a, .12, 4.5))
        # League-level xG estimates from previous games ONLY; a sparse team's
        # shots are partially pooled with its league. Never use an invented
        # xG field when there are fewer than six recorded xG matches in league.
        xg_lamh = xg_lama = None
        if min(lh[5], la[5]) >= 6:
            lgx_h = (lh[3] + 8.0 * mu_h) / (lh[5] + 8.0)
            lgx_a = (la[3] + 8.0 * mu_a) / (la[5] + 8.0)
            xgf_h = (hs[3] + 5.0*lgx_h) / (hs[5] + 5.0)
            xga_a = (as_[4] + 5.0*lgx_h) / (as_[5] + 5.0)
            xgf_a = (as_[3] + 5.0*lgx_a) / (as_[5] + 5.0)
            xga_h = (hs[4] + 5.0*lgx_a) / (hs[5] + 5.0)
            xg_lamh = float(np.clip(.55*lam_h + .45*xgf_h*xga_a/max(.2,lgx_h), .12, 4.5))
            xg_lama = float(np.clip(.55*lam_a + .45*xgf_a*xga_h/max(.2,lgx_a), .12, 4.5))
        vector = np.array([lam_h, lam_a, mu_h, mu_a, hs[0], as_[0], lh[0],
                           for_h, against_h, for_a, against_a,
                           (hs[1]-hs[2])/(hs[0]+3),
                           (as_[1]-as_[2])/(as_[0]+3)], dtype=float)
        return {"h": lam_h, "a": lam_a, "mu_h": mu_h, "mu_a": mu_a,
                "hs": hs, "as": as_, "xgh": xg_lamh, "xga": xg_lama,
                "vector": vector}

    def add(self, m):
        self.league_h[m.league].add(m.day, m.hg, m.ag, m.xgh, m.xga)
        self.league_a[m.league].add(m.day, m.ag, m.hg, m.xga, m.xgh)
        self.home[(m.league, m.home)].add(m.day, m.hg, m.ag, m.xgh, m.xga)
        self.away[(m.league, m.away)].add(m.day, m.ag, m.hg, m.xga, m.xgh)


def normalized(p):
    p = np.nan_to_num(np.asarray(p, dtype=float), nan=0, posinf=0, neginf=0)
    p = np.maximum(0, p)
    total = p.sum()
    if total <= 0:
        raise ValueError("Invalid empty probability distribution")
    return p / total


def poisson_grid(lh, la):
    return normalized(np.outer(poisson.pmf(GOALS, lh), poisson.pmf(GOALS, la)))


def dixon_coles(lh, la, rho):
    p = poisson_grid(lh, la)
    p[0, 0] *= max(.001, 1 - lh * la * rho)
    p[0, 1] *= max(.001, 1 + lh * rho)
    p[1, 0] *= max(.001, 1 + la * rho)
    p[1, 1] *= max(.001, 1 - rho)
    return normalized(p)


def estimate_dc_rho(recent):
    low = [(h, a, gh, ga) for h, a, gh, ga in recent if gh <= 1 and ga <= 1]
    if len(low) < 80:
        return -.04  # pre-specified fallback, never fitted on evaluation outcomes
    def loss(r):
        vals = []
        for h, a, gh, ga in low:
            tau = ((1-h*a*r) if gh == 0 and ga == 0 else
                   (1+h*r) if gh == 0 else (1+a*r) if ga == 0 else (1-r))
            vals.append(-math.log(max(.001, tau)))
        return sum(vals) + 2*r*r  # weak regularization
    return float(minimize_scalar(loss, bounds=(-.15, .15), method="bounded").x)


def bivariate_grid(lh, la, shared):
    shared = max(0.0, min(shared, .45 * min(lh, la)))
    aa, bb = max(.001, lh-shared), max(.001, la-shared)
    p = np.zeros((MAX_GOALS+1, MAX_GOALS+1), dtype=float)
    for i in range(MAX_GOALS+1):
        for j in range(MAX_GOALS+1):
            terms = [((i-k)*math.log(aa)-gammaln(i-k+1)
                      +(j-k)*math.log(bb)-gammaln(j-k+1)
                      +(k*math.log(shared)-gammaln(k+1) if shared > 0 else 0))
                     for k in range(min(i, j)+1) if shared > 0 or k == 0]
            p[i, j] = math.exp(-(aa+bb+shared)) * sum(math.exp(t) for t in terms)
    return normalized(p)


def estimate_shared(observations):
    """Maximum likelihood fit of the bivariate common Poisson factor on PRIOR forecasts.
    Returns a shared-goal fraction (0-0.45). Zero is a legitimate fitted result.
    """
    if len(observations) < 120:
        return 0.0
    recent = np.asarray(observations[-6500:], dtype=float)
    lh, la, gh0, ga0 = [recent[:, i] for i in range(4)]
    gh, ga = gh0.astype(int), ga0.astype(int)
    min_goals = np.minimum(gh, ga)
    max_k = int(min(MAX_GOALS, min_goals.max()))
    def negative_ll(fraction):
        shared = np.minimum(lh, la) * fraction
        x, y = np.maximum(.001, lh-shared), np.maximum(.001, la-shared)
        log_terms = np.full(len(lh), -np.inf)
        for k in range(max_k+1):
            mask = min_goals >= k
            if not np.any(mask):
                continue
            u, v = gh[mask]-k, ga[mask]-k
            v_log = u*np.log(x[mask]) - gammaln(u+1) + v*np.log(y[mask]) - gammaln(v+1)
            if k:
                v_log += k*np.log(np.maximum(shared[mask], 1e-15))-gammaln(k+1)
            log_terms[mask] = np.logaddexp(log_terms[mask], v_log)
        return -float(np.sum(-x-y-shared+log_terms)) + 15*fraction*fraction
    opt = minimize_scalar(negative_ll, bounds=(.000001, .45),
                          method="bounded", options={"xatol": .001})
    return float(opt.x) if opt.success and opt.fun < negative_ll(0) else 0.0


def league_shared_covariance(residuals, global_shared):
    """Partial pooling allows positive correlation in leagues with support."""
    if len(residuals) < 60:
        return global_shared
    r = np.asarray(residuals[-650:], dtype=float)
    cov = float(np.mean(r[:,0]*r[:,1]) - r[:,0].mean()*r[:,1].mean())
    weight = len(r)/(len(r)+180)
    return float(np.clip(.65*global_shared + .35*max(0, cov)*weight, 0, .45))


def bayesian_grid(f, seed):
    """Gamma priors on home/away scoring and conceding intensities.
    Integrating 128 posterior simulations approximates posterior predictive p(score)."""
    rng = np.random.default_rng(seed)
    h, a = f["hs"], f["as"]
    mh, ma = f["mu_h"], f["mu_a"]
    k = 8
    sh = rng.gamma(shape=max(.01, k*mh+h[1]), scale=1/(k+h[0]), size=128)
    dh = rng.gamma(shape=max(.01, k*mh+a[2]), scale=1/(k+a[0]), size=128)
    sa = rng.gamma(shape=max(.01, k*ma+a[1]), scale=1/(k+a[0]), size=128)
    da = rng.gamma(shape=max(.01, k*ma+h[2]), scale=1/(k+h[0]), size=128)
    lh = np.clip(sh*dh/mh, .12, 5.)
    la = np.clip(sa*da/ma, .12, 5.)
    ph = poisson.pmf(GOALS[None, :], lh[:, None])
    pa = poisson.pmf(GOALS[None, :], la[:, None])
    return normalized(np.einsum("ni,nj->ij", ph, pa) / len(lh))


def monte_carlo_grid(lh, la, seed, n=4000):
    """A stochastic match-tempo model, NOT an independent learned estimator."""
    rng = np.random.default_rng(seed)
    tempo = rng.gamma(shape=12.0, scale=1/12.0, size=n)
    h = rng.poisson(lh*tempo)
    a = rng.poisson(la*tempo)
    mask = (h <= MAX_GOALS) & (a <= MAX_GOALS)
    result = np.zeros((MAX_GOALS+1, MAX_GOALS+1))
    np.add.at(result, (h[mask], a[mask]), 1)
    return normalized(result)


def market_grid(baseline, odds):
    if not odds:
        return None
    exact = odds.get("exact") or {}
    if len(exact) >= 12:
        p = np.zeros_like(baseline)
        for key, value in exact.items():
            try:
                h, a = map(int, key.split(":"))
                if 0 <= h <= MAX_GOALS and 0 <= a <= MAX_GOALS:
                    p[h, a] = 1 / float(value)
            except (ValueError, ZeroDivisionError):
                continue
        if p.sum() > 0 and np.count_nonzero(p) >= 12:
            # Missing quoted scores: do not claim complete direct market model.
            coverage = np.count_nonzero(p)
            if coverage >= (MAX_GOALS+1)**2:
                return normalized(p)
    one = odds.get("1x2")
    if not one:
        return None
    target = normalized([1/x for x in one])
    h, a = np.indices(baseline.shape)
    masks = [h>a, h==a, h<a]
    p = baseline.copy()
    for category, mask in enumerate(masks):
        mass = p[mask].sum()
        if mass:
            p[mask] *= target[category]/mass
    return normalized(p)


def train_ml(records):
    if len(records) < 350:
        return None
    # All features are snapshotted before the target matches. Labels only after final.
    data = records[-65000:]
    X = np.array([r[0] for r in data], dtype=float)
    yh = np.array([r[1] for r in data], dtype=float)
    ya = np.array([r[2] for r in data], dtype=float)
    trained = []
    for y in (yh, ya):
        model = HistGradientBoostingRegressor(loss="poisson", learning_rate=.055,
                                              max_iter=95, max_leaf_nodes=18,
                                              l2_regularization=5, random_state=SEED)
        model.fit(X, y)
        trained.append(model)
    return trained


def score_odds_for(m, gh, ga):
    if not m.odds or not m.odds.get("exact"):
        return None
    return number(m.odds["exact"].get(f"{gh}:{ga}"))


def summarize(stats):
    result = {}
    for name in MODELS:
        entries = stats[name]
        if not entries:
            result[name] = {"status": "NOT_EVALUABLE", "n": 0, "reason":
                            "Required historical observations or verified pre-match inputs unavailable"}
            continue
        n = len(entries)
        hit = sum(x["hit"] for x in entries)
        avg_loss = sum(x["log_loss"] for x in entries)/n
        mean_prob = sum(x["top_probability"] for x in entries)/n
        roi = [x["roi"] for x in entries if x["roi"] is not None]
        result[name] = {
            "status": "EVALUATED", "n": n, "exact_hits": hit,
            "exact_hit_rate_pct": round(100*hit/n, 3),
            "mean_top_score_confidence_pct": round(100*mean_prob, 3),
            "log_loss": round(avg_loss, 5),
            "top3_hit_rate_pct": round(100*sum(x["top3_hit"] for x in entries)/n, 3),
            "mean_brier_top_score": round(sum((x["hit"]-x["top_probability"])**2 for x in entries)/n, 6),
            "calibration_gap_pct_points": round(100*abs(mean_prob-hit/n), 3),
            "quoted_odds_n": len(roi),
            "flat_stake_roi_pct": round(100*sum(roi)/len(roi), 3) if roi else None,
        }
    return result


def backtest(matches, begin, end, out, max_eval=0):
    states = FormState()
    training = []
    recent_low = []
    recent_residuals = []
    league_residuals = defaultdict(list)
    results = defaultdict(list)
    audit = Counter()
    detail = []
    dc_rho = -.04
    shared = .10
    ml = None
    last_retrain = None
    played = 0
    first_evaluated = None
    last_evaluated = None
    for day, grouped in groupby(matches, lambda m: m.day):
        daily = list(grouped)
        if day > end:
            break
        evaluating = begin <= day <= end
        if evaluating and (last_retrain is None or last_retrain != (day.year, day.month)):
            ml = train_ml(training)
            dc_rho = estimate_dc_rho(recent_low[-9000:])
            shared = estimate_shared(recent_low)
            last_retrain = (day.year, day.month)
            print("RETRAIN", day, "train_rows", len(training),
                  "rho", round(dc_rho, 4), "shared", round(shared, 4),
                  "ml", ml is not None, flush=True)
        # FIRST calculate ALL forecasts for the date, THEN add their results to history.
        pending = []
        for m in daily:
            f = states.features(m)
            pending.append((m, f))
            if not evaluating or (max_eval and played >= max_eval):
                continue
            played += 1
            if first_evaluated is None:
                first_evaluated = day
            last_evaluated = day
            audit["evaluated_matches"] += 1
            if m.xgh is not None and m.xga is not None:
                audit["targets_having_postmatch_xg_ignored"] += 1
            seed = (SEED + sum(ord(c) for c in m.key) * 8191) % (2**32)
            p0 = poisson_grid(f["h"], f["a"])
            forecasts = {
                "poisson": p0,
                "dixon_coles": dixon_coles(f["h"], f["a"], dc_rho),
                "bivariate_poisson": bivariate_grid(f["h"], f["a"], league_shared_covariance(league_residuals[m.league], shared*min(f["h"], f["a"]))),
                "bayesian_gamma": bayesian_grid(f, seed),
                "monte_carlo": monte_carlo_grid(f["h"], f["a"], seed+1),
            }
            if f["xgh"] is not None and f["xga"] is not None:
                forecasts["xg_poisson"] = poisson_grid(f["xgh"], f["xga"])
            else:
                audit["xg_model_missing_prior_xg"] += 1
            if ml is not None:
                lh = float(np.clip(ml[0].predict(f["vector"][None, :])[0], .12, 5))
                la = float(np.clip(ml[1].predict(f["vector"][None, :])[0], .12, 5))
                forecasts["machine_learning"] = poisson_grid(lh, la)
            else:
                audit["ml_not_enough_training"] += 1
            market = market_grid(p0, m.odds)
            if market is not None:
                forecasts["market_adjusted"] = market
            else:
                audit["market_model_missing_verified_odds"] += 1
            for name, grid in forecasts.items():
                i, j = np.unravel_index(grid.argmax(), grid.shape)
                prob = float(grid[m.hg, m.ag])
                quoted = score_odds_for(m, i, j)
                top3 = np.argpartition(grid.ravel(), -3)[-3:]
                top3_hit = int(m.hg*(MAX_GOALS+1) + m.ag in top3)
                row = {
                    "top3_hit": top3_hit, "model": name, "date": str(m.day), "id": m.key, "league": m.league,
                    "home": m.home, "away": m.away, "actual_score": f"{m.hg}:{m.ag}",
                    "predicted_score": f"{i}:{j}", "top_probability": float(grid[i, j]),
                    "actual_probability": prob, "hit": int(i == m.hg and j == m.ag),
                    "log_loss": -math.log(max(prob, 1e-15)),
                    "quoted_odds": quoted, "roi": (quoted if i==m.hg and j==m.ag else 0)-1
                    if quoted is not None else None,
                }
                results[name].append(row)
                detail.append({k: (round(v, 7) if isinstance(v, float) else v)
                               for k, v in row.items() if k not in ("roi",)})
        # A day's final scores become visible no earlier than the following day.
        for m, f in pending:
            recent_low.append((f["h"], f["a"], m.hg, m.ag))
            recent_residuals.append((m.hg-f["h"], m.ag-f["a"]))
            league_residuals[m.league].append((m.hg-f["h"], m.ag-f["a"]))
            training.append((f["vector"], m.hg, m.ag))
            states.add(m)
        if evaluating and (day.day == 1 or day == end):
            print("PROGRESS", day, "scored", played, flush=True)
    summary = summarize(results)
    paired_cohorts = {}
    for conditional_model in ("xg_poisson", "market_adjusted"):
        eligible = {(r["date"], r["id"]) for r in results[conditional_model]}
        if not eligible:
            paired_cohorts[conditional_model] = {"matched_games": 0}
            continue
        matched = defaultdict(list)
        for model_name, entries in results.items():
            matched[model_name] = [r for r in entries if (r["date"],r["id"]) in eligible]
        paired_cohorts[conditional_model] = {
            "matched_games": len(eligible),
            "comparisons": summarize(matched)
        }
    os.makedirs(out, exist_ok=True)
    report = {
        "source": "strict sportId=1 archive",
        "period_start": str(begin), "period_end": str(end),
        "first_actual_match_date": str(first_evaluated) if first_evaluated else None,
        "last_actual_match_date": str(last_evaluated) if last_evaluated else None,
        "no_leakage_policy": "Strictly previous UTC calendar dates for ALL models",
        "n_evaluation_matches": audit["evaluated_matches"],
        "skips": dict(audit),
        "results": summary,
        "method_notes": {
            "poisson": "Independently distributed scored goals, smoothed home/away attack and defense",
            "dixon_coles": "Four-cell low-score correction, rho refitted only on prior outcomes monthly",
            "bivariate_poisson": "Common latent Poisson intensity estimated from prior goal residuals",
            "xg_poisson": "Uses past-match genuine xG only; disabled if the source lacks xG",
            "bayesian_gamma": "Gamma strength priors with posterior predictive Monte Carlo integration",
            "machine_learning": "Chronologically refitted Poisson-gradient-boosting for home/away goals",
            "monte_carlo": "4,000 simulations with shared Gamma tempo; stochastic scenario technique",
            "market_adjusted": "Only verified timestamped PREMATCH market quotes; incomplete score odds are not treated as a full market distribution",
        },
        "warning": "Backtested probabilities are not guarantees. Models have different coverage when external inputs are missing.",
    }
    monthly = defaultdict(list)
    leagues = defaultdict(list)
    reliability = defaultdict(list)
    for model_name, entries in results.items():
        for entry in entries:
            monthly[(model_name, entry["date"][:7])].append(entry)
            leagues[(model_name, entry["league"])].append(entry)
            bin_id = min(9, int(entry["top_probability"] * 10))
            reliability[(model_name, bin_id)].append(entry)

    def grouped_report(filename, groups, minimum, label):
        with (Path(out) / filename).open("w", newline="", encoding="utf8") as fh:
            wr = csv.writer(fh)
            wr.writerow(["model", label, "matches", "exact_hits", "hit_rate_pct",
                         "log_loss", "mean_confidence_pct", "top3_hit_rate_pct"])
            for (model_name, key), entries in sorted(groups.items()):
                n = len(entries)
                if n < minimum:
                    continue
                hits = sum(e["hit"] for e in entries)
                wr.writerow([model_name, key, n, hits, round(100*hits/n, 4),
                             round(sum(e["log_loss"] for e in entries)/n, 5),
                             round(100*sum(e["top_probability"] for e in entries)/n, 4),
                             round(100*sum(e["top3_hit"] for e in entries)/n, 4)])

    grouped_report("monthly.csv", monthly, 1, "month")
    grouped_report("leagues.csv", leagues, 100, "league")
    grouped_report("calibration.csv", reliability, 20, "probability_bin")
    report["matched_cohort_comparisons"] = paired_cohorts
    report["files"] = ["summary.json", "all_predictions.csv", "monthly.csv",
                       "leagues.csv", "calibration.csv"]
    report["bivariate_fitted_global_common_fraction"] = round(shared, 6)
    with open(Path(out)/"summary.json", "w", encoding="utf8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    with open(Path(out)/"all_predictions.csv", "w", newline="", encoding="utf8") as fh:
        if detail:
            wr = csv.DictWriter(fh, fieldnames=list(detail[0]))
            wr.writeheader()
            wr.writerows(detail)
        else:
            fh.write("no_predictions\n")
    print("FINAL_BACKTEST_RESULTS", json.dumps(report, ensure_ascii=False), flush=True)
    return summary


def self_test():
    a = poisson_grid(1.7, 1.1)
    assert np.isclose(a.sum(), 1.0)
    assert np.isclose(dixon_coles(1.7,1.1,-.06).sum(),1.0)
    assert np.isclose(bivariate_grid(1.7,1.1,.12).sum(),1.0)
    assert np.max(np.abs(bivariate_grid(1.7,1.1,.12)-poisson_grid(1.7,1.1))) > .001
    assert np.isclose(monte_carlo_grid(1.7,1.1,1234).sum(),1.0)
    f = {"hs": np.array([15, 24, 13, 0, 0, 0]), "as": np.array([12, 12, 16, 0, 0, 0]),
         "mu_h": 1.4, "mu_a": 1.1}
    assert np.isclose(bayesian_grid(f,12).sum(),1.)
    assert normalize_odds({"start_time":"2026-05-02T19:00:00Z",
                           "odds_timestamp":"2026-05-03T00:00:00Z",
                           "odds":{"1x2":{"1":2,"X":3,"2":4}}}) is None
    assert normalize_odds({"start_time":"2026-05-02T19:00:00Z",
                           "odds_timestamp":"2026-05-01T19:00:00Z",
                           "odds":{"1x2":{"1":2,"X":3,"2":4}}}) is not None
    assert normalize_odds({"start_time":"2026-05-02T19:00:00Z",
                           "odds_timestamp":"2026-05-02T18:00:00Z",
                           "odds":{"1x2":{"1":2,"X":3,"2":4}}}) is not None
    print("SELF_TEST_OK", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="research/private/football_history.json")
    ap.add_argument("--start", default="2026-01-01")
    ap.add_argument("--end", default="2026-10-19")
    ap.add_argument("--out", default="research/results/single_ml_v2")
    ap.add_argument("--max-eval", type=int, default=0)
    ap.add_argument("--self-test-only", action="store_true")
    args = ap.parse_args()
    self_test()
    if args.self_test_only:
        return
    begin, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    if end >= datetime.now(timezone.utc).date():
        raise ValueError("Backtest end must be earlier than current UTC date")
    matches = load_matches(args.source, end)
    if not matches:
        raise ValueError("No sportId=1 completed football matches; rebuild certified research history")
    backtest(matches, begin, end, args.out, max_eval=args.max_eval)


if __name__ == "__main__":
    main()
