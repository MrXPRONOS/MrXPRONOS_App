"""Daily pipeline safety checks: baseline default, explicit opt-in, safe fallbacks."""
from datetime import datetime, timedelta, timezone
from dcscore.daily_rank import RankedFixture
from dcscore.domain import Match
from dcscore.daily_pipeline import run_daily
from dcscore.goal_calibration import GoalCalibration
from dcscore.model import DCModel, ModelError

NOW=datetime(2026,11,10,20,tzinfo=timezone.utc)
DAY=(NOW+timedelta(days=1)).date()
TEAMS=("A","B","C","D")


def _history():
    out=[]
    for i in range(140):
        h=TEAMS[i%4];a=TEAMS[(i%4+1+i//4%3)%4]
        if h==a:a=TEAMS[(i+1)%4]
        out.append(Match(id=f"m{i}",competition="ES:ESP.1",
             kickoff=NOW-timedelta(days=141-i),home_id=h,away_id=a,
             home_name=h,away_name=a,status="FINISHED",
             home_goals=i%3,away_goals=(i+1)%3,source="csv"))
    return out


class Provider:
    name="test"
    source_verified=True
    def discover(self, day, now):
        return [RankedFixture(
            id="example",competition="ES:ESP.1",competition_name="Liga",
            kickoff=NOW+timedelta(hours=27),home_id="A",away_id="B",
            home_name="A",away_name="B",stage="REGULAR_SEASON",
            source="ESPN public scoreboard",source_verified=True,
            neutral_venue=False,
            home_logo_url="https://a.espncdn.com/i/teamlogos/soccer/500/111.png",
            away_logo_url="https://a.espncdn.com/i/teamlogos/soccer/500/222.png"), []
    def history(self, fixture, now):
        return _history(), []


def _fake_fit(rows, *, as_of, **kwargs):
    assert all(m.kickoff < as_of for m in rows)
    return DCModel(
        teams=TEAMS, alpha={x:1. for x in TEAMS},
        beta={x:1. for x in TEAMS}, gamma=1.1,
        rho=0.,xi=.0065,trained_at=as_of,
        first_game=rows[0].kickoff,last_game=rows[-1].kickoff,
        n_games=len(rows),log_likelihood=-123.,optimizer_message="test")


def test_pipeline_does_not_calibrate_laliga_without_explicit_opt_in(monkeypatch):
    monkeypatch.setattr("dcscore.daily_pipeline.fit",_fake_fit)
    def forbidden(*args, **kwargs):
        raise AssertionError("Goal calibration called when disabled")
    monkeypatch.setattr("dcscore.daily_pipeline.select_goal_multiplier",forbidden)
    result=run_daily(Provider(),day=DAY,as_of=NOW,limit=1,min_team=4,
                     min_importance=70,max_staleness_days=35)
    assert result["selected_count"]==1
    f=result["selected"][0]["forecast"]
    assert f["goal_calibration"]["multiplier"]==1.0
    assert f["goal_calibration"]["status"]=="BASELINE_CALIBRATION_DISABLED"
    assert f["uncalibrated_expected_goals"]==f["expected_goals"]
    assert 0<f["score_1_1_probability"]<1


def test_opted_in_laliga_uses_validated_scale_and_records_it(monkeypatch):
    monkeypatch.setattr("dcscore.daily_pipeline.fit",_fake_fit)
    def calibrated(rows, *, as_of):
        assert all(m.kickoff < as_of for m in rows)
        return GoalCalibration(multiplier=1.07,status="VALIDATED_ADJUSTMENT",
                               train_count=80,calibration_count=40,validation_count=20,
                               validation_baseline_nll=3.,validation_candidate_nll=2.9)
    monkeypatch.setattr("dcscore.daily_pipeline.select_goal_multiplier",calibrated)
    result=run_daily(Provider(),day=DAY,as_of=NOW,limit=1,min_team=4,
                     min_importance=70,max_staleness_days=35,
                     enable_goal_calibration=True)
    match=result["selected"][0]
    assert match["goal_calibration_status"]=="VALIDATED_ADJUSTMENT"
    assert match["goal_multiplier"]==1.07
    f=match["forecast"]
    assert f["expected_goals"]["home"]>f["uncalibrated_expected_goals"]["home"]
    assert f["expected_goals"]["away"]>f["uncalibrated_expected_goals"]["away"]


def test_unsafe_scaled_score_falls_back_to_unmodified_baseline(monkeypatch):
    monkeypatch.setattr("dcscore.daily_pipeline.fit",_fake_fit)
    monkeypatch.setattr(
        "dcscore.daily_pipeline.select_goal_multiplier",
        lambda *a, **kw: GoalCalibration(multiplier=1.12,status="VALIDATED_ADJUSTMENT"))
    from dcscore import daily_pipeline
    original=daily_pipeline.forecast
    def fake_forecast(*args, **kwargs):
        if kwargs.get("goal_multiplier",1.)>1.:
            raise ModelError("Unsafe adjusted rho")
        return original(*args, **kwargs)
    monkeypatch.setattr("dcscore.daily_pipeline.forecast",fake_forecast)
    result=run_daily(Provider(),day=DAY,as_of=NOW,limit=1,min_team=4,
                     min_importance=70,max_staleness_days=35,
                     enable_goal_calibration=True)
    assert result["selected_count"]==1
    match=result["selected"][0]
    assert match["goal_calibration_status"]=="BASELINE_CALIBRATION_FALLBACK"
    assert match["goal_multiplier"]==1.
