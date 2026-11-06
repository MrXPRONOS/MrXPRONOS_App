"""Historical coherent calibration: train Jan-Aug 2025, gate on Sep-Dec 2025.

No 2026 result enters fitting or the gate. Candidate model scores stay on
a joint score distribution, unlike independent per-market probability edits.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from math import fsum
from .legacy import estimate_goals, fixture_datetime, outcome_scores, realized
from .probabilities import coherent_candidates, normalized, tilt_result, tilt_event, prove_coherence

@dataclass
class V3Calibration:
    corrections: dict
    trained: int
    validated: int
    validation_baseline_brier: float | None = None
    validation_candidate_brier: float | None = None
    active: bool = False

    def apply(self, matrix):
        if not self.active or not self.corrections:
            return normalized(matrix)
        _matrix, base = matrix, __import__("bsd_v3.legacy", fromlist=["markets_from_matrix"]).markets_from_matrix(matrix)
        probs = {c.key: c.probability for c in base}
        target = [max(.0001, probs[k] + self.corrections.get(k, 0.))
                  for k in ("1", "X", "2")]
        matrix = tilt_result(matrix, target)
        # Stronger back-and-forth at a bounded shift avoids a single final
        # independent-market correction that would break monotonicity.
        for _ in range(2):
            for line in ("15", "25", "35", "45"):
                key = "OVER_" + line
                if key in self.corrections:
                    desired = max(.001, min(.999, probs[key] + self.corrections[key]))
                    matrix = tilt_event(matrix, lambda score, line=int(line)//10: sum(score)>line,
                                        desired, strength=.20)
            if "BTTS_YES" in self.corrections:
                desired = max(.001, min(.999, probs["BTTS_YES"]+self.corrections["BTTS_YES"]))
                matrix = tilt_event(matrix, lambda score: score[0]>0 and score[1]>0,
                                    desired, strength=.20)
        return normalized(matrix)

    def metadata(self):
        return {"trained":self.trained, "validated":self.validated,
                "active":self.active, "base_brier":self.validation_baseline_brier,
                "calibrated_brier":self.validation_candidate_brier,
                "source_period":"2025-01 to 2025-08",
                "gate_period":"2025-09 to 2025-12",
                "n_corrections":len(self.corrections)}

def _score_rows(event, index, rho):
    feat, reason = estimate_goals(event, index)
    if feat is None:
        return None
    matrix, candidates = coherent_candidates(feat, rho)
    return matrix, candidates

def _brier(candidates, home, away):
    return fsum((c.probability - realized(c, home, away)) ** 2 for c in candidates)/len(candidates)

def fit_calibration(index, rho, *, train_limit=2500, validation_limit=1000,
                    min_validation=100, min_improvement=.00001):
    matches = [item for _,item in index.global_games
               if fixture_datetime(item).year == 2025]
    matches.sort(key=lambda e: (fixture_datetime(e), str(e.get("id"))))
    train = [m for m in matches if fixture_datetime(m).month <= 8][:train_limit]
    validation = [m for m in matches if fixture_datetime(m).month >= 9][:validation_limit]
    deltas = defaultdict(lambda: [0.,0])
    trained = 0
    for event in train:
        values = _score_rows(event, index, rho)
        if values is None:
            continue
        _, candidates = values
        h,a = outcome_scores(event)
        for c in candidates:
            row = deltas[c.key]
            row[0] += realized(c,h,a) - c.probability
            row[1] += 1
        trained += 1
    # Shrunk empirical residuals, with a hard 3.5-point cap to avoid
    # overfitting sparse markets.
    corrections = {key: max(-.035, min(.035, error/(n+100.)))
                   for key,(error,n) in deltas.items() if n >= 40}
    model = V3Calibration(corrections, trained, 0)
    baseline_loss = candidate_loss = 0.
    for event in validation:
        values = _score_rows(event, index, rho)
        if values is None:
            continue
        matrix, baseline = values
        h,a = outcome_scores(event)
        b = _brier(baseline,h,a)
        candidate = __import__("bsd_v3.legacy", fromlist=["markets_from_matrix"]).markets_from_matrix(model.apply.__func__(model,matrix)
                 if False else matrix)  # reference unchanged before validation
        model.active = True
        try:
            calibrated = __import__("bsd_v3.legacy", fromlist=["markets_from_matrix"]).markets_from_matrix(model.apply(matrix))
            prove_coherence(calibrated)
            c = _brier(calibrated,h,a)
        finally:
            model.active = False
        baseline_loss += b
        candidate_loss += c
        model.validated += 1
    if model.validated:
        model.validation_baseline_brier = round(baseline_loss/model.validated, 8)
        model.validation_candidate_brier = round(candidate_loss/model.validated, 8)
    model.active = bool(model.validated >= min_validation and model.trained >= 100 and
                        model.validation_candidate_brier is not None and
                        model.validation_candidate_brier + min_improvement <
                        model.validation_baseline_brier)
    return model
