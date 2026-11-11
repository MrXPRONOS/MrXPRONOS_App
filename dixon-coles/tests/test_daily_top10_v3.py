"""Top10 V3: source activation, tier fill, strict/flexible output, and no-fake safeguards."""
from datetime import datetime, timedelta, timezone
from collections import Counter
import pytest

from dcscore.daily_espn import ALLOWED, CANDIDATES, ENABLED, ESPNProvider
from dcscore.daily_rank import RankedFixture, importance, select_tiered, popularity_tier
from dcscore.daily_pipeline import run_daily
from dcscore.domain import Match
from dcscore.model import DCModel
from dcscore.video_render import validate_payload
from dcscore.video_grid_neon import positions

NOW=datetime(2026,11,11,20,tzinfo=timezone.utc)
DAY=(NOW+timedelta(days=1)).date()
TEAM=("t0","t1","t2","t3")
CREST="https://a.espncdn.com/i/teamlogos/soccer/500/100.png"


def f(idx,home="Arsenal",away="Chelsea",league="ES:ENG.1"):
    return RankedFixture(
        id=f"{league}:{idx}",competition=league,
        competition_name="Premier League", kickoff=NOW+timedelta(days=1,hours=idx%5),
        home_id=TEAM[idx%4],away_id=TEAM[(idx+1)%4],
        home_name=home,away_name=away,stage="REGULAR_SEASON",
        source="ESPN public scoreboard",source_verified=True,
        neutral_venue=False,home_logo_url=CREST,away_logo_url=CREST)


def training():
    return [Match(
        id=f"hist{i}",competition="ES:ENG.1",kickoff=NOW-timedelta(days=100-i),
        home_id=TEAM[i%4],away_id=TEAM[(i+1)%4],
        home_name="Home",away_name="Away",status="FINISHED",home_goals=i%3,
        away_goals=(i+1)%2,source="test") for i in range(100)]


class Provider:
    name="ESPN public scoreboard"
    source_verified=True
    def __init__(self, fixtures):
        self.fixtures=fixtures
        self.discovery_counts={"ESPN/eng.1":len(fixtures)}
    def discover(self,day,now):
        return self.fixtures, []
    def history(self,fixture,now):
        return training(), []


def fake_fit(rows, *, as_of, **kw):
    assert all(m.kickoff<as_of for m in rows)
    return DCModel(
        teams=TEAM,alpha={x:1.0 for x in TEAM},
        beta={x:1.0 for x in TEAM},gamma=1.08,rho=0.,xi=.0065,
        trained_at=as_of,first_game=rows[0].kickoff,last_game=rows[-1].kickoff,
        n_games=len(rows),log_likelihood=-90.,optimizer_message="test")


def test_candidate_catalog_not_mistaken_for_enabled_competitions():
    assert len(ALLOWED)>=45
    assert len(CANDIDATES)>=15
    assert len(ENABLED)==31
    assert not (set(CANDIDATES)&set(ENABLED))
    assert 'eng.2' in CANDIDATES  # annual scoreboards were capped at 400
    assert 'por.1' in ENABLED and 'bra.1' in ENABLED
    assert 'egy.1' not in ENABLED
    assert ESPNProvider().leagues==ENABLED
    assert ESPNProvider(leagues=["por.1"]).leagues==("por.1",)


def test_tier_a_b_c_and_diversity_then_filling():
    a=f(0,"Arsenal","Chelsea")
    b=f(1,"Arsenal","Small Town")
    c=f(2,"Village United","Small Town")
    assert popularity_tier(importance(a).importance)=="A"
    assert popularity_tier(importance(b).importance)=="B"
    assert popularity_tier(importance(c).importance)=="C"
    fixtures=[f(i,"Arsenal","Chelsea") for i in range(7)]
    fixtures+= [f(i,"Town","Village",league="ES:GER.1") for i in range(8,14)]
    selected=select_tiered(fixtures,limit=10,max_per_league=4)
    assert len(selected)==10 and len({m.id for m in selected})==10
    counts=Counter(m.competition for m in selected)
    assert counts["ES:ENG.1"]>=4
    assert counts["ES:GER.1"]>=3


def test_shortfall_is_reported_without_creating_fake_matches(monkeypatch):
    monkeypatch.setattr("dcscore.daily_pipeline.fit",fake_fit)
    matches=[f(0),f(1,"Arsenal","Small Town"),f(2,"Town","Village")]
    strict=run_daily(Provider(matches),day=DAY,as_of=NOW,limit=10,
                     min_importance=70,min_team=4,max_staleness_days=35)
    assert strict["selected_count"]==3
    assert strict["daily_shortfall"]==7
    assert strict["ready_for_video"] is False
    assert strict["status"]=="PARTIAL"
    assert strict["selection_diagnostics"]["selected_by_tier"]=={"A":1,"B":1,"C":1}
    assert strict["selection_diagnostics"]["shortfall"]==7
    assert strict["publication_mode"]=="strict"
    assert len(strict["video_payload"]["clips"])==3


