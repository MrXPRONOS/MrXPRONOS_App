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
    return "C"


def select_tiered(fixtures: list[RankedFixture], limit: int,
                  max_per_league: int = 4) -> list[RankedFixture]:
    """Prioritize A -> B -> C, maintaining a soft diversity quota.

    First pass respects max_per_league for all tiers. Second pass fills from
    highest editorial grade without the quota; it never invents fixtures.
    All fixtures must have already passed historical and source checks.
    """
    if not 1 <= limit <= 30:
        raise ValueError("Nombre de pronostics hors limites")
    if max_per_league < 1:
        raise ValueError("Quota de championnat hors limites")
    ranked = rank_fixtures(fixtures)
    # rank_fixtures is already monotonic with grades; tie break is deterministic.
    result: list[RankedFixture] = []
    seen: set[str] = set()
    per_league: dict[str, int] = {}
    for allow_overquota in (False, True):
        for match in ranked:
            if match.id in seen:
                continue
            if not allow_overquota and per_league.get(match.competition, 0) >= max_per_league:
                continue
            result.append(match)
            seen.add(match.id)
            per_league[match.competition] = per_league.get(match.competition, 0) + 1
            if len(result) >= limit:
                return result
    return result
