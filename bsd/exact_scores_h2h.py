"""Low-scoring, stable H2H detector — point-in-time, BSD V2 private history.

The system NEVER consults scores of the fixture itself or later events.
History becomes available only after BSD V2's 4-hour settlement delay.
Low-variance H2H is a selection PRIORITY, not a guarantee of an exact result.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from datetime import timedelta
from math import sqrt

from bsd_h2h import _team_id
from bsd_v2_core import fixture_datetime, outcome_scores


class H2HIndex:
    def __init__(self, history):
        pairs = defaultdict(list)
        for settled_at, event in history.global_games:
            h, a = _team_id(event, "home"), _team_id(event, "away")
            if h is None or a is None:
                continue
            key = tuple(sorted((h, a)))
            pairs[key].append((settled_at, event))
        self.pairs = {}
        for key, entries in pairs.items():
            entries.sort(key=lambda item: item[0])
            self.pairs[key] = (entries, [t for t, _ in entries])

    def past_scores(self, fixture, *, limit=8, years=4):
        home, away = _team_id(fixture, "home"), _team_id(fixture, "away")
        if not home or not away or home == away:
            return []
        entries, timestamps = self.pairs.get(tuple(sorted((home, away))), ([], []))
        cutoff = fixture_datetime(fixture)
        begin = cutoff - timedelta(days=365.25 * years)
        end_idx = bisect_right(timestamps, cutoff.timestamp())
        out = []
        for _, previous in reversed(entries[:end_idx]):
            when = fixture_datetime(previous)
            if when < begin:
                break
            scores = outcome_scores(previous)
            if scores is None:
                continue
            if _team_id(previous, "home") == home:
                h, a = scores
            else:
                h, a = scores[1], scores[0]
            out.append((h, a))
            if len(out) >= limit:
                break
        return out


def h2h_signal(scores, *, min_meetings=3):
    """Identify low and nonvolatile matches; thresholds decided before 2026 test.

    3+ meetings, mean <= 1.75 total goals, >=75% <=2 goals,
    no historical fixture >3 goals and SD(total goals) <= 1.0.
    """
    totals = [h + a for h, a in scores]
    n = len(totals)
    if not n:
        return {"prioritized": False, "meetings": 0, "reason": "no_history"}
    avg = sum(totals) / n
    variance = sum((v - avg) ** 2 for v in totals) / n
    std = sqrt(variance)
    low_fraction = sum(t <= 2 for t in totals) / n
    stable = (
        n >= min_meetings
        and avg <= 1.75
        and low_fraction >= .75
        and max(totals) <= 3
        and std <= 1.0
    )
    # Ranking only, never replace statistically calibrated match probability.
    # When insufficient H2H, the rank is 0, not a falsely confident score.
    priority = (min(1.0, n / 6) * low_fraction *
                max(0.0, 1 - avg / 3) * max(0.0, 1 - std / 2)
                if stable else 0.0)
    return {
        "prioritized": stable, "meetings": n,
        "avg_total": round(avg, 4), "std_total": round(std, 4),
        "share_at_most_2": round(low_fraction, 4),
        "max_total": max(totals), "priority": round(priority, 6),
        "reason": "low_and_stable" if stable else
                  ("insufficient_meetings" if n < min_meetings else "not_low_stable"),
    }


def blended_goals(home, away, signal, *, influence=0.0):
    """Controlled optional correction; influence trained only on 2025 H2Hs.

    Total H2H mean is shrunk toward the base model to avoid n=3 overfit.
    Zero influence = pure priority/screening, identical score probabilities.
    """
    if not signal.get("prioritized") or influence <= 0:
        return home, away
    n = signal["meetings"]
    strength = n / (n + 6.0)
    base = home + away
    target = max(.75, min(4.5, float(signal["avg_total"])))
    multiplier = 1 + influence * strength * (target / base - 1)
    multiplier = max(.70, min(1.10, multiplier))
    return home * multiplier, away * multiplier
