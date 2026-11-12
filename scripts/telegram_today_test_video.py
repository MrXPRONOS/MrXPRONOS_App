#!/usr/bin/env python3
"""One-time TODAY's verified Dixon-Coles V5 video for @predict_mrxp ONLY.

This does not use the tomorrow-only public social publisher, alter scheduled
workflows, post to production Telegram, or fabricate fixture information.
Build and send are distinct commands. No fake crests or preview assets.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dixon-coles"))

from dcscore.daily import main as daily_main
from dcscore.video_grid_neon import render
from create_social_exact_score_video import verify_ready
from telegram_test_guard import validate_test_channel, TestChannelGuardError

LOME = ZoneInfo("Africa/Lome")
ONLY_TEST_CHANNEL = "predict_mrxp"


class TestVideoFailure(ValueError):
    """Fails closed; do not retry ambiguous Telegram POSTs automatically."""


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_day(day: str, now: datetime) -> None:
    try:
        parsed = date.fromisoformat(day)
    except ValueError as exc:
        raise TestVideoFailure("Jour cible invalide") from exc
    if parsed != now.astimezone(LOME).date():
        raise TestVideoFailure("Ce test est réservé aux matchs d'aujourd'hui à Lomé")


def verified_matches(predictions: dict, storyboard: dict, target: str,
                     now: datetime) -> int:
    verify_ready(predictions, storyboard, target, publication_mode="flexible")
    n = predictions["selected_count"]
    if not isinstance(n, int) or not 1 <= n <= 10:
        raise TestVideoFailure("Aucun match réel et prêt à publier")
    for match, clip in zip(predictions["selected"], storyboard["clips"]):
        if (match.get("fixture_provider_reported") is not True
                or not match.get("home_logo_url")
                or not match.get("away_logo_url")):
            raise TestVideoFailure("Match ou écussons non confirmés par ESPN")
        if not re.fullmatch(r"\d{1,2}-\d{1,2}", str(clip.get("display_score",""))):
            raise TestVideoFailure("Score exact non calculé")
        try:
            kickoff = datetime.fromisoformat(clip["kickoff_utc"].replace("Z","+00:00"))
        except (KeyError, ValueError, AttributeError) as exc:
            raise TestVideoFailure("Heure de match invalide") from exc
        if kickoff.tzinfo is None or kickoff <= now:
            raise TestVideoFailure("Match déjà commencé : envoi de test interrompu")
    return n


def probe_mp4(video: Path, count: int) -> dict:
    if not video.is_file() or not 100_000 <= video.stat().st_size <= 24 * 1024 * 1024:
        raise TestVideoFailure("Vidéo absente ou taille inhabituelle")
    try:
        raw = subprocess.run(
            ["ffprobe","-v","error","-show_entries",
             "stream=codec_name,codec_type,width,height:format=duration",
             "-of","json",str(video)],
            capture_output=True,check=True,text=True,timeout=30)
        data = json.loads(raw.stdout)
        streams=data.get("streams") or []
        duration=float((data.get("format") or {}).get("duration",0))
    except (OSError,subprocess.SubprocessError,ValueError,TypeError) as exc:
        raise TestVideoFailure("Impossible d'analyser le MP4") from exc
    video_streams=[s for s in streams if s.get("codec_type")=="video"]
    audio=[s for s in streams if s.get("codec_type")=="audio"]
    if (len(video_streams)!=1 or video_streams[0].get("codec_name")!="h264"
            or (video_streams[0].get("width"),video_streams[0].get("height"))!=(1080,1920)
            or not any(s.get("codec_name")=="aac" for s in audio)
            or not 2<=duration<=60 or not 1<=count<=10):
        raise TestVideoFailure("MP4 exige H.264, AAC, 1080×1920 et une durée courte")
    return {"duration_seconds":round(duration,2),"video":"h264","audio":"aac",
            "width":1080,"height":1920}


def generate(day: str, out: Path, *, source: str="espn", now: datetime | None=None) -> int:
    now=now or datetime.now(timezone.utc)
    check_day(day, now)
    if source!="espn":
        raise TestVideoFailure("Test autorisé uniquement avec de vraies rencontres ESPN")
    status=daily_main([
        "--day", day, "--source", source, "--count","10",
        "--publication-mode","flexible","--require-renderable",
        "--min-team","4","--min-importance","70",
        "--max-staleness-days","35","--output-dir",str(out/"model")])
    if status:
        raise TestVideoFailure("Échec du calcul des scores réels")
    pred_path=out/"model"/day/"predictions.json"
    board_path=out/"model"/day/"video_payload.json"
    predictions,storyboard=_read(pred_path),_read(board_path)
    target=out/day
    target.mkdir(parents=True,exist_ok=True)
    if predictions.get("ready_for_video") is not True:
        (target/"skipped.json").write_text(json.dumps({
            "date":day,"selected_count":predictions.get("selected_count"),
            "reason":"Aucune rencontre réelle publiable",
            "details":predictions.get("reasons_not_ready",[]),
        },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("TELEGRAM_TODAY_TEST_SKIPPED",day,
              predictions.get("selected_count"),flush=True)
        return 3
    n=verified_matches(predictions,storyboard,day,now)
    video=target/f"mrxpronos_scores_{day}_{n}.mp4"
    info=render(storyboard,video,fullhd=True,
                asset_root=str(ROOT/"dixon-coles"),
                require_real_logos=True,
                allow_partial_production=True)
    if (info["count"]!=n or info["real_logo_instances"]!=2*n
            or info["placeholder_logo_instances"]!=0
            or info["resolution"]!="1080x1920"):
        video.unlink(missing_ok=True)
        raise TestVideoFailure("Le rendu contient des éléments artificiels")
    mp4=probe_mp4(video,n)
    proof={
        "date":day, "target_chat":"@predict_mrxp", "count":n,
        "video":str(video), "video_sha256":_digest(video),
        "predictions_sha256":_digest(pred_path),
        "storyboard_sha256":_digest(board_path),
        "match_ids":[str(row["id"]) for row in predictions["selected"]],
        "real_logo_instances":info["real_logo_instances"],
        "placeholder_logo_instances":info["placeholder_logo_instances"],
        "mp4":mp4, "status":"READY_TEST_ONLY",
    }
    (target/"test_manifest.json").write_text(
        json.dumps(proof,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("TELEGRAM_TODAY_TEST_VIDEO_READY",
          json.dumps({"day":day,"count":n,"size":video.stat().st_size,
                      "mp4":mp4,"video":str(video)},ensure_ascii=False),
          flush=True)
    return 0


def verified_proof(day:str,out:Path,now:datetime) -> tuple[dict,Path]:
    check_day(day,now)
    target=out/day
    proof=_read(target/"test_manifest.json")
    pred_path=out/"model"/day/"predictions.json"
    board_path=out/"model"/day/"video_payload.json"
    if (proof.get("date")!=day or proof.get("target_chat")!="@predict_mrxp"
            or proof.get("status")!="READY_TEST_ONLY"):
        raise TestVideoFailure("Manifeste étranger à la destination de test")
    n=verified_matches(_read(pred_path),_read(board_path),day,now)
    video=Path(proof["video"])
    if (n!=proof.get("count") or n!=len(proof.get("match_ids",[]))
            or not isinstance(proof.get("match_ids"),list)
            or proof["match_ids"]!=[
                str(g["id"]) for g in _read(pred_path)["selected"]]
            or not video.is_file()
            or _digest(video)!=proof.get("video_sha256")
            or _digest(pred_path)!=proof.get("predictions_sha256")
            or _digest(board_path)!=proof.get("storyboard_sha256")
            or proof.get("real_logo_instances")!=2*n
            or proof.get("placeholder_logo_instances")!=0):
        raise TestVideoFailure("Preuves du MP4 ou des pronostics altérées")
    if probe_mp4(video,n)!=proof.get("mp4"):
        raise TestVideoFailure("Fichier vidéo modifié après validation")
    return proof,video


def send(day:str,out:Path,*,token:str,chat:str,
         now:datetime|None=None,session=None,route_validator=validate_test_channel) -> dict:
    now=now or datetime.now(timezone.utc)
    proof,video=verified_proof(day,out,now)
    # Never post to a generic chat, main Telegram channel or user-supplied ID
    # without remotely checking its *current* username and bot privileges.
    destination=route_validator(chat,token)
    if (destination.get("username")!=ONLY_TEST_CHANNEL
            or destination.get("can_post") is not True):
        raise TestVideoFailure("Destination Telegram différente du canal de test")
    target=out/day
    if (target/"sent_receipt.json").exists():
        raise TestVideoFailure("Une confirmation de publication existe déjà; aucun doublon")
    n=proof["count"]
    fallback=sum(1 for r in _read(out/"model"/day/"predictions.json")["selected"]
                 if r.get("selection_pass")=="fallback")
    caption=(
        "🧪 TEST UNIQUEMENT — MR XPRONOS\n"
        f"⚽ {n} score{'s' if n!=1 else ''} exact{'s' if n!=1 else ''} "
        f"possible{'s' if n!=1 else ''} du {date.fromisoformat(day).strftime('%d/%m/%Y')}\n"
        f"📊 {n} rencontre{'s' if n!=1 else ''} réelle{'s' if n!=1 else ''}"
        f" • {fallback} estimation{'s' if fallback!=1 else ''} de secours\n"
        "Prévisions non garanties. Certaines estimations peuvent reposer "
        "sur des données insuffisantes. 18+ • Joue responsablement."
    )
    session=session or requests.Session()
    try:
        with video.open("rb") as handle:
            response=session.post(
                "https://api.telegram.org/bot"+token+"/sendVideo",
                data={"chat_id":destination["chat_id"],"caption":caption,
                      "supports_streaming":"true",
                      "disable_notification":"true"},
                files={"video":(video.name,handle,"video/mp4")},
                timeout=(15,120))
        if response.status_code!=200:
            raise TestVideoFailure(f"Telegram HTTP {response.status_code} : non confirmé")
        data=response.json()
    except requests.RequestException:
        # API path embeds bot token: do not disclose it in logs.
        raise TestVideoFailure("Envoi Telegram incertain ou problème réseau, ne pas relancer automatiquement") from None
    except ValueError:
        raise TestVideoFailure("Réponse Telegram illisible") from None
    if data.get("ok") is not True:
        raise TestVideoFailure("Telegram n'a pas confirmé l'envoi")
    message=data.get("result") or {}
    if (not isinstance(message.get("message_id"),int)
            or not isinstance(message.get("chat"),dict)
            or message["chat"].get("id")!=destination["chat_id"]
            or str(message["chat"].get("username") or "").casefold()!=ONLY_TEST_CHANNEL):
        raise TestVideoFailure("Telegram n'a pas confirmé le message dans le canal TEST")
    receipt={"destination":"@predict_mrxp","date":day,"count":n,
             "message_id":message["message_id"],
             "url":f"https://t.me/predict_mrxp/{message['message_id']}",
             "video_sha256":proof["video_sha256"],"fallback_count":fallback}
    (target/"sent_receipt.json").write_text(
        json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("TELEGRAM_TODAY_TEST_SENT",json.dumps(receipt,ensure_ascii=False),flush=True)
    return receipt


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("build","send"))
    p.add_argument("--day",default="2026-11-12")
    p.add_argument("--output-dir",type=Path,default=Path("telegram_today_test"))
    args=p.parse_args()
    try:
        if args.action=="build":
            return generate(args.day,args.output_dir)
        send(args.day,args.output_dir,
             token=os.getenv("FOOTBALL_NEWS_BOT_TOKEN","").strip(),
             chat=(os.getenv("TELEGRAM_TEST_CHAT_ID") or "@predict_mrxp").strip())
        return 0
    except (TestVideoFailure,TestChannelGuardError,ValueError,
            OSError,KeyError,subprocess.SubprocessError) as exc:
        # Do not include HTTP exception objects (could contain a bot token).
        print("TELEGRAM_TODAY_TEST_FAILURE",str(exc),file=sys.stderr,flush=True)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
