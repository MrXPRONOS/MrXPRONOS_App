"""Calibration et qualité V2 : aucune donnée 2026 dans l'entraînement.

Calibration sur janvier–août 2025 ; contrôle qualité sur septembre–décembre
2025. Tous les tests 2026 restent hors échantillon. Paramètres explicites,
et non optimisés sur les résultats 2026.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime
from math import sqrt
from typing import Optional
from bsd_v2_core import estimate_goals, fixture_datetime, markets_from_matrix, score_matrix, outcome_scores, choose_market
from bsd_markets import realized


class V2Calibration:
    def __init__(self, prior=90, counts=None):
        self.prior = int(prior)
        self.counts = {k: tuple(v) for k,v in (counts or {}).items()}

    @staticmethod
    def _key(item):
        return "%s:%d" % (item.key, min(9, int(item.probability * 10)))

    def observe(self, item, won):
        k = self._key(item)
        n, successes, sum_expected = self.counts.get(k, (0,0,0.))
        self.counts[k] = n+1, successes+int(won), sum_expected+item.probability

    def score(self, item):
        n, success, expected_sum = self.counts.get(self._key(item), (0,0,0.))
        # Le prior maintient la probabilité de la distribution de scores;
        # la tranche empirique ne la corrige qu'après suffisamment d'exemples.
        observed_minus_expected = (success - expected_sum) / (self.prior+n)
        corrected = min(.99,max(.01,item.probability+observed_minus_expected))
        # Plancher empirique (pas un IC garanti), réduit la surconfiance.
        lower = max(0.,corrected - max(.012,sqrt(corrected*(1-corrected)/(n+self.prior+1))))
        return lower, corrected, n

    def to_dict(self):
        return {"format":"bsd-v2-market-calibrator-1",
                "prior":self.prior,"counts":{k:list(v) for k,v in self.counts.items()}}

    @classmethod
    def from_dict(cls, data):
        if data.get("format") != "bsd-v2-market-calibrator-1":
            raise ValueError("Calibration V2 incompatible")
        counts = data.get("counts")
        if not isinstance(counts,dict):
            raise ValueError("Counts invalides")
        for row in counts.values():
            if not isinstance(row,list) or len(row)!=3 or row[0]<0 or row[1]<0 or row[1]>row[0]:
                raise ValueError("Données calibration invalides")
        return cls(data["prior"],counts)


class V2QualityPolicy:
    def __init__(self, performance=None, *, min_league=20, min_form=6, max_age=150,
                 max_market_gap=.08, min_market_validation=30):
        self.performance=dict(performance or {})
        self.min_league=min_league
        self.min_form=min_form
        self.max_age=max_age
        self.max_market_gap=max_market_gap
        self.min_market_validation=min_market_validation

    def check_fixture(self, features):
        if features["league_samples"] < self.min_league:
            return "quality_league_history"
        if min(features["home_recent_matches"],features["away_recent_matches"]) < self.min_form:
            return "quality_short_form"
        if features["max_last_match_age_days"] > self.max_age:
            return "quality_stale_form"
        return None

    def check_market(self, choice):
        key = choice["candidate"].key
        stats = self.performance.get(key)
        if stats and stats["n"] >= self.min_market_validation:
            if stats["sum_pred"] / stats["n"] - stats["wins"] / stats["n"] > self.max_market_gap:
                return "quality_market_overconfident"
        return None

    def to_dict(self):
        return {"format":"bsd-v2-quality-1","performance":self.performance,
                "min_league":self.min_league,"min_form":self.min_form,
                "max_age":self.max_age,"max_market_gap":self.max_market_gap,
                "min_market_validation":self.min_market_validation}

    @classmethod
    def from_dict(cls,doc):
        if doc.get("format")!="bsd-v2-quality-1":
            raise ValueError("Qualité V2 incompatible")
        return cls(doc["performance"],min_league=doc["min_league"],
                   min_form=doc["min_form"],max_age=doc["max_age"],
                   max_market_gap=doc["max_market_gap"],
                   min_market_validation=doc["min_market_validation"])


def fit_policy(index, *, rho, calibration_year=2025, max_train=3000, max_validation=1200,
               btts_model=None):
    """Séparation temporelle stricte à l'intérieur de 2025, sans ré-entrainement
    sur le trimestre utilisé pour estimer la qualité par marché.
    """
    matches=[e for _,e in index.global_games
             if fixture_datetime(e).year==calibration_year]
    matches.sort(key=lambda e:(e["event_date"],str(e["id"])))
    train=[e for e in matches if fixture_datetime(e).month<=8]
    validation=[e for e in matches if fixture_datetime(e).month>=9]
    def thin(xs, cap):
        return [xs[int(i*len(xs)/cap)] for i in range(cap)] if len(xs)>cap else xs
    train=thin(train,max_train)
    validation=thin(validation,max_validation)
    cal=V2Calibration()
    trained=0
    for event in train:
        feat,why=estimate_goals(event,index)
        if feat is None:continue
        scored=outcome_scores(event)
        candidates=markets_from_matrix(score_matrix(feat["home"],feat["away"],rho))
        if btts_model is not None:
            from bsd_v2_btts import btts_candidates
            candidates=btts_candidates(event,index,candidates,btts_model)
        for c in candidates:
            cal.observe(c,realized(c,*scored))
        trained+=1
    perf=defaultdict(lambda:{"n":0,"wins":0,"sum_pred":0.})
    validated=0
    for event in validation:
        feat,why=estimate_goals(event,index)
        if feat is None:continue
        candidates=markets_from_matrix(score_matrix(feat["home"],feat["away"],rho))
        if btts_model is not None:
            from bsd_v2_btts import btts_candidates
            candidates=btts_candidates(event,index,candidates,btts_model)
        # Contrôle par marché : tous les marchés observés, pas seulement le gagnant.
        actual=outcome_scores(event)
        for c in candidates:
            _lower,p,_n=cal.score(c)
            row=perf[c.key]
            row["n"]+=1
            row["wins"]+=realized(c,*actual)
            row["sum_pred"]+=p
        validated+=1
    policy=V2QualityPolicy(dict(perf))
    diag={"train_period":"2025-01-01 to 2025-08-31",
          "validation_period":"2025-09-01 to 2025-12-31",
          "training_eligible":trained,"validation_eligible":validated,
          "calendar_year":calibration_year}
    return cal,policy,diag
