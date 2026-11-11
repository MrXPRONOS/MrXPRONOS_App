"""Daily flexible production contract, no real external social uploads."""
from __future__ import annotations
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from check_daily_flexible_manifest import validate_daily_manifest
from publish_social_exact_score_video import build_copy

DAY="2026-11-12"


def manifest(n:int,mode:str="flexible"):
    return {
        "schema":("mrx-dixon-coles-social-flex-v3" if mode=="flexible"
                  else "mrx-dixon-coles-social-top10-v1"),
        "publication_mode":mode,
        "status":"READY","ready_for_video":True,
        "target":DAY,
        "count":n,
        "video":f"social_exact_scores_out/{DAY}/social_exact_scores_{n}.mp4",
        "render_evidence":{
            "real_logo_instances":2*n,
            "placeholder_logo_instances":0,
            "resolution":"1080x1920",
        },
        "match_ids":[f"ESPN-{i}" for i in range(n)],
    }


@pytest.mark.parametrize("n",range(1,11))
def test_publisher_accepts_only_actual_1_to_10_match_count(n):
    m=manifest(n)
    assert validate_daily_manifest(m,day=DAY,mode="flexible")==n
    title,desc,caption=build_copy(DAY,n)
    assert f"{n} score" in title and f"{n} rencontre" in desc
    assert "pas de résultat garanti" in caption


@pytest.mark.parametrize("count",[0,11])
def test_no_video_or_publication_if_zero_or_excess_matches(count):
    with pytest.raises(ValueError):
        validate_daily_manifest(manifest(count),day=DAY,mode="flexible")


def test_strict_still_requires_exactly_ten_and_same_video_contract():
    assert validate_daily_manifest(manifest(10,"strict"),day=DAY,mode="strict")==10
    with pytest.raises(ValueError):
        validate_daily_manifest(manifest(8,"strict"),day=DAY,mode="strict")


@pytest.mark.parametrize("field,value",[
    ("count",9),("target","2026-11-13"),("status","PARTIAL"),
    ("ready_for_video",False),("publication_mode","strict"),
    ("schema","mrx-dixon-coles-social-flex-v2"),
    ("video","social_exact_scores_10.mp4"),
])
def test_bad_manifest_metadata_refused_before_any_social_upload(field,value):
    m=manifest(6);m[field]=value
    with pytest.raises(ValueError):
        validate_daily_manifest(m,day=DAY,mode="flexible")


def test_missing_or_fake_crests_and_repeated_games_block_publication():
    for value in (0,11):
        m=manifest(6);m["render_evidence"]["real_logo_instances"]=value
        with pytest.raises(ValueError):
            validate_daily_manifest(m,day=DAY,mode="flexible")
    m=manifest(6);m["render_evidence"]["placeholder_logo_instances"]=1
    with pytest.raises(ValueError):
        validate_daily_manifest(m,day=DAY,mode="flexible")
    m=manifest(6);m["match_ids"][1]=m["match_ids"][0]
    with pytest.raises(ValueError):
        validate_daily_manifest(m,day=DAY,mode="flexible")


def test_daily_workflow_is_flexible_and_publishes_not_merely_preview():
    text=(ROOT/".github/workflows/dixon-coles-social-top10-20h.yml").read_text()
    assert "cron: '0 20 * * *'" in text
    assert "github.event_name == 'schedule' && 'publish'" in text
    assert "github.event_name == 'schedule' && 'flexible'" in text
    assert "default: flexible" in text
    assert "--publication-mode \"$DCSCORE_PUBLICATION_MODE\"" in text
    assert "python scripts/check_daily_flexible_manifest.py" in text
    assert "--day \"$TARGET\"" in text
    assert "--report social_exact_scores_out/social_post_results.json" in text
    assert "python scripts/verify_social_publications.py" in text
    assert "SOCIAL_MODE == 'publish'" in text
    assert "tiktok_consent" in text


def test_original_risk_controls_remain_in_video_builder():
    src=(ROOT/"scripts/create_social_exact_score_video.py").read_text()
    assert '"--count", "10"' in src
    assert '"--require-renderable"' in src
    assert "require_real_logos=True" in src
    assert "allow_partial_production=(publication_mode=='flexible')" in src
    assert 'social_exact_scores_{count}.mp4' in src
