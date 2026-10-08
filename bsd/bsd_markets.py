"""Marchés pré-match buts et résultats; une sélection possible par rencontre.

Codes normalisés BSD (NOT des codes de coupon bookmaker).
Comparaison fondée sur P(score exact) d'un modèle de Poisson, et calibration
hors échantillon. Les paris avec remboursement (DNB) sont exclus du classement
binaire faute de comparabilité directe; ils pourront être évalués avec cotes.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, factorial, sqrt
from typing import Dict, List, Optional, Tuple

# Ne pas autoriser les prix théoriques dérisoires; ne remplace PAS des cotes réelles.
DEFAULT_MIN_FAIR_ODDS = 1.32
DEFAULT_MIN_PROBABILITY = 0.70


@dataclass(frozen=True)
class Candidate:
    key: str
    market: str
    outcome: str
    label: str
    family: str
    probability: float
    line: Optional[float] = None

    @property
    def market_code(self) -> str:
        if self.family == "goals":
            return "OU_%.1f_%s_FT" % (self.line, self.outcome.upper())
        if self.family == "result":
            return "1X2_%s_FT" % self.outcome
        if self.family == "double_chance":
            return "DC_%s_FT" % self.outcome
        return "BTTS_%s_FT" % self.outcome.upper()


def candidates_from_goals(home_xg: float, away_xg: float, *, max_goals: int = 16) -> List[Candidate]:
    if not 0 < home_xg <= 10 or not 0 < away_xg <= 10 or max_goals < 10:
        raise ValueError("Paramètres buts invalides")
    ph = [exp(-home_xg) * home_xg**i / factorial(i) for i in range(max_goals + 1)]
    pa = [exp(-away_xg) * away_xg**i / factorial(i) for i in range(max_goals + 1)]
    total = sum(ph) * sum(pa)
    p1 = pd = p2 = btts = 0.0
    overs = {line: 0.0 for line in (1.5, 2.5, 3.5, 4.5)}
    for h, hp in enumerate(ph):
        for a, ap in enumerate(pa):
            p = hp * ap / total
            if h > a:
                p1 += p
            elif h == a:
                pd += p
            else:
                p2 += p
            if h and a:
                btts += p
            for line in overs:
                if h + a > line:
                    overs[line] += p
    specs = [
        ("1", "1x2", "HOME", "Victoire domicile", "result", p1, None),
        ("X", "1x2", "DRAW", "Match nul", "result", pd, None),
        ("2", "1x2", "AWAY", "Victoire extérieur", "result", p2, None),
        ("1X", "double_chance", "1X", "Domicile ou nul", "double_chance", p1 + pd, None),
        ("12", "double_chance", "12", "Une équipe gagne", "double_chance", p1 + p2, None),
        ("X2", "double_chance", "X2", "Extérieur ou nul", "double_chance", p2 + pd, None),
        ("BTTS_YES", "btts", "yes", "Les deux marquent : Oui", "btts", btts, None),
        ("BTTS_NO", "btts", "no", "Les deux marquent : Non", "btts", 1-btts, None),
    ]
    for line, p_over in overs.items():
        suffix = str(line).replace(".", "")
        specs += [
            ("OVER_" + suffix, "over_under_" + suffix, "over", "Plus de %.1f buts" % line, "goals", p_over, line),
            ("UNDER_" + suffix, "over_under_" + suffix, "under", "Moins de %.1f buts" % line, "goals", 1-p_over, line),
        ]
    return [Candidate(*spec) for spec in specs]


def realized(candidate: Candidate, home_goals: int, away_goals: int) -> int:
    if home_goals < 0 or away_goals < 0:
        raise ValueError("Scores négatifs")
    key = candidate.key
    if key == "1": return int(home_goals > away_goals)
    if key == "X": return int(home_goals == away_goals)
    if key == "2": return int(away_goals > home_goals)
    if key == "1X": return int(home_goals >= away_goals)
    if key == "X2": return int(away_goals >= home_goals)
    if key == "12": return int(home_goals != away_goals)
    if key == "BTTS_YES": return int(home_goals > 0 and away_goals > 0)
    if key == "BTTS_NO": return int(home_goals == 0 or away_goals == 0)
    if key.startswith("OVER_"): return int(home_goals + away_goals > candidate.line)
    if key.startswith("UNDER_"): return int(home_goals + away_goals < candidate.line)
    raise ValueError("Marché non reconnu : " + key)


class MarketCalibrator:
    """Beta-Binomial par marché+tranche, apprentissage sur année antérieure.

    Le prior représente la probabilité du modèle et évite de surestimer
    une catégorie de quelques observations.
    """

    def __init__(self, counts=None, *, prior_strength: int = 60):
        self.counts = dict(counts or {})
        self.prior_strength = prior_strength

    @staticmethod
    def _bucket(p: float) -> str:
        return str(min(9, max(0, int(p * 10))))

    def observe(self, item: Candidate, actual: int) -> None:
        k = item.key + ":" + self._bucket(item.probability)
        n, successes = self.counts.get(k, (0, 0))
        self.counts[k] = (n + 1, successes + int(actual))

    def score(self, item: Candidate) -> Tuple[float, float, int]:
        n, successes = self.counts.get(item.key + ":" + self._bucket(item.probability), (0, 0))
        empirical_posterior = (self.prior_strength * item.probability + successes) / (self.prior_strength + n)
        # La calibration provient de 2025, pas de la saison courante : on limite
        # son influence pour éviter des probabilités exagérément optimistes.
        transfer_weight = 0.35 * n / (n + 400)
        shift = max(-0.035, min(0.035, transfer_weight * (empirical_posterior - item.probability)))
        calibrated = max(0.01, min(0.99, item.probability + shift))
        # Garde-fou empirique, pas une borne statistique à 95 % :
        # une tranche calibrée globalement ne garantit pas un match particulier.
        uncertainty = max(0.015, 0.5 * sqrt(calibrated * (1 - calibrated) / (self.prior_strength + n + 1)))
        conservative = calibrated - uncertainty
        return max(0.0, conservative), calibrated, n

    def to_dict(self):
        return {"model": "bsd-market-calibration-v1", "prior_strength": self.prior_strength,
                "counts": {k: list(v) for k, v in self.counts.items()}}

    @classmethod
    def from_dict(cls, doc):
        if doc.get("model") != "bsd-market-calibration-v1":
            raise ValueError("Calibration incompatible")
        return cls({k: tuple(v) for k, v in doc["counts"].items()},
                   prior_strength=int(doc["prior_strength"]))


def select_best(candidates: List[Candidate], *, calibration: Optional[MarketCalibrator] = None,
                min_probability: float = DEFAULT_MIN_PROBABILITY,
                min_fair_odds: float = DEFAULT_MIN_FAIR_ODDS,
                max_fair_odds: float = 3.50):
    """Compare tous les marchés sur une base identique, peut ne rien sélectionner.

    En l'absence de cotes réelles, le plancher de 1.32 n'est qu'un filtre
    théorique de marchés excessivement probables, PAS une preuve de valeur.
    """
    ranked = []
    for c in candidates:
        if c.probability <= 0 or c.probability >= 1:
            continue
        fair_odds = 1 / c.probability
        if not min_fair_odds <= fair_odds <= max_fair_odds:
            continue
        if calibration is None:
            conservative, calibrated, support = c.probability - .04, c.probability, 0
        else:
            conservative, calibrated, support = calibration.score(c)
        if conservative < min_probability:
            continue
        ranked.append({
            "candidate": c,
            "model_probability": round(c.probability, 6),
            "calibrated_probability": round(calibrated, 6),
            "conservative_probability": round(conservative, 6),
            "calibration_samples": support,
            "model_fair_odds": round(fair_odds, 3),
        })
    ranked.sort(key=lambda x: (-x["conservative_probability"], -x["calibrated_probability"],
                               x["candidate"].key))
    return (ranked[0] if ranked else None), ranked
