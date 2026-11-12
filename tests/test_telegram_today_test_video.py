"""Offline tests for the ONE-TIME 12 Nov real-football Telegram test upload.

No Telegram API calls, no fake matches published and no production chat use.
"""
from __future__ import annotations
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import telegram_today_test_video as target

NOW=datetime(2026,11,12,0,6,tzinfo=timezone.utc)
DAY="2026-11-12"


def test_today_only_date_guard():
    target.check_day(DAY,NOW)
    with pytest.raises(target.TestVideoFailure,match="aujourd'hui"):
        target.check_day("2026-11-13",NOW)
    with pytest.raises(target.TestVideoFailure):
        target.check_day("2026-11-11",NOW)


def test_no_fake_video_metadata_accepted(tmp_path):
    video=tmp_path/"fake.mp4"
    video.write_bytes(b"junk"*100_000)
    with pytest.raises(target.TestVideoFailure,match="MP4"):
        target.probe_mp4(video,4)


def _sender_fixture(tmp_path,monkeypatch,n=3):
    out=tmp_path/"today"
    folder=out/DAY
    folder.mkdir(parents=True)
    pred=out/"model"/DAY/"predictions.json"
    pred.parent.mkdir(parents=True)
    pred.write_text(json.dumps({"selected":[
        {"selection_pass":"strict"},
        {"selection_pass":"fallback"},
        {"selection_pass":"strict"},
    ][:n]}),encoding="utf-8")
    vid=folder/"match_test.mp4"
    vid.write_bytes(b"test bytes not decoded; mocked verified_proof")
    proof={"date":DAY,"count":n,"video_sha256":"a"*64}
    monkeypatch.setattr(target,"verified_proof",lambda *a:(proof,vid))
    return out


class FakeSession:
    def __init__(self, username="predict_mrxp",status=200):
        self.posts=[]
        self.username=username
        self.status=status
    def post(self,url,*,data,files,timeout):
        self.posts.append({"url":url,"data":data,"files":files,"timeout":timeout})
        return SimpleNamespace(
            status_code=self.status,
            json=lambda:{
                "ok":self.status==200,
                "result":{"message_id":8109,"chat":{
                    "id":-1004366833281,"username":self.username}},
            })


def _verified_route(chat,token):
    assert token=="FAKE_BOT_TOKEN"
    return {"chat_id":-1004366833281,"username":"predict_mrxp","can_post":True}


def test_sender_posts_only_real_count_to_verified_test_channel_and_writes_receipt(tmp_path,monkeypatch):
    out=_sender_fixture(tmp_path,monkeypatch,3)
    fake=FakeSession()
    receipt=target.send(DAY,out,token="FAKE_BOT_TOKEN",
                         chat="@predict_mrxp",now=NOW,session=fake,
                         route_validator=_verified_route)
    assert len(fake.posts)==1
    post=fake.posts[0]
    assert post["data"]["chat_id"]==-1004366833281
    assert "🧪 TEST UNIQUEMENT" in post["data"]["caption"]
    assert "3 scores exacts possibles" in post["data"]["caption"]
    assert "1 estimation de secours" in post["data"]["caption"]
    assert receipt["count"]==3
    assert receipt["url"]=="https://t.me/predict_mrxp/8109"
    assert (out/DAY/"sent_receipt.json").is_file()
    with pytest.raises(target.TestVideoFailure,match="aucun doublon"):
        target.send(DAY,out,token="FAKE_BOT_TOKEN",chat="@predict_mrxp",
                    now=NOW,session=fake,route_validator=_verified_route)
    assert len(fake.posts)==1


def test_sender_refuses_unverified_destination_before_network(tmp_path,monkeypatch):
    out=_sender_fixture(tmp_path,monkeypatch)
    fake=FakeSession()
    def wrong_channel(chat,token):
        return {"chat_id":-100987654321,"username":"actual_production",
                "can_post":True}
    with pytest.raises(target.TestVideoFailure,match="canal de test"):
        target.send(DAY,out,token="FAKE_BOT_TOKEN",
                    chat="@anything",now=NOW,session=fake,
                    route_validator=wrong_channel)
    assert not fake.posts


def test_sender_rejects_unconfirmed_telegram_chat_response(tmp_path,monkeypatch):
    out=_sender_fixture(tmp_path,monkeypatch)
    fake=FakeSession(username="other_channel")
    with pytest.raises(target.TestVideoFailure,match="pas confirmé"):
        target.send(DAY,out,token="FAKE_BOT_TOKEN",
                    chat="@predict_mrxp",now=NOW,session=fake,
                    route_validator=_verified_route)
    assert not (out/DAY/"sent_receipt.json").exists()


def test_uncertain_transport_timeout_is_not_retried(tmp_path,monkeypatch):
    out=_sender_fixture(tmp_path,monkeypatch)
    class TimeoutSession:
        sent=0
        def post(self,*args,**kwargs):
            self.sent+=1
            raise requests.Timeout("Could be sent")
    fake=TimeoutSession()
    with pytest.raises(target.TestVideoFailure,match="incertain"):
        target.send(DAY,out,token="FAKE_BOT_TOKEN",
                    chat="@predict_mrxp",now=NOW,session=fake,
                    route_validator=_verified_route)
    assert fake.sent==1


def test_today_test_isolated_from_production_publisher():
    src=(ROOT/"scripts/telegram_today_test_video.py").read_text()
    assert "validate_test_channel" in src
    assert "predict_mrxp" in src
    assert "FOOTBALL_NEWS_BOT_TOKEN" in src
    assert "TELEGRAM_TEST_CHAT_ID" in src
    assert "scripts/publish_social_exact_score_video.py" not in src
    assert "telegram_test_guard" in src
