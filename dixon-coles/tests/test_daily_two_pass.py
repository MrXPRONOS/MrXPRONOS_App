"""V5: genuine two-pass Top10, including zero-history or unknown-team forecasts.

No fabricated fixtures, results, identities or training matches. The published
video pipeline and visual layout are intentionally outside the scope.
"""
from datetime import datetime, timedelta, timezone
from dataclasses import replace

import pytest

from dcscore.daily_pipeline import run_daily
from dcscore.daily_rank import RankedFixture
from dcscore.domain import Match
from dcscore.fallback_model import cold_start_model
from dcscore.model import forecast, DCModel
from dcscore.daily_espn import ESPNProvider, CANDIDATES

NOW=datetime(2026,11,11,20,tzinfo=timezone.utc)
DAY=(NOW+timedelta(days=1)).date()
CREST="https://a.espncdn.com/i/teamlogos/soccer/500/123.png"
TEAMS=tuple(f"t{i}" for i in range(4))


def fixture(i, comp="ES:ENG.1", home="Arsenal", away="Chelsea"):
    return RankedFixture(
        id=f"{comp}:{i}",competition=comp,
        competition_name="First division" if comp=="ES:ENG.1" else "EFL Trophy",
        kickoff=NOW+timedelta(days=1,hours=i%6),home_id=TEAMS[i%4],
        away_id=TEAMS[(i+1)%4],home_name=home,away_name=away,
        stage="REGULAR_SEASON",source="ESPN public scoreboard",
        source_verified=True,neutral_venue=False,
        home_logo_url=CREST,away_logo_url=CREST)


def history():
    return [Match(id=f"hist-{i}",competition="ES:ENG.1",
                  kickoff=NOW-timedelta(days=105-i),home_id=TEAMS[i%4],
                  away_id=TEAMS[(i+1)%4],
                  home_name="Home",away_name="Away",
                  status="FINISHED",home_goals=i%3,away_goals=i%2,
                  source="espn-reported",result_provenance="provider_reported")
            for i in range(100)]


def fitted(rows, *, as_of, **kwargs):
    assert all(r.kickoff < as_of for r in rows)
    return DCModel(teams=TEAMS,alpha={x:1.0 for x in TEAMS},
                   beta={x:1.12 for x in TEAMS},gamma=1.11,rho=0,
                   xi=.0065,trained_at=as_of,first_game=rows[0].kickoff,
                   last_game=rows[-1].kickoff,n_games=len(rows),
                   log_likelihood=-100,optimizer_message="test")


class Provider:
    name="ESPN public scoreboard"
    def __init__(self,fixtures,extra=()):
        self.main=list(fixtures)
        self.extra=list(extra)
        self.discovery_counts={}
        self.history_requests=[]
        self.expansions=0
    def discover(self,day,now):
        assert day==DAY
        self.discovery_counts={"main":len(self.main)}
        return self.main,[]
    def discover_more(self,day,now):
        self.expansions+=1
        self.discovery_counts["extra"]=len(self.extra)
        return self.extra,[]
    def history(self,match,now):
        self.history_requests.append(match.competition)
        return (history() if match.competition=="ES:ENG.1" else []),[]


def execute(monkeypatch,source,**kw):
    monkeypatch.setattr("dcscore.daily_pipeline.fit",fitted)
    return run_daily(source,day=DAY,as_of=NOW,limit=10,
                     min_games=80,min_team=4,max_staleness_days=35,
                     min_importance=70,publication_mode="strict",
                     require_renderable=True,**kw)


def test_second_pass_reaches_ten_when_older_minimums_are_only_blocker(monkeypatch):
    main=[fixture(i) for i in range(3)]
    unknown=[fixture(i+10,"ES:ENG.TROPHY",home="Local East",away="Local West")
             for i in range(12)]
    provider=Provider(main+unknown)
    result=execute(monkeypatch,provider)
    assert result["status"]=="READY"
    assert result["selected_count"]==10 and result["ready_for_video"] is True
    assert result["selection_diagnostics"]["first_pass_eligible"]==3
    assert result["selection_diagnostics"]["second_pass_selected"]==7
    assert [x["selection_pass"] for x in result["selected"][:3]]==["strict"]*3
    assert [x["selection_pass"] for x in result["selected"][3:]]==["fallback"]*7
    assert result["selection_diagnostics"]["day_has_ten_real_fixtures_discovered"]
    assert all(x["prediction_basis"]=="GENERIC_POISSON_PRIOR_NO_HISTORY"
               for x in result["selected"][3:])
    assert all(x["model"]=="untrained_poisson_prior_rho_zero"
               for x in result["selected"][3:])
    assert all(x["forecast"]["recommendation_status"]=="UNCALIBRATED_SECOND_PASS"
               for x in result["selected"][3:])
    assert len(result["video_payload"]["clips"])==10


