"""BSD V2 : moteur indépendant centré sur les buts et résultats.

Implémentation point-in-time : chaque match historique devient utilisable
SEULEMENT 4 h après son coup d'envoi. Pas de corners, tirs ou fautes.
Poisson indépendant et correction Dixon-Coles comparables.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from math import exp, factorial, log, isfinite
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

from bsd_h2h import _team_id, _utc, _valid_score
from bsd_markets import Candidate, MarketCalibrator, candidates_from_goals, realized

SETTLEMENT_DELAY = 4 * 3600
HALF_LIFE_DAYS = 120
MIN_TEAM_GAMES = 5
MIN_PROBABILITY = .70


def league_key(item: Dict[str, Any]) -> str:
    key = item.get("league_id")
    if key is None and isinstance(item.get("league"), dict):
        key = item["league"].get("id")
    if key is not None:
        return "id:" + str(key)
    name = item.get("league_name") or item.get("league")
    if isinstance(name, str) and name.strip():
        return "name:" + name.strip().casefold()
    return ""


def outcome_scores(item):
    h, a = _valid_score(item.get("home_score")), _valid_score(item.get("away_score"))
    if h is None or a is None or str(item.get("status") or "").lower() != "finished":
        return None
    return h, a


def fixture_datetime(item):
    return _utc(str(item.get("event_date") or ""))


class V2History:
    def __init__(self, events: List[dict]):
        self.teams = defaultdict(list)
        self.leagues = defaultdict(list)
        self.global_games = []
        seen = set()
        for e in events:
            if not isinstance(e, dict) or e.get("id") is None or str(e["id"]) in seen:
                continue
            h, a = _team_id(e, "home"), _team_id(e, "away")
            if h is None or a is None or h <= 0 or a <= 0 or h == a or outcome_scores(e) is None:
                continue
            try:
                finished = fixture_datetime(e).timestamp() + SETTLEMENT_DELAY
            except (ValueError, TypeError, OverflowError):
                continue
            seen.add(str(e["id"]))
            self.teams[h].append((finished, e))
            self.teams[a].append((finished, e))
            k = league_key(e)
            if k:
                self.leagues[k].append((finished, e))
            self.global_games.append((finished, e))
        for obj in (self.teams, self.leagues):
            for v in obj.values():
                v.sort(key=lambda x: x[0])
        self.global_games.sort(key=lambda x: x[0])
        self.team_times = {k: [v[0] for v in items] for k, items in self.teams.items()}
        self.league_times = {k: [v[0] for v in items] for k, items in self.leagues.items()}
        self.global_times = [v[0] for v in self.global_games]

    @staticmethod
    def _past(items, times, when, limit):
        i = bisect_right(times, when.timestamp())
        return [v[1] for v in items[max(0, i-limit):i]][::-1]

    def team(self, team_id, at: datetime, limit=12, venue=None):
        rows = self.teams.get(team_id, [])
        result = self._past(rows, self.team_times.get(team_id, []), at, 80 if venue else limit)
        if venue:
            result = [m for m in result if _team_id(m, venue) == team_id]
        return result[:limit]

    def league(self, key, at: datetime, limit=600):
        rows = self.leagues.get(key, [])
        return self._past(rows, self.league_times.get(key, []), at, limit)

    def global_prior(self, at: datetime, limit=1200):
        return self._past(self.global_games, self.global_times, at, limit)

    def league_baselines(self, key, at):
        global_rows = self.global_prior(at)
        global_h = (sum(outcome_scores(x)[0] for x in global_rows) + 200 * 1.43) / (len(global_rows) + 200)
        global_a = (sum(outcome_scores(x)[1] for x in global_rows) + 200 * 1.20) / (len(global_rows) + 200)
        rows = self.league(key, at)
        # Empirical Bayes: league-specific averages shrunk toward current global rates.
        h = (sum(outcome_scores(x)[0] for x in rows) + 70 * global_h) / (len(rows) + 70)
        a = (sum(outcome_scores(x)[1] for x in rows) + 70 * global_a) / (len(rows) + 70)
        return max(.6, h), max(.6, a), len(rows)


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


def _weighted_rate(events, team_id, at, *, goals_for, opponent_adjust, league_mean, index):
    numerator = denominator = 0.0
    for e in events:
        scores = outcome_scores(e)
        hid = _team_id(e, "home")
        if scores is None or hid is None:
            continue
        side = 0 if hid == team_id else 1
        goals = scores[side if goals_for else 1-side]
        opponent = _team_id(e, "away" if side == 0 else "home")
        weight = exp(-log(2) * max(0, (at - fixture_datetime(e)).days) / HALF_LIFE_DAYS)
        # Ajustement faible à la force de l'adversaire connue au moment du pari.
        if opponent_adjust and opponent:
            other = index.team(opponent, at, limit=10)
            if len(other) >= 4:
                against = []
                for old in other:
                    sc = outcome_scores(old)
                    against.append(sc[1] if _team_id(old, "home") == opponent else sc[0])
                other_conceded = (sum(against) + 6 * league_mean) / (len(against) + 6)
                factor = _clip(league_mean / max(.35, other_conceded), .80, 1.25)
                if goals_for:
                    goals *= factor
        numerator += weight * goals
        denominator += weight
    return (numerator + 4 * league_mean) / (denominator + 4)


def estimate_goals(event: dict, index: V2History) -> Tuple[Optional[dict], str]:
    hid, aid = _team_id(event, "home"), _team_id(event, "away")
    if not hid or not aid or hid == aid:
        return None, "missing_team_ids"
    at = fixture_datetime(event)
    hg, ag = index.team(hid, at), index.team(aid, at)
    if min(len(hg), len(ag)) < MIN_TEAM_GAMES:
        return None, "insufficient_form"
    if max((at - fixture_datetime(hg[0])).days, (at - fixture_datetime(ag[0])).days) > 240:
        return None, "stale_team_form"
    key = league_key(event)
    lh, la, league_games = index.league_baselines(key, at)
    home_attack = _weighted_rate(hg, hid, at, goals_for=True, opponent_adjust=True, league_mean=lh, index=index)
    away_defence = _weighted_rate(ag, aid, at, goals_for=False, opponent_adjust=False, league_mean=lh, index=index)
    away_attack = _weighted_rate(ag, aid, at, goals_for=True, opponent_adjust=True, league_mean=la, index=index)
    home_defence = _weighted_rate(hg, hid, at, goals_for=False, opponent_adjust=False, league_mean=la, index=index)
    home_venue = index.team(hid, at, venue="home", limit=8)
    away_venue = index.team(aid, at, venue="away", limit=8)
    xh = home_attack * away_defence / lh
    xa = away_attack * home_defence / la
    if len(home_venue) >= 3:
        rate = _weighted_rate(home_venue, hid, at, goals_for=True, opponent_adjust=False, league_mean=lh, index=index)
        xh = .85 * xh + .15 * rate
    if len(away_venue) >= 3:
        rate = _weighted_rate(away_venue, aid, at, goals_for=True, opponent_adjust=False, league_mean=la, index=index)
        xa = .85 * xa + .15 * rate
    xh, xa = _clip(xh, .35, 3.50), _clip(xa, .35, 3.50)
    return {
        "home": round(xh, 5), "away": round(xa, 5),
        "league_key": key, "league_samples": league_games,
        "league_goals_home": round(lh, 4), "league_goals_away": round(la, 4),
        "home_recent_matches": len(hg), "away_recent_matches": len(ag),
        "home_venue_matches": len(home_venue), "away_venue_matches": len(away_venue),
        "max_last_match_age_days": max((at - fixture_datetime(hg[0])).days, (at - fixture_datetime(ag[0])).days),
    }, "ok"


def score_matrix(lh: float, la: float, rho: float = 0.0, max_goals: int = 12):
    if not (.1 <= lh <= 5 and .1 <= la <= 5 and -.13 <= rho <= .13):
        raise ValueError("Invalid Poisson/Dixon-Coles parameters")
    ph = [exp(-lh) * lh**h / factorial(h) for h in range(max_goals+1)]
    pa = [exp(-la) * la**a / factorial(a) for a in range(max_goals+1)]
    result = {}
    total = 0.0
    for h in range(max_goals+1):
        for a in range(max_goals+1):
            tau = 1.0
            if h == 0 and a == 0: tau = 1 - lh*la*rho
            elif h == 0 and a == 1: tau = 1 + lh*rho
            elif h == 1 and a == 0: tau = 1 + la*rho
            elif h == 1 and a == 1: tau = 1 - rho
            p = ph[h] * pa[a] * max(tau, 1e-6)
            result[(h, a)] = p
            total += p
    return {k: v/total for k, v in result.items()}


def markets_from_matrix(matrix) -> List[Candidate]:
    p1 = sum(p for (h,a),p in matrix.items() if h > a)
    px = sum(p for (h,a),p in matrix.items() if h == a)
    p2 = sum(p for (h,a),p in matrix.items() if h < a)
    btts = sum(p for (h,a),p in matrix.items() if h > 0 and a > 0)
    over = {k: sum(p for (h,a),p in matrix.items() if h+a > k) for k in (1.5,2.5,3.5,4.5)}
    ps = {"1":p1, "X":px, "2":p2, "1X":p1+px, "X2":p2+px, "12":p1+p2,
          "BTTS_YES":btts,"BTTS_NO":1-btts}
    for k, prob in over.items():
        line = str(k).replace(".", "")
        ps["OVER_"+line] = prob
        ps["UNDER_"+line] = 1-prob
    return [replace(c, probability=_clip(ps[c.key],0.00001,.99999))
            for c in candidates_from_goals(1.3, 1.1)]


def _calibrated(candidate: Candidate, calibration: Optional[MarketCalibrator]):
    if calibration is None:
        return candidate.probability, 0
    _lower, p, n = calibration.score(candidate)
    return p, n


def choose_market(candidates, *, calibration=None, odds_by_market=None,
                  mode="reliability", min_probability=MIN_PROBABILITY, league_samples=100,
                  form_samples=10, require_odds=False, min_odds=1.20,
                  excluded_keys=None):
    """Fiabilité = meilleure probabilité calibrée (PAS meilleure cote).

    Mode value explicit : exige des cotes fournies et retourne le meilleur EV.
    Aucune cote n'est inventée depuis l'API BSD.
    """
    if mode not in ("reliability", "value"):
        raise ValueError("Unknown ranking mode")
    if not 1.01 <= min_odds <= 100:
        raise ValueError("Cote minimale incorrecte")
    banned = frozenset(excluded_keys or ())
    rows = []
    for c in candidates:
        if c.key in banned:
            continue
        p, n = _calibrated(c, calibration)
        if p < min_probability:
            continue
        price = None
        if odds_by_market and c.market_code in odds_by_market:
            value = odds_by_market[c.market_code]
            if not isinstance(value, bool):
                try:
                    value = float(value)
                    if isfinite(value) and min_odds <= value <= 100:
                        price = value
                except (TypeError, ValueError):
                    pass
        if (require_odds or mode == "value") and price is None:
            continue
        ev = p * price - 1 if price is not None else None
        if mode == "value" and ev <= .03:
            continue
        # Incertitude augmente en cas de peu de matches ou championnat mal couvert.
        uncertainty = .012 + (.025 if league_samples < 30 else 0) + (.020 if form_samples < 8 else 0)
        ranking_confidence = max(0, p - uncertainty)
        rows.append({
            "candidate": c, "calibrated_probability": round(p, 6),
            "ranking_confidence": round(ranking_confidence, 6),
            "calibration_samples": n,
            "theoretical_fair_odds": round(1/p, 4),
            "bookmaker_odds": price, "expected_value": round(ev, 5) if ev is not None else None,
        })
    if mode == "value":
        rows.sort(key=lambda x: (-x["expected_value"],-x["ranking_confidence"],x["candidate"].key))
    else:
        rows.sort(key=lambda x: (-x["ranking_confidence"],-x["calibrated_probability"],x["candidate"].key))
    return (rows[0] if rows else None), rows


def predict_v2(event, index, *, calibration=None, rho=0.0, clock=None,
               mode="reliability", odds_by_market=None, quality_policy=None,
               require_odds=False, min_odds=1.20, excluded_keys=None,
               btts_model=None):
    if str(event.get("status") or "").lower() not in ("notstarted", "upcoming"):
        return None, "not_upcoming"
    if event.get("id") is None:
        return None, "missing_event_id"
    try:
        at = fixture_datetime(event)
    except (ValueError, TypeError):
        return None, "invalid_date"
    if clock is not None and at <= clock:
        return None, "already_started"
    expected, reason = estimate_goals(event, index)
    if expected is None:
        return None, reason
    if quality_policy is not None:
        rejection = quality_policy.check_fixture(expected)
        if rejection:
            return None, rejection
    candidates = markets_from_matrix(score_matrix(expected["home"], expected["away"], rho))
    if btts_model is not None:
        from bsd_v2_btts import btts_candidates
        candidates = btts_candidates(event,index,candidates,btts_model)
    choice, all_options = choose_market(
        candidates, calibration=calibration, odds_by_market=odds_by_market,
        mode=mode, league_samples=expected["league_samples"],
        form_samples=min(expected["home_recent_matches"], expected["away_recent_matches"]),
        require_odds=require_odds, min_odds=min_odds, excluded_keys=excluded_keys,
    )
    if choice is None:
        return None, "no_qualified_market"
    if quality_policy is not None:
        # Un marché trop optimiste ne doit pas faire rejeter le match entier :
        # examiner le deuxième marché coté, puis les suivants.
        choice = next((row for row in all_options
                       if quality_policy.check_market(row) is None), None)
        if choice is None:
            return None, "quality_all_quoted_markets_rejected"
    c = choice["candidate"]
    # "PRO" based on data coverage; this label is not a measured hit-rate promise.
    pro = (choice["ranking_confidence"] >= .77 and expected["league_samples"] >= 40
           and min(expected["home_recent_matches"],expected["away_recent_matches"]) >= 10)
    market = {
        "key": c.key, "name": c.label, "market": c.market,
        "outcome": c.outcome, "line": c.line,
        "internal_market_code": c.market_code,
        "bookmaker_selection_code": None,
        "odds_source": "provided_verified_quote" if choice["bookmaker_odds"] is not None else None,
        "probability": choice["calibrated_probability"],
        "conservative_probability": choice["ranking_confidence"],
        "fair_odds": choice["theoretical_fair_odds"],
        "bookmaker_odds": choice["bookmaker_odds"],
        "estimated_value": choice["expected_value"],
        "calibration_samples": choice["calibration_samples"],
    }
    data = {
        "id": "bsd:" + str(event["id"]), "provider": "BSD",
        "source_event_id": event["id"],
        "event_date": at.isoformat(), "date": at.date().isoformat(),
        "league": event.get("league_name") or (event.get("league") if isinstance(event.get("league"),str) else None),
        "league_id": event.get("league_id"), "home_team_id": _team_id(event,"home"),
        "away_team_id": _team_id(event,"away"), "home_team": event.get("home_team"),
        "away_team": event.get("away_team"), "prediction": market,
        "estimated_goals": expected, "score_model": "Dixon-Coles" if rho else "Poisson",
        "rho": rho, "selection_mode": mode, "category": "pro" if pro else "simple",
        "model_version": "bsd-v2-isolated", "experimental": True, "published": False,
        "top_candidates": [{"key": row["candidate"].key,
                            "probability": row["calibrated_probability"],
                            "fair_odds": row["theoretical_fair_odds"]}
                           for row in all_options[:5]],
    }
    return data, "ok"


def fit_rho_2024(index: V2History, max_training=600, max_validation=300):
    """Ajuste rho sur janvier-août 2024 puis l'accepte uniquement s'il gagne
    en log-vraisemblance sur septembre-décembre 2024 (jamais 2025/2026).
    """
    training, validation = [], []
    for _, e in index.global_games:
        try:
            dt = fixture_datetime(e)
            if dt.year != 2024: continue
            feat, reason = estimate_goals(e, index)
            if feat is None: continue
            row = (feat["home"], feat["away"], outcome_scores(e))
            if dt.month <= 8:
                training.append(row)
            else:
                validation.append(row)
        except (ValueError, TypeError, OverflowError):
            continue
    # Deterministic stride sampling.
    def sample(xs, n):
        return [xs[int(i*len(xs)/n)] for i in range(n)] if len(xs)>n else xs
    train, val = sample(training, max_training), sample(validation, max_validation)
    if len(train) < 100 or len(val) < 50:
        return 0.0, {"training":len(train),"validation":len(val),"reason":"insufficient_2024_data"}
    grid = (-.12,-.08,-.04,0.0,.04,.08,.12)
    def average_nll(rows, rho):
        loss = 0.
        for h,a,score in rows:
            m = score_matrix(h,a,rho)
            loss -= log(max(1e-12, m.get(score,1e-12)))
        return loss/len(rows)
    best = min(grid,key=lambda x: average_nll(train,x))
    base_val = average_nll(val,0)
    score_val = average_nll(val,best)
    chosen = best if score_val < base_val - .0005 else 0.0
    return chosen, {"training":len(train),"validation":len(val),
                    "fitted_rho":best,"chosen_rho":chosen,
                    "poisson_validation_logloss":round(base_val,5),
                    "dixon_coles_validation_logloss":round(score_val,5)}
