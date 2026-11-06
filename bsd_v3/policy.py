"""Explicit V3 risk policy. No changes to BSD V2 policy or published data."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite

PUBLIC_EXCLUSIONS = frozenset({"UNDER_45", "12"})
FAMILIES = frozenset({"result", "double_chance", "goals", "btts"})
FAMILY_EDGE = {"result": .025, "double_chance": .018, "goals": .022, "btts": .022}


@dataclass(frozen=True)
class V3Policy:
    min_team_games: int = 5
    min_league_games: int = 15
    min_full_league_games: int = 30
    min_full_venue_games: int = 3
    max_recent_days: int = 150
    min_public_probability: float = .79
    min_public_conservative: float = .775
    min_over15_conservative: float = .85
    min_odds: float = 1.20
    max_quote_age_seconds: int = 7200
    min_shadow_value_ev: float = .03
    max_joint_correlation: float = .55
    max_selections: int = 2
    max_odds_events: int = 15
    max_api_requests: int = 90

    def __post_init__(self):
        if (not 0 < self.min_public_conservative <= self.min_public_probability < 1
                or not 0 < self.min_shadow_value_ev < 1
                or not 1 < self.min_odds <= 100
                or not 0 < self.max_joint_correlation < 1
                or not 1 <= self.max_selections <= 2
                or self.max_odds_events < 0 or self.max_api_requests < 1):
            raise ValueError("Invalid BSD V3 policy")


def valid_probability(p):
    return type(p) in (int, float) and isfinite(p) and 0 < p < 1


def classify_fixture(features, policy=V3Policy()):
    """Do not guess missing histories. 'limited' never becomes a public recommendation."""
    if not isinstance(features, dict):
        return {"level": "rejected", "reason": "missing_features"}
    if min(features.get("home_recent_matches", 0), features.get("away_recent_matches", 0)) < policy.min_team_games:
        return {"level": "rejected", "reason": "short_form"}
    if features.get("league_samples", 0) < policy.min_league_games:
        return {"level": "rejected", "reason": "league_history"}
    if features.get("max_last_match_age_days", 9999) > policy.max_recent_days:
        return {"level": "rejected", "reason": "stale_form"}
    venues = min(features.get("home_venue_matches", 0), features.get("away_venue_matches", 0))
    full = (features["league_samples"] >= policy.min_full_league_games
            and venues >= policy.min_full_venue_games)
    return {"level": "full" if full else "limited",
            "reason": "sufficient" if full else "limited_venue_or_league",
            "league_games": features["league_samples"], "venue_games": venues,
            "recent_games": min(features["home_recent_matches"],
                                features["away_recent_matches"])}


def uncertainty_adjustment(features, quality, calibration_samples=0):
    """Empirical safety haircut, not a claimed statistical confidence interval."""
    delta = .02
    if quality["level"] == "limited":
        delta += .04
    if features.get("league_samples", 0) < 30:
        delta += .015
    if calibration_samples < 30:
        delta += .015
    return min(.15, delta)


def quality_tier(row, quality):
    """Mirror V2 Pro/VIP history requirements before considering odds."""
    if not isinstance(quality, dict) or quality.get("level") != "full":
        return "simple"
    recent = quality.get("recent_games", 0)
    league = quality.get("league_games", 0)
    venue = quality.get("venue_games", 0)
    p = row.get("conservative_probability", 0)
    if p >= .81 and league >= 80 and recent >= 12 and venue >= 5:
        return "vip"
    if p >= .77 and league >= 40 and recent >= 10:
        return "pro"
    return "simple"


def public_candidate(row, quality, policy=V3Policy()):
    if row["key"] in PUBLIC_EXCLUSIONS or quality_tier(row, quality) == "simple":
        return False
    if row["probability"] < policy.min_public_probability:
        return False
    if row["conservative_probability"] < policy.min_public_conservative:
        return False
    if row["key"] == "OVER_15" and row["conservative_probability"] < policy.min_over15_conservative:
        return False
    return True


def quote_value(row, quote, policy=V3Policy()):
    """Only a fresh, externally observed quote may establish economic value."""
    if not quote or quote.get("verified") is not True:
        return None
    price = quote.get("odds")
    if not (valid_probability(row.get("conservative_probability")) and
            type(price) in (float, int) and isfinite(price) and price >= policy.min_odds):
        return None
    p = row["probability"]
    pc = row["conservative_probability"]
    return {"central_ev": round(p * price - 1, 6),
            "conservative_ev": round(pc * price - 1, 6),
            "implied_probability": round(1 / price, 6)}


def label_candidate(row, quality, quote, policy=V3Policy()):
    """Shadow classifications; never an authorization to publish."""
    public = public_candidate(row, quality, policy)
    ev = quote_value(row, quote, policy)
    price_ok = bool(ev and ev["conservative_ev"] >= FAMILY_EDGE[row["family"]]
                    and row["conservative_probability"] >=
                    ev["implied_probability"] + FAMILY_EDGE[row["family"]])
    value = bool(row["key"] not in PUBLIC_EXCLUSIONS and ev and quote
                 and quote.get("executable") is True
                 and ev["conservative_ev"] >= policy.min_shadow_value_ev)
    return {"pro_vip_shadow": public and price_ok,
            "quality_tier":quality_tier(row,quality),
            "value_shadow": value,
            "quote_benchmark_only":bool(quote and quote.get("benchmark_only")),
            "ev": ev,
            "public_preprice": public,
            "quote_verified": bool(quote and quote.get("verified"))}


def utc_datetime(raw):
    if isinstance(raw, datetime):
        dt = raw
    elif isinstance(raw, str):
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    else:
        raise ValueError("Missing timestamp")
    if dt.tzinfo is None:
        raise ValueError("Naive timestamp is forbidden")
    return dt.astimezone(timezone.utc)
