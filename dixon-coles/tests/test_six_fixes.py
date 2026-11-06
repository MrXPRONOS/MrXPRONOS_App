"""Regression gates for the six deficiencies identified in the independent scorer."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone, timedelta
import sqlite3

import pytest
from fastapi.testclient import TestClient

from dcscore.api import create_app
from dcscore.domain import Match
from dcscore.model import fit, forecast
from dcscore.service import backtest
from dcscore.sources import parse_csv
from dcscore.store import Store


def game(id="g1", status="FINISHED", score=(2,1), **options):
    return Match(id=id, competition="csv:TEST", kickoff=datetime(2025,1,1,tzinfo=timezone.utc),
                 home_id="a",away_id="b",home_name="A",away_name="B",
                 status=status,home_goals=score[0] if status=="FINISHED" else None,
                 away_goals=score[1] if status=="FINISHED" else None,
                 source="csv",**options)


def test_01_finished_never_downgraded_or_silently_rewritten(teststore):
    final=game()
    teststore.upsert_matches([final])
    teststore.upsert_matches([game(status="SCHEDULED")])
    actual=teststore.get_match("g1")
    assert actual.status=="FINISHED" and (actual.home_goals,actual.away_goals)==(2,1)
    assert actual.result_provenance=="csv_import"
    with pytest.raises(ValueError,match="correction explicite"):
        teststore.upsert_matches([game(score=(0,0))])
    assert teststore.get_match("g1").home_goals==2


def test_01_atomic_batch_rollback_and_identity(teststore):
    teststore.upsert_matches([game()])
    good=replace(game(),id="new")
    with pytest.raises(ValueError):
        teststore.upsert_matches([good,game(score=(3,3))])
    assert teststore.get_match("new") is None
    with pytest.raises(ValueError,match="identité"):
        teststore.upsert_matches([replace(game(),away_id="evil")])


def test_01_explicit_correction_is_audited_and_preserved(teststore):
    teststore.upsert_matches([game()])
    with pytest.raises(ValueError,match="justification"):
        teststore.correct_final_result("g1",1,1,reason="oops")
    m=teststore.correct_final_result("g1",1,1,reason="Score confirmé après publication de la feuille officielle")
    assert m.result_provenance=="manual_correction"
    assert (m.home_goals,m.away_goals)==(1,1)
    with pytest.raises(ValueError,match="correction explicite"):
        teststore.upsert_matches([game()])  # stale original provider
    assert teststore.get_match("g1").home_goals==1
    history=teststore.result_history("g1")
    assert len(history)==1 and history[0]["previous_score"]=="2-1"
    assert history[0]["new_score"]=="1-1"


def test_01_existing_sqlite_database_is_migrated(tmp_path):
    path=str(tmp_path/"legacy.sqlite")
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE matches (id TEXT PRIMARY KEY, competition TEXT NOT NULL,
            kickoff TEXT NOT NULL,home_id TEXT NOT NULL,away_id TEXT NOT NULL,
            home_name TEXT NOT NULL,away_name TEXT NOT NULL,status TEXT NOT NULL,
            home_goals INTEGER,away_goals INTEGER,season TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL,updated_at TEXT NOT NULL)""")
        db.execute("""INSERT INTO matches VALUES ('old','csv:TEST','2025-01-01T00:00:00Z',
            'a','b','A','B','FINISHED',1,0,'2024','csv','2025-01-02T00:00:00Z')""")
    old=Store(path).get_match("old")
    assert old.neutral_venue is False and old.result_provenance=="csv_import"
    assert old.home_goals==1


def test_02_public_mode_requires_strong_token_and_auth_all_api(teststore,monkeypatch):
    monkeypatch.setenv("DCSCORE_PUBLIC_MODE","1")
    monkeypatch.delenv("DCSCORE_ADMIN_TOKEN",raising=False)
    with pytest.raises(RuntimeError,match="32"):
        create_app(teststore)
    token="a"*40
    monkeypatch.setenv("DCSCORE_ADMIN_TOKEN",token)
    with TestClient(create_app(teststore)) as client:
        assert client.get("/api/health").status_code==200
        assert client.get("/api/competitions").status_code==401
        assert client.post("/api/demo").status_code==401
        headers={"Authorization":"Bearer "+token}
        assert client.get("/api/competitions",headers=headers).status_code==200
        assert client.post("/api/demo",headers=headers).status_code==200
        assert client.post("/api/demo",headers={**headers,"Origin":"https://attacker.example"}).status_code==403
        assert client.post("/api/demo",headers={**headers,"Sec-Fetch-Site":"cross-site"}).status_code==403
        assert client.get("/api/predictions",headers=headers).headers["Cache-Control"]=="no-store"