def test_extra_league_lookup_only_when_strict_fails_and_keeps_order(monkeypatch):
    popular=[fixture(i) for i in range(3)]
    other=[fixture(i+200,"ES:ENG.TROPHY",home="Town",away="Village")
           for i in range(12)]
    provider=Provider(popular,other)
    result=execute(monkeypatch,provider)
    assert provider.expansions==1
    assert provider.discovery_counts["extra"]==12
    assert result["selected_count"]==10
    assert result["selection_diagnostics"]["second_pass_extra_competition_fixtures"]==12
    assert all(m["id"]==popular[i].id for i,m in enumerate(result["selected"][:3]))


def test_no_extra_source_request_when_initial_ten_verified(monkeypatch):
    provider=Provider([fixture(i) for i in range(12)],
                      [fixture(100,"ES:ENG.TROPHY")])
    report=execute(monkeypatch,provider)
    assert provider.expansions==0
    assert report["selection_diagnostics"]["second_pass_selected"]==0
    assert report["selected_count"]==10


def test_no_matches_remain_zero_instead_of_fabricating_ten(monkeypatch):
    report=execute(monkeypatch,Provider([]))
    assert report["status"]=="NO_ELIGIBLE_MATCHES"
    assert report["selected_count"]==0
    assert report["ready_for_video"] is False


def test_historyless_scores_exist_but_are_not_mislabeled_as_trained():
    match=fixture(0,"ES:ENG.TROPHY",home="Unknown A",away="Unknown B")
    model,meta=cold_start_model(match,[],as_of=NOW)
    actual=forecast(model,match.home_id,match.away_id)
    assert meta["basis"]=="GENERIC_POISSON_PRIOR_NO_HISTORY"
    assert meta["n_games"]==0
    assert model.rho==0 and model.n_games==0
    assert actual["top_scores"][0]["probability"]>0
    assert actual["top_scores"][0]["score"].count("-")==1
    assert abs(sum(actual["one_x_two"].values())-1)<1e-6


def test_sparse_prior_ignores_future_final_score():
    match=fixture(2,"ES:ENG.1")
    past=history()[:8]
    future=Match(id="future",competition="ES:ENG.1",
                 kickoff=NOW+timedelta(hours=8),home_id=match.home_id,
                 away_id=match.away_id,home_name="A",away_name="B",
                 status="FINISHED",home_goals=28,away_goals=0,
                 source="espn-reported",result_provenance="provider_reported")
    a,ameta=cold_start_model(match,past,as_of=NOW,allow_fit=False)
    b,bmeta=cold_start_model(match,past+[future],as_of=NOW,allow_fit=False)
    assert a.alpha==b.alpha and a.beta==b.beta and a.gamma==b.gamma
    assert ameta["n_games"]==bmeta["n_games"]==8


def test_partial_source_errors_cannot_generate_synthetic_fixtures(monkeypatch):
    main=[fixture(i) for i in range(3)]
    additional=[fixture(i+50,"ES:ENG.TROPHY") for i in range(10)]
    invalid=replace(additional[0],home_logo_url=None)
    fake=replace(additional[1],source_verified=False)
    postponed=replace(additional[2],kickoff=NOW-timedelta(minutes=10))
    provider=Provider(main,[invalid,fake,postponed]+additional[3:])
    report=execute(monkeypatch,provider)
    assert report["selected_count"]==10
    assert all(m["fixture_provider_reported"] for m in report["selected"])
    assert all(m["home_logo_url"] for m in report["selected"])
    assert all(m["kickoff_utc"]>NOW.isoformat().replace("+00:00","Z")
               for m in report["selected"])


def test_second_pass_can_be_disabled_for_legacy_comparison(monkeypatch):
    provider=Provider([fixture(i) for i in range(3)]
                      +[fixture(i+9,"ES:ENG.TROPHY") for i in range(10)])
    result=execute(monkeypatch,provider,second_pass=False)
    assert result["selected_count"]==3
    assert not result["ready_for_video"]
    assert provider.expansions==0
