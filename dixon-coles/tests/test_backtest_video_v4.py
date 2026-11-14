"""Regression for V4 score-source isolation and 31-day matched V3/V4 reports."""
import json
from datetime import date, datetime, timezone, timedelta

import pytest

from dcscore.backtest_video_v4 import (
    retrospectively_unplayed, prediction_row, statistics,
)
from dcscore.combine_backtest_video_v4 import merge


def _finished_event():
    return {
        "id":"401000000","date":"2026-10-15T18:00:00Z",
        "status":{"type":{"name":"STATUS_FINAL","completed":True}},
        "competitions":[{"competitors":[
            {"homeAway":"home","score":"5","team":{"id":"1","displayName":"Home"}},
            {"homeAway":"away","score":"0","team":{"id":"2","displayName":"Away"}},
        ]}],
    }


def test_score_and_terminal_status_removed_from_prediction_input():
    completed=_finished_event()
    fixture=retrospectively_unplayed(completed)
    assert completed["status"]["type"]["completed"] is True
    assert fixture["status"]["type"]["completed"] is False
    assert fixture["status"]["type"]["name"]=="STATUS_SCHEDULED"
    assert all("score" not in team for team in fixture["competitions"][0]["competitors"])
    assert completed["competitions"][0]["competitors"][0]["score"]=="5"


def test_exact_score_evaluation_uses_only_separate_truth():
    prediction={
        "id":"match-1","competition_name":"Premier League","home":"A","away":"B",
        "importance":220,"importance_reasons":["big clubs"],
        "competition_code":"ES:ENG.1","stage":"REGULAR_SEASON",
        "popularity_tier":"A","home_team_category":"senior",
        "away_team_category":"senior","kickoff_utc":"2026-10-15T18:00:00Z",
        "home_logo_url":"https://a.espncdn.com/i/teamlogos/soccer/500/111.png",
        "away_logo_url":"https://a.espncdn.com/i/teamlogos/soccer/500/222.png",
        "forecast":{"most_likely_score":"1-0","most_likely_probability":.19,
                    "top_5":[{"score":s,"probability":.19-i*.02}
                             for i,s in enumerate(("1-0","2-0","1-1","2-1","0-0"))],
                    "outcomes_1x2":{"home":.7,"draw":.2,"away":.1}},
        "training_matches":99,"training_last_result":"2026-10-14T18:00:00Z",
        "result_age_days":1,
    }
    row=prediction_row(prediction,(5,0),date(2026,10,15))
    assert row["predicted_exact"]=="1-0"
    assert row["real_exact"]=="5-0"
    assert row["top1_hit"]==0
    assert row["one_x_two_hit"]==1
    assert row["has_valid_logo_urls"] is True


def _empty_report(days):
    return {
        "days":[{"date":d,"discovered":0,"eligible":0,"selected":0,
                 "ready_for_video":False,"flexible_video_possible":False,
                 "selection_changed":False,"v4_renderable_rejections":0,
                 "source_warnings":[]} for d in days],
        "paired_v3_days":[{"date":d,"discovered":0,"eligible":0,"selected":0,
                           "ready_for_video":False,"flexible_video_possible":False}
                          for d in days],
        "matches":[],"paired_v3_matches":[],
        "data_quality":{"source_warnings_count":0,"source_warnings_examples":[]},
        "status":"NO_VERIFIABLE_BACKTEST_SAMPLE",
    }


def _five_parts(tmp_path,duplicate=False):
    first=date(2026,10,1)
    segments=[7,7,7,7,3]
    cursor=first
    for i,n in enumerate(segments):
        days=[]
        for _ in range(n):
            days.append(cursor.isoformat())
            cursor+=timedelta(days=1)
        if duplicate and i==4:
            days[-1]=days[0]
        directory=tmp_path/f"part-{i}"
        directory.mkdir()
        (directory/"backtest_oct2026_v4.json").write_text(
            json.dumps(_empty_report(days)),encoding="utf-8")


def test_aggregation_audits_31_days_and_zero_denominator(tmp_path):
    _five_parts(tmp_path)
    out=tmp_path/"final"
    data=merge(tmp_path,out)
    assert data["comparison"]["matched_calendar_days"]==31
    assert data["stats"]["results_observed"]==0
    assert data["status"]=="NO_VERIFIABLE_BACKTEST_SAMPLE"
    assert (out/"synthese_backtest_v4_octobre_2026.md").is_file()


def test_aggregation_rejects_duplicate_days(tmp_path):
    _five_parts(tmp_path,duplicate=True)
    with pytest.raises(ValueError,match="dates missing or duplicated"):
        merge(tmp_path,tmp_path/"final")