def test_06_provenance_and_neutral_csv_import(teststore):
    content=("date,home_team,away_team,home_goals,away_goals,competition,neutral_venue\n"
             "2025-01-01,A,B,2,1,ZZ,oui\n").encode()
    m=parse_csv(content)[0]
    assert m.neutral_venue is True and m.result_provenance=="csv_import"
    teststore.upsert_matches([m])
    restored=teststore.get_match(m.id)
    assert restored.neutral_venue and restored.result_provenance=="csv_import"
    with pytest.raises(ValueError,match="Terrain neutre"):
        parse_csv(content.replace(b"oui",b"unknown"))


def test_06_neutral_prediction_switches_off_gamma(demo_store):
    history=demo_store.matches("demo:SIM",finished=True)
    model=fit(history,as_of=datetime.now(timezone.utc),min_games=80)
    a,b=history[0].home_id,history[0].away_id
    normal=forecast(model,a,b)
    neutral=forecast(model,a,b,neutral_venue=True)
    assert neutral["neutral_venue"] is True
    assert neutral["effective_home_multiplier"] == 1.
    assert neutral["expected_home_goals"] == pytest.approx(normal["expected_home_goals"]/model.gamma)
    assert normal["expected_away_goals"] == pytest.approx(neutral["expected_away_goals"])


def test_04_poisson_retrained_and_monthly_leakage_protected(demo_store):
    r=backtest(demo_store,"demo:SIM",n_samples=4)
    assert r["n_evaluated"]==4
    assert "mean_poisson_independent_log_loss" in r
    assert r["n_folds"]>=1
    assert all(f["last_training_match"]<f["start"] for f in r["folds"])
    assert sum(x["n"] for x in r["top1_confidence_buckets"])==r["n_evaluated"]
    assert 0<=r["mean_one_x_two_brier"]<=2.
    assert "réentraîné indépendamment" in r["baseline_note"]


def test_03_real_source_has_distinct_provenance():
    from dcscore.openfootball import parse_openfootball_season
    payload={"matches":[{"date":"2024-08-16","time":"20:00","team1":"A FC",
                         "team2":"B FC","score":{"ft":[1,0]}}]}
    rows=parse_openfootball_season(payload,"2024-25",as_of=datetime(2026,11,6,tzinfo=timezone.utc))
    assert len(rows)==1 and rows[0].result_provenance=="community_reported"
    assert rows[0].source=="openfootball/football.json"


def test_05_real_xi_report_is_packaged_and_auto_available(teststore):
    r=teststore.latest_xi_calibration("of:ENG-PL")
    assert r is not None
    assert r["n_scored"]>=100
    assert r["selected_xi"] in [x["xi"] for x in r["candidate_results"]]
    assert r["holdout_not_used_for_selection"]["n_tested"]>100
    assert r["data_source"]==["openfootball/football.json"]


def test_06_venue_correction_requires_reason_and_is_audited(teststore):
    teststore.upsert_matches([game()])
    with pytest.raises(ValueError,match="Justification"):
        teststore.set_neutral_venue("g1",True,reason="oops")
    corrected=teststore.set_neutral_venue("g1",True,
        reason="Terrain neutre confirmé dans le rapport de match")
    assert corrected.neutral_venue
    assert teststore.venue_history("g1")[0]["old_neutral"]==0
    assert teststore.venue_history("g1")[0]["new_neutral"]==1
    teststore.upsert_matches([game()])
    assert teststore.get_match("g1").neutral_venue


def test_04_more_than_30_predictions_and_independent_model(demo_store):
    r=backtest(demo_store,"demo:SIM",n_samples=40)
    assert r['n_evaluated']==40
    assert r['n_folds']>=2
    assert all(x['result_provenance']=='synthetic_demo' for x in r['detailed'])
    assert r['mean_poisson_baseline_log_loss']==r['mean_poisson_independent_log_loss']
