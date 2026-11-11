from copy import deepcopy
from datetime import date, datetime, timezone

from dcscore.backtest_top10_v3 import (
    RetrospectiveESPN, retrospectively_unplayed, prediction_row, statistics,
)
from dcscore.daily_rank import RankedFixture, rank_fixtures, diverse_ranked


def event(day="2026-10-15", *, completed=True, home=2, away=1):
    return {
        "id": "123450",
        "date": day + "T18:00:00Z",
        "status": {"type": {"completed": completed, "name": "STATUS_FINAL" if completed else "STATUS_SCHEDULED"}},
        "competitions": [{
            "competitors": [
                {"homeAway": "home", "team": {
                    "id": "111", "displayName": "Arsenal",
                    "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/111.png",
                }, "score": home},
                {"homeAway": "away", "team": {
                    "id": "222", "displayName": "Chelsea",
                    "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/222.png",
                }, "score": away},
            ],
        }],
    }


def test_final_results_are_stripped_before_retro_fixture_selection():
    old = event()
    view = retrospectively_unplayed(old)
    assert old["status"]["type"]["completed"] is True
    assert view["status"]["type"]["completed"] is False
    assert "score" not in view["competitions"][0]["competitors"][0]
    assert "score" not in view["competitions"][0]["competitors"][1]
    assert old["competitions"][0]["competitors"][0]["score"] == 2


def test_retro_provider_creates_future_fixture_and_separate_ground_truth():
    p = RetrospectiveESPN()
    p._fetch = lambda league, selector: [event()] if league == "uefa.wchampions" else []
    past = datetime(2026, 10, 14, 20, tzinfo=timezone.utc)
    games, warnings = p.discover(date(2026, 10, 15), past)
    assert warnings == []
    assert len(games) == 1
    assert games[0].kickoff > past
    assert games[0].home_name == "Arsenal"
    assert p.truth[games[0].id] == (2, 1)


def test_retro_history_does_not_train_on_future_result():
    p = RetrospectiveESPN()
    prior = event("2026-10-08")
    future = event("2026-10-15")
    future["id"] = "123451"
    p._fetch = lambda league, selector: [prior, future] if league == "uefa.wchampions" else []
    date_cutoff = datetime(2026, 10, 14, 20, tzinfo=timezone.utc)
    games, _ = p.discover(date(2026, 10, 15), date_cutoff)
    past, warnings = p.history(games[0], date_cutoff)
    assert warnings == []
    assert len(past) == 1
    assert past[0].kickoff < date_cutoff
    assert past[0].id.endswith("123450")


def test_production_popularity_ranking_is_not_post_match_scoring():
    start = datetime(2026, 10, 15, 18, tzinfo=timezone.utc)
    def fixture(number, a, b):
        return RankedFixture(str(number), "ES:UEFA.WCHAMPIONS", "Women UCL", start,
                             str(number*2), str(number*2+1), a, b, "REGULAR_SEASON",
                             "ESPN public scoreboard", True)
    fixtures = [fixture(1, "Lesser A", "Lesser B"),
                fixture(2, "Real Madrid", "Barcelona"),
                fixture(3, "Chelsea", "Arsenal")]
    ranked = rank_fixtures(fixtures)
    assert [f.id for f in ranked] == ["2", "3", "1"]
    assert [f.id for f in diverse_ranked(fixtures, limit=2, max_per_league=4)] == ["2", "3"]


def test_exact_score_rates_have_honest_denominators():
    d = {
        "id": "match", "competition_name": "Women UCL", "competition_code": "ES:UEFA.WCHAMPIONS",
        "stage": "REGULAR_SEASON", "popularity_class": "notable",
        "popularity_tier":"B",
        "home_team_category": "women", "away_team_category": "women", "home": "Arsenal",
        "away": "Chelsea", "importance": 220, "importance_reasons": ["club"],
        "kickoff_utc": "2026-10-15T18:00:00Z", "training_matches": 100,
        "training_last_result": "2026-10-13T00:00:00Z", "result_age_days": 2,
        "forecast": {
            "top_5": [{"score": s, "probability": 0.12 - i*.01}
                      for i,s in enumerate(["1-0", "2-1", "1-1", "0-0", "0-1"])],
            "most_likely_score": "1-0", "most_likely_probability": 0.12,
            "outcomes_1x2": {"home": 0.6, "draw": 0.2, "away": 0.2},
        },
    }
    row = prediction_row(d, (2, 1), date(2026, 10, 15))
    stats = statistics([row], [{"discovered": 1, "selected": 1,
                                "ready_for_video": False, "eligible": 1}])
    assert stats["top1_exact_hits"] == 0
    assert stats["top3_exact_hits"] == 1
    assert stats["top5_exact_hits"] == 1
    assert stats["one_x_two_hits"] == 1
    assert stats["video_ready_days"] == 0
    assert stats["expected_top1_hits_given_model_probabilities"] == 0.12


def test_v2_production_pool_and_youth_vs_senior_popularity():
    from dcscore.daily_espn import ALLOWED, ENABLED
    from dcscore.daily_rank import importance, RankedFixture
    assert len(ENABLED) >= 14
    assert len(ALLOWED) >= len(ENABLED)
    assert {"uefa.champions", "eng.1", "esp.1", "ita.1", "fra.1", "ger.1"}.issubset(ALLOWED)
    from datetime import datetime, timezone
    stamp=datetime(2026,10,6,18,tzinfo=timezone.utc)
    def fx(identifier, h, a, c):
        return RankedFixture(id=identifier,competition=c,competition_name="Test",kickoff=stamp,
                             home_id=identifier+"h",away_id=identifier+"a",home_name=h,
                             away_name=a,stage="REGULAR_SEASON",source="ESPN",source_verified=True)
    senior=importance(fx("a","Liverpool","Manchester United","ES:ENG.1"))
    youth=importance(fx("b","Liverpool U21","Manchester United U21","ES:ENG.TROPHY"))
    assert senior.importance > youth.importance
    assert "equipe_jeunes_reserve=-60" in youth.importance_reasons