def test_flexible_mode_ready_only_for_nonempty_verified_match_list(monkeypatch):
    monkeypatch.setattr("dcscore.daily_pipeline.fit",fake_fit)
    forecast=run_daily(Provider([f(i) for i in range(3)]),
        day=DAY,as_of=NOW,limit=10,min_importance=70,min_team=4,
        max_staleness_days=35,publication_mode="flexible")
    assert forecast["ready_for_video"] is True
    assert forecast["status"]=="READY" and forecast["selected_count"]==3
    assert forecast["daily_shortfall"]==7
    assert forecast["video_payload"]["clips"]
    empty=run_daily(Provider([]),day=DAY,as_of=NOW,limit=10,min_importance=70,
                    publication_mode="flexible")
    assert empty["ready_for_video"] is False


def test_source_uncertainty_and_history_are_not_bypassed(monkeypatch):
    monkeypatch.setattr("dcscore.daily_pipeline.fit",fake_fit)
    bad=f(0)
    from dataclasses import replace
    missing=replace(bad,home_logo_url=None)
    forecast=run_daily(Provider([missing]),day=DAY,as_of=NOW,limit=10,
        min_importance=70,min_team=4,max_staleness_days=35,
        publication_mode="flexible")
    assert not forecast["ready_for_video"]
    assert any("Logos" in s for s in forecast["reasons_not_ready"])


def test_neon_dynamic_slots_and_strict_payload_guard():
    assert len(positions(1))==1
    assert len(positions(7))==7
    assert len(positions(10))==10
    with pytest.raises(ValueError):
        positions(11)
    with pytest.raises(ValueError):
        validate_payload({"clips":[]},preview=True)
    # Partial preview/production must be explicitly requested.
    preview={"clips":[{"headline":"Arsenal - Chelsea","display_score":"1-0"}]}
    with pytest.raises(ValueError):
        validate_payload(preview,preview=True)
    assert len(validate_payload(preview,preview=True,
                 allow_partial_preview=True))==1


def test_flexible_production_validator_checks_date_and_counts():
    from datetime import date
    from dcscore.domain import iso_date
    now=datetime.now(timezone.utc)
    target=(now.date()+timedelta(days=1)).isoformat()
    clips=[{"headline":"Arsenal - Chelsea","display_score":"1-1",
           "home_logo_url":CREST,"away_logo_url":CREST,
           "kickoff_utc":iso_date(now+timedelta(days=1,hours=4))}]
    payload={"date_local_africa_lome":target,"generated_at_utc":iso_date(now),
             "status":"READY","ready_for_video":True,
             "selected_count":1,"publication_mode":"flexible","clips":clips}
    with pytest.raises(ValueError,match="10 matchs"):
        validate_payload(payload)
    assert len(validate_payload(payload,allow_partial_production=True))==1
    payload["selected_count"]=2
    with pytest.raises(ValueError):
        validate_payload(payload,allow_partial_production=True)


def test_invalid_publishing_mode_is_rejected_before_network():
    with pytest.raises(ValueError,match="strict ou flexible"):
        run_daily(Provider([]),day=DAY,as_of=NOW,publication_mode="always")


def test_renderable_gate_fills_with_next_valid_fixture(monkeypatch):
    from dataclasses import replace
    monkeypatch.setattr("dcscore.daily_pipeline.fit",fake_fit)
    # These top-ranked events have an invalid crest or unverified provider.
    first=replace(f(0),home_logo_url=None)
    second=replace(f(1),source_verified=False)
    third=replace(f(2),stage="FINAL",neutral_venue=None)
    fallback=f(3,"Arsenal","Small Town")
    result=run_daily(Provider([first,second,third,fallback]),
        day=DAY,as_of=NOW,limit=10,min_importance=70,min_team=4,
        max_staleness_days=35,publication_mode="flexible",
        require_renderable=True)
    assert result["selected_count"]==1
    assert result["selected"][0]["id"]==fallback.id
    assert result["ready_for_video"] is True
    assert result["selection_diagnostics"]["rejected_by_reason"]["logos_invalides"]==1
    assert result["selection_diagnostics"]["rejected_by_reason"]["calendrier_non_verifie"]==1
    assert result["selection_diagnostics"]["rejected_by_reason"]["terrain_finale_non_confirme"]==1
    # Original predictor functionality is unmodified unless explicitly requested.
    legacy=run_daily(Provider([first,second,third,fallback]),
        day=DAY,as_of=NOW,limit=10,min_importance=70,min_team=4,
        max_staleness_days=35,publication_mode="flexible")
    assert legacy["selected_count"]==4 and legacy["ready_for_video"] is False
