"""End-to-end flexible social workflow tests, OFFLINE (never publish).

Tests real FFmpeg encoding, logo-count integrity and the exact source/MP4/receipt
contract. Synthetic crests and matches are for an ephemeral smoke fixture only;
this test never uploads or calls a social provider.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from dcscore.domain import iso_date
from dcscore.video_grid_neon import render, positions
from dcscore.video_render import LogoCache
from dcscore.logo_policy import valid_logo_url

publisher=importlib.import_module("publish_social_exact_score_video")
creator=importlib.import_module("create_social_exact_score_video")
verifier=importlib.import_module("verify_social_publications")

CREST_1="https://a.espncdn.com/i/teamlogos/soccer/500/1.png"
CREST_2="https://a.espncdn.com/i/teamlogos/soccer/500/2.png"
PROVIDERS="facebook,youtube,instagram,threads,bluesky"


def fixture(target_count:int, path:Path, *, with_local_logos:bool=False):
    assert 1<=target_count<=9
    now=datetime.now(timezone.utc)
    day=(now+timedelta(days=1)).date().isoformat()
    selected=[]
    clips=[]
    for i in range(target_count):
        id=f"espn:eng.1:{i+100}"
        home=f"Home Test {i}"
        away=f"Away Test {i}"
        kickoff=iso_date(now+timedelta(days=1,hours=3+i))
        selected.append({
            "id":id,"home":home,"away":away,
            "home_logo_url":CREST_1,"away_logo_url":CREST_2,
            "kickoff_utc":kickoff,
            "forecast":{"most_likely_score":"2-1"},
            "fixture_provider_reported":True,
        })
        clips.append({
            "match_id":id,"headline":home+" - "+away,
            "display_score":"2-1", "kickoff_utc":kickoff,
            "home_logo_url":CREST_1,"away_logo_url":CREST_2,
        })
        if with_local_logos:
            clips[-1]["home_logo_asset"]="logos/test-home.png"
            clips[-1]["away_logo_asset"]="logos/test-away.png"
    if with_local_logos:
        for name,color in (("test-home.png",(50,110,205,255)),
                           ("test-away.png",(240,168,32,255))):
            file=path/"logos"/name
            file.parent.mkdir(exist_ok=True,parents=True)
            Image.new("RGBA",(72,72),color).save(file,"PNG")
    prediction={
        "date_local_africa_lome":day, "status":"READY",
        "publication_mode":"flexible","ready_for_video":True,
        "selected_count":target_count,"selected":selected,
    }
    storyboard={
        "date_local_africa_lome":day,"generated_at_utc":iso_date(now),
        "status":"READY","publication_mode":"flexible",
        "ready_for_video":True,"selected_count":target_count,
        "clips":clips,
    }
    report=path/"predictions.json"
    scene=path/"storyboard.json"
    report.write_text(json.dumps(prediction),encoding="utf-8")
    scene.write_text(json.dumps(storyboard),encoding="utf-8")
    return prediction,storyboard,report,scene


def manifest_for(video:Path, report:Path, scene:Path, selected:list,
                 count:int, day:str):
    return {
        "schema":"mrx-dixon-coles-social-flex-v3",
        "publication_mode":"flexible","target":day,"count":count,
        "match_ids":[x["id"] for x in selected],
        "predictions_sha256":sha256(report.read_bytes()).hexdigest(),
        "storyboard_sha256":sha256(scene.read_bytes()).hexdigest(),
        "render_evidence":{"real_logo_instances":2*count,
                           "placeholder_logo_instances":0,"resolution":"1080x1920"},
        "status":"READY","ready_for_video":True,
        "sha256":sha256(video.read_bytes()).hexdigest(),
        "telegram_username":"@mr_xpronos",
    }


@pytest.mark.parametrize("count",[1,3,9])
def test_flexible_proofs_for_1_3_and_9_reject_any_tampering(tmp_path,count):
    data,story,report,scene=fixture(count,tmp_path)
    creator.verify_ready(data,story,data["date_local_africa_lome"],publication_mode="flexible")
    video=tmp_path/"video.mp4"
    video.write_bytes(b"x"*100100)
    manifest=manifest_for(video,report,scene,data["selected"],count,data["date_local_africa_lome"])
    assert publisher.validate_manifest(manifest,video,predictions_path=report,
                                       storyboard_path=scene)==data["date_local_africa_lome"]
    assert count==len(manifest["match_ids"])
    with pytest.raises(ValueError,match="nécessaires"):
        publisher.validate_manifest(manifest,video)
    bad=dict(manifest,match_ids=manifest["match_ids"]+manifest["match_ids"][:1])
    with pytest.raises(ValueError,match="Identifiants"):
        publisher.validate_manifest(bad,video,predictions_path=report,storyboard_path=scene)
    bad=dict(manifest,render_evidence={"real_logo_instances":count,
                                      "placeholder_logo_instances":count,
                                      "resolution":"1080x1920"})
    with pytest.raises(ValueError,match="Preuve"):
        publisher.validate_manifest(bad,video,predictions_path=report,storyboard_path=scene)
    story["clips"][0]["display_score"]="7-7"
    scene.write_text(json.dumps(story),encoding="utf-8")
    with pytest.raises(ValueError,match="altérées"):
        publisher.validate_manifest(manifest,video,predictions_path=report,storyboard_path=scene)
    with pytest.raises(ValueError,match="10"):
        creator.verify_ready(data,story,data["date_local_africa_lome"],publication_mode="strict")


def test_ranked_storyboard_mismatch_fails_before_render(tmp_path):
    selection,story,report,scene=fixture(3,tmp_path)
    story["clips"][1]["match_id"]=selection["selected"][0]["id"]
    with pytest.raises(ValueError,match="identité"):
        creator.verify_ready(selection,story,selection["date_local_africa_lome"],
                             publication_mode="flexible")


def test_odd_flexible_video_has_single_centered_last_row():
    for n in (1,3,9):
        slot=positions(n)[-1]
        assert slot[0]==round((23+368)/2)
    assert positions(8)[-1][0]==368


def test_logo_cache_recounts_repeated_real_images(tmp_path):
    import dcscore.video_render as vr
    (tmp_path/"logos").mkdir()
    Image.new("RGBA",(72,72),(10,80,230,255)).save(tmp_path/"logos"/"t.png")
    cache=LogoCache(tmp_path/"cache",asset_root=tmp_path,preview=False)
    clip={"headline":"A Test - B Test","home_logo_asset":"logos/t.png",
          "away_logo_asset":"logos/t.png"}
    for i in range(4):
        assert cache.get(clip,"home",i).real
        assert cache.get(clip,"away",i).real
    assert cache.real_count==8 and cache.fallback_count==0


def test_full_ffmpeg_flexible_production_smoke_with_offline_demo_assets(tmp_path):
    # Completely offline synthetic matches/crests are used to exercise the
    # video encoder; they MUST NEVER be sent to any social network.
    import shutil
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg and ffprobe unavailable in local test runtime")
    data,story,report,scene=fixture(3,tmp_path,with_local_logos=True)
    output=tmp_path/"social_exact_scores_3.mp4"
    creator.verify_ready(data,story,data["date_local_africa_lome"],
                         publication_mode="flexible")
    proof=render(story,output,fullhd=True,asset_root=tmp_path,fps=4,
                 require_real_logos=True,allow_partial_production=True)
    assert proof["count"]==3 and proof["resolution"]=="1080x1920"
    assert proof["real_logo_instances"]==6 and proof["placeholder_logo_instances"]==0
    assert output.stat().st_size>100_000
    manifest=manifest_for(output,report,scene,data["selected"],3,data["date_local_africa_lome"])
    assert publisher.validate_manifest(manifest,output,predictions_path=report,
                                       storyboard_path=scene)==manifest["target"]


def test_social_provider_receipts_all_five_with_idempotent_d1_claims(tmp_path,monkeypatch):
    data,story,report,scene=fixture(3,tmp_path)
    video=tmp_path/"video.mp4"
    video.write_bytes(b"z"*100100)
    manifest=manifest_for(video,report,scene,data["selected"],3,data["date_local_africa_lome"])
    path=tmp_path/"social_manifest.json"
    path.write_text(json.dumps(manifest),encoding="utf-8")
    sent={}
    def record_query(self,sql,args):
        kind,ref,day=args[-3:]
        if sql.startswith("SELECT"):
            return {"results":[{"delivery_status":"sent",
                                "validation_details":json.dumps({"id":sent[(kind,ref,day)]})}]
                    if (kind,ref,day) in sent else []}
        if sql.startswith("UPDATE"):
            sent[(kind,ref,day)]=args[1]
            return {"meta":{"changes":1}}
        raise AssertionError(sql)
    claimed=[]
    class FakeLedger:
        def query(self,sql,args):
            if sql.startswith("SELECT"):
                kind,ref,day=args
                key=(kind,ref,day)
                return {"results":[{"delivery_status":"sent",
                                    "validation_details":json.dumps({"id":sent[key]})}]
                        if key in sent else []}
            if sql.startswith("UPDATE"):
                _,receipt,kind,ref,day=args
                sent[(kind,ref,day)]=json.loads(receipt)["id"]
                return {"meta":{"changes":1}}
            raise AssertionError(sql)
        def claim(self,kind,ref,day):
            claimed.append((kind,ref,day))
            return True
    posted=[]
    def fake_dispatch(platform, video_path, url, title, desc, caption):
        assert "3 scores exacts" in title
        assert "3 rencontres" in desc and "3 scores exacts" in caption
        assert video_path==video
        if platform in ("instagram","threads"):
            assert url=="https://example.invalid/verified-video.mp4"
        posted.append(platform)
        id=f"at://social.test/{platform}/1" if platform=="bluesky" else f"verified-{platform}-001"
        return SimpleNamespace(ok=True,message="Provider mocked success",data={"id":id})
    monkeypatch.setattr(publisher,"D1Ledger",FakeLedger)
    monkeypatch.setattr(publisher,"public_url",lambda *_:"https://example.invalid/verified-video.mp4")
    monkeypatch.setattr(publisher,"dispatch",fake_dispatch)
    args=["publisher","--video",str(video),"--manifest",str(path),
          "--predictions",str(report),"--storyboard",str(scene),
          "--platforms",PROVIDERS,"--report",str(tmp_path/"receipts.json")]
    monkeypatch.setattr(sys,"argv",args)
    assert publisher.main()==0
    receipts=json.loads((tmp_path/"receipts.json").read_text())
    assert verifier.validate(PROVIDERS,receipts,manifest)["checked"]==5
    assert posted==PROVIDERS.split(",")
    assert len(claimed)==5
    # Re-entrant run must reuse D1 provider IDs without a second upload.
    assert publisher.main()==0
    assert posted==PROVIDERS.split(",") and len(claimed)==5
    receipts=json.loads((tmp_path/"receipts.json").read_text())
    assert verifier.validate(PROVIDERS,receipts,manifest)["checked"]==5
    receipts[0]["count"]=10
    with pytest.raises(ValueError,match="MISMATCH"):
        verifier.validate(PROVIDERS,receipts,manifest)
