"""V2 popularity selection: club identity, match, competition and round."""
from datetime import datetime, timezone

from dcscore.daily_rank import (
    RankedFixture, importance, rank_fixtures, diverse_ranked, squad_category,
    club_class,
)
from dcscore.daily_popularity import stage_class
from dcscore.daily_espn import _provider_round, ALLOWED, parse_event


NOW = datetime(2026, 11, 12, 20, tzinfo=timezone.utc)


def f(home="Real Madrid", away="Barcelona", competition="ES:ESP.1",
      league="Liga", stage="REGULAR_SEASON", num=1):
    return RankedFixture(
        id=str(num), competition=competition, competition_name=league,
        kickoff=NOW, home_id="h"+str(num), away_id="a"+str(num),
        home_name=home, away_name=away, stage=stage, source="test",
        source_verified=True,
    )


def test_senior_liverpool_does_not_transfer_brand_to_u21():
    first = importance(f("Liverpool", "Manchester United", "ES:ENG.1", "Premier League"))
    juniors = importance(f("Liverpool U21", "Manchester United U21",
                           "ES:ENG.TROPHY", "EFL Trophy"))
    assert first.importance > juniors.importance + 140
    assert "equipe_jeunes_reserve=-60" in juniors.importance_reasons
    assert not any("club_domicile" in s for s in juniors.importance_reasons)
    assert not any("derby_reconnu" in s for s in juniors.importance_reasons)
    assert squad_category("Liverpool U21") == "youth_reserve"


def test_reserves_youth_and_academy_identified_without_fuzzy_senior_match():
    for team in ("Barcelona B", "Bayern II", "Real Madrid Castilla",
                 "Chelsea Academy", "PSG U19", "Porto Reserves"):
        assert squad_category(team) == "youth_reserve"
        assert club_class(team)[1] == 0
    assert club_class("Real Madrid CFF")[1] == 0


def test_women_have_separate_not_zero_recognition():
    fixture = importance(f("Chelsea Women", "FC Barcelona Women",
                          "ES:UEFA.WCHAMPIONS", "Ligue des champions féminine"))
    assert club_class("Chelsea Women")[2] == "women"
    assert club_class("Chelsea Women")[1] < club_class("Chelsea")[1]
    assert fixture.importance > 148
    assert "equipe_jeunes_reserve=-60" not in fixture.importance_reasons
    assert squad_category("Chelsea", "ES:UEFA.WCHAMPIONS") == "women"


def test_grand_club_names_are_exact_with_common_aliases():
    for name in ("PSG", "Paris Saint-Germain", "Paris St-Germain", "Paris SG"):
        assert club_class(name)[0] == "paris saint germain"
    assert club_class("FC Bayern München")[0] == "bayern"
    assert club_class("Man City")[0] == "manchester city"
    assert club_class("Auckland City")[0] == ""


def test_major_derbies_and_big_match_bonus():
    classic = importance(f("Real Madrid", "FC Barcelona"))
    ordinary = importance(f("Real Madrid", "Getafe"))
    assert classic.importance > ordinary.importance + 70
    assert "derby_reconnu=75" in classic.importance_reasons
    assert "deux_grands_clubs=28" in classic.importance_reasons
    assert "derby_reconnu=75" in importance(f("Paris Saint-Germain", "Marseille")).importance_reasons
    assert "derby_reconnu=75" in importance(f("Wydad AC", "Raja Casablanca")).importance_reasons


def test_finals_and_knockout_stages_have_explicit_tiers():
    base = f("Atalanta", "Villarreal", "ES:UEFA.CHAMPIONS", "Ligue des champions")
    def make(stage):
        from dataclasses import replace
        return importance(replace(base, stage=stage))
    assert make("FINAL").importance > make("SEMI_FINALS").importance > \
           make("QUARTER_FINALS").importance > make("LAST_16").importance > \
           make("REGULAR_SEASON").importance
    assert "tour_final=225" in make("FINAL").importance_reasons
    assert stage_class("round of 16") == "LAST_16"


def test_priority_competitions_above_secondary_trophy_and_country_pool():
    premier = importance(f("Everton", "Fulham", "ES:ENG.1"))
    trophy = importance(f("Everton", "Fulham", "ES:ENG.TROPHY"))
    champions = importance(f("Everton", "Fulham", "ES:UEFA.CHAMPIONS"))
    assert champions.importance > premier.importance > trophy.importance
    assert "uefa.champions" in ALLOWED and "eng.1" in ALLOWED
    assert "esp.1" in ALLOWED and "uefa.wchampions" in ALLOWED


def test_national_teams_are_distinct_from_club_tiers():
    fixture = importance(f("France", "Argentina", "ES:FIFA.WORLD", "World Cup"))
    assert "deux_grands_clubs=28" in fixture.importance_reasons
    assert squad_category("France", "ES:FIFA.WORLD") == "national"
    assert club_class("France")[1] == 0


def test_espn_structured_final_stage_without_guessing():
    def event(note):
        return {"id": "123456", "date": "2026-11-13T20:00:00Z",
                "status": {"type": {"completed": False, "name": "STATUS_SCHEDULED"}},
                "competitions": [{"notes": [{"headline": note}], "competitors": [
                    {"homeAway": "home", "team": {"id": "1", "displayName": "Chelsea"}},
                    {"homeAway": "away", "team": {"id": "2", "displayName": "Arsenal"}},
                ]}]}
    for note, expected in (
        ("Final", "FINAL"), ("Semifinals", "SEMI_FINALS"),
        ("Quarterfinals", "QUARTER_FINALS"), ("Round of 16", "LAST_16"),
        ("Final round of league phase", "REGULAR_SEASON"),
    ):
        _, item = parse_event(event(note), "uefa.champions", now=NOW)
        assert item.stage == expected
    _, standard = parse_event(event("1st Leg"), "uefa.champions", now=NOW)
    assert standard.stage == "REGULAR_SEASON"
    _, unknown = parse_event(event("Matchday 31"), "uefa.champions", now=NOW)
    assert unknown.stage == "REGULAR_SEASON"


def test_diversity_prefers_multiple_leagues_then_fills_without_fakes():
    fixtures = [f("Real Madrid", "Barcelona", competition="ES:ESP.1", num=i) for i in range(1, 8)]
    fixtures += [f("Manchester City", "Liverpool", competition="ES:ENG.1", num=i) for i in range(8, 13)]
    selected = diverse_ranked(fixtures, limit=10, max_per_league=4)
    assert len(selected) == 10
    assert len({x.id for x in selected}) == 10
    assert sum(m.competition == "ES:ENG.1" for m in selected) >= 4
    assert len(diverse_ranked(fixtures[:3], limit=10)) == 3


def test_stable_pre_match_editorial_rank_ignores_scores():
    fixture = f("Liverpool U21", "Chelsea", "ES:ENG.TROPHY")
    x = importance(fixture)
    y = importance(fixture)
    assert x.importance == y.importance and x.importance_reasons == y.importance_reasons
    assert len(rank_fixtures([f("Real Madrid", "Barcelona"), fixture])) == 2
