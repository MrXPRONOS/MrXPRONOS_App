"""Transparent editorial ranking of notable football fixtures.

V2 recognises senior / youth / women's teams and competition/stage distinctions.
Ranking never uses goals, result scores, betting odds, live audience or model
prediction probabilities. Importance means editorial prominence only.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import datetime

from .daily_popularity import (
    LEAGUE_WEIGHT, STAGE_WEIGHT, TEAM_WEIGHT, DERBIES, normalize,
    _team_class, club_class, squad_category, stage_class, importance_score,
)


@dataclass(frozen=True)
class RankedFixture:
    id: str
    competition: str
    competition_name: str
    kickoff: datetime
    home_id: str
    away_id: str
    home_name: str
    away_name: str
    stage: str
    source: str
    source_verified: bool
    neutral_venue: bool | None = None
    home_logo_url: str | None = None
    away_logo_url: str | None = None
    importance: int = 0
    importance_reasons: tuple[str, ...] = ()


def importance(fixture: RankedFixture) -> RankedFixture:
    score, reasons = importance_score(fixture)
    return replace(fixture, importance=score, importance_reasons=reasons)


def rank_fixtures(fixtures: list[RankedFixture]) -> list[RankedFixture]:
    return sorted((importance(f) for f in fixtures),
                  key=lambda f: (-f.importance, f.kickoff, f.id))


def diverse_ranked(fixtures: list[RankedFixture], limit: int, max_per_league: int = 4
                   ) -> list[RankedFixture]:
    """Apply a soft per-league quota, then fill with remaining popular fixtures.

    Retains pre-existing behaviour: a source with only one competition can
    still fill ten fixtures. Never invent a match to satisfy the daily quota.
    """
    if limit < 1:
        return []
    ranked = rank_fixtures(fixtures)
    result: list[RankedFixture] = []
    seen: set[str] = set()
    counts: dict[str, int] = {}
    for fixture in ranked:
        if fixture.id in seen or counts.get(fixture.competition, 0) >= max_per_league:
            continue
        result.append(fixture)
        seen.add(fixture.id)
        counts[fixture.competition] = counts.get(fixture.competition, 0) + 1
        if len(result) == limit:
            return result
    for fixture in ranked:
        if fixture.id not in seen:
            result.append(fixture)
            seen.add(fixture.id)
            if len(result) == limit:
                break
    return result


# Editorial grades, not bookmaker-confidence grades.
# All three levels still require real schedules and separately validated history.
TIER_A_MIN = 220
TIER_B_MIN = 145
TIER_C_MIN = 70


def popularity_tier(importance_value: int) -> str:
    if importance_value >= TIER_A_MIN:
        return "A"
    if importance_value >= TIER_B_MIN:
        return "B"
    if importance_value >= TIER_C_MIN:
        return "C"
    return "D"


def select_tiered(fixtures: list[RankedFixture], limit: int,
                  max_per_league: int = 4,
                  history_strength: dict[str, int] | None = None
                  ) -> list[RankedFixture]:
    """Fill up to limit with real eligible fixtures in A, B, C, D order.

    A/B/C are the popularity-first selections; D includes otherwise eligible
    less-famous clubs and leagues and is used strictly as a fallback. Never
    sacrifice an A fixture to enforce the per-league quota on a lower tier.

    History counts are a *tie-breaker only* for equally ranked fixtures: they
    do not manufacture club popularity or weaken any pre-match quality gate.
    All fixtures must have passed provider, history and model checks upstream.
    """
    if not 1 <= limit <= 30:
        raise ValueError("Nombre de pronostics hors limites")
    if max_per_league < 1:
        raise ValueError("Quota de championnat hors limites")
    strength = history_strength or {}
    ranked = sorted(rank_fixtures(fixtures),
                    key=lambda f: (-f.importance, -max(0, strength.get(f.id, 0)),
                                   f.kickoff, f.id))
    result: list[RankedFixture] = []
    seen: set[str] = set()
    per_league: dict[str, int] = {}
    for tier in ("A", "B", "C", "D"):
        # Diversity is soft *within the same priority tier*, not across tiers.
        # A fifth prestigious match beats any B/C/D candidate, for example.
        for allow_overquota in (False, True):
            for match in ranked:
                if match.id in seen or popularity_tier(match.importance) != tier:
                    continue
                if not allow_overquota and per_league.get(match.competition, 0) >= max_per_league:
                    continue
                result.append(match)
                seen.add(match.id)
                per_league[match.competition] = per_league.get(match.competition, 0) + 1
                if len(result) >= limit:
                    return result
    return result
