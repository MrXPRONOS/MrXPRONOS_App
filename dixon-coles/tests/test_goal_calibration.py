"""Deterministic tests: no lookahead, coherent scores, no arbitrary high-goal patch."""
from datetime import datetime, timedelta, timezone

import pytest
from dcscore.domain import Match
from dcscore.model import DCModel, ModelError, forecast
from dcscore.goal_calibration import select_goal_multiplier, GoalCalibration


CUTOFF = datetime(2026, 10, 1, 20, tzinfo=timezone.utc)


def _toy_model():
    return DCModel(
        teams=("a","b","c","d"),
        alpha={"a":1.0,"b":1.0,"c":1.0,"d":1.0},
        beta={"a":1.0,"b":1.0,"c":1.0,"d":1.0},
        gamma=1.0, rho=0.0, xi=0.0065, trained_at=CUTOFF,
        first_game=CUTOFF-timedelta(days=500),
        last_game=CUTOFF-timedelta(days=1),
        n_games=100, log_likelihood=-100.0, optimizer_message="test")


def test_default_forecast_is_unchanged_and_probability_mass_is_valid():
    model=_toy_model()
    baseline=forecast(model,"a","b")
    unchanged=forecast(model,"a","b",goal_multiplier=1.0)
    assert baseline["top_scores"] == unchanged["top_scores"]
    assert baseline["one_x_two"] == unchanged["one_x_two"]
    assert unchanged["raw_expected_home_goals"] == 1.
    assert unchanged["goal_multiplier"] == 1.
    for factor in (0.85,1.2):
        result=forecast(model,"a","b",goal_multiplier=factor)
        assert result["expected_home_goals"] == pytest.approx(factor)
        assert result["expected_away_goals"] == pytest.approx(factor)
        assert sum(result["one_x_two"].values()) == pytest.approx(1,abs=1e-5)
        assert sum(result["matrix_0_6"][0]) > 0
        assert all(0<=x["probability"]<=1 for x in result["top_scores"])


def test_out_of_bounds_or_nan_multiplier_fails_closed():
    model=_toy_model()
    for bad in (0.,0.70,1.21,float("nan"),float("inf")):
        with pytest.raises(ModelError):
            forecast(model,"a","b",goal_multiplier=bad)


def _sample_history(validation_home=2, validation_away=2):
    rows=[]
    for day in range(500,0,-1):
        when=CUTOFF-timedelta(days=day)
        if day>240:
            h,a=1,1
        elif day>60:
            h,a=2,2
        else:
            h,a=validation_home,validation_away
        rows.append(Match(
            id=f"toy:{day}",competition="ES:ESP.1",kickoff=when,
            home_id="a",away_id="b",home_name="A",away_name="B",
            status="FINISHED",home_goals=h,away_goals=a,
            source="csv",neutral_venue=False))
    return rows


def test_calibration_is_accepted_only_after_disjoint_later_validation(monkeypatch):
    seen=[]
    def fake_fit(rows,*,as_of,**kwargs):
        assert all(m.kickoff < as_of for m in rows), "Future leakage"
        seen.append((as_of, {m.id for m in rows}))
        return _toy_model()
    monkeypatch.setattr("dcscore.goal_calibration.fit",fake_fit)
    rows=_sample_history()
    result=select_goal_multiplier(rows,as_of=CUTOFF)
    assert result.status=="VALIDATED_ADJUSTMENT"
    assert 1.0 < result.multiplier <= 1.2
    assert result.validation_candidate_nll < result.validation_baseline_nll
    assert len(seen)==2
    assert seen[0][0] == CUTOFF-timedelta(days=240)
    assert seen[1][0] == CUTOFF-timedelta(days=60)
    assert len(seen[0][1] & seen[1][1])==len(seen[0][1])


def test_bad_september_validation_rejects_goal_boost(monkeypatch):
    monkeypatch.setattr("dcscore.goal_calibration.fit",lambda *args, **kwargs:_toy_model())
    rows=_sample_history(validation_home=0,validation_away=0)
    result=select_goal_multiplier(rows,as_of=CUTOFF)
    assert result.status == "BASELINE_VALIDATION_REJECTED"
    assert result.estimate > 1.
    assert result.multiplier == 1.0


def test_history_after_as_of_is_ignored(monkeypatch):
    monkeypatch.setattr("dcscore.goal_calibration.fit",lambda *args, **kwargs:_toy_model())
    before=_sample_history()
    result=select_goal_multiplier(before,as_of=CUTOFF)
    after=Match(id="future",competition="ES:ESP.1",
                kickoff=CUTOFF+timedelta(days=1),home_id="a",away_id="b",
                home_name="A",away_name="B",status="FINISHED",home_goals=17,away_goals=16,
                source="csv")
    assert select_goal_multiplier(before+[after],as_of=CUTOFF)==result


def test_small_sample_falls_back_to_original_forecast():
    rows=_sample_history()[:105]
    c=select_goal_multiplier(rows,as_of=CUTOFF)
    assert c.multiplier==1.0
    assert c.status=="BASELINE_INSUFFICIENT_HISTORY"
