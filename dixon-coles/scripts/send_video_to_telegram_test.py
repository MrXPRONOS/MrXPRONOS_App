"""Send exactly one real, pre-match, 10-score video to @predict_mrxp only.

No production destination, no fabricated clips, and no token in logs.
Uses the existing repository's scripts/telegram_test_guard.py to verify
@predict_mrxp, bot identity and administrator posting permissions.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / 'scripts'))
from telegram_test_guard import validate_test_channel, TestChannelGuardError

class TestVideoError(ValueError):
    pass


def verify_assets(payload: dict, video: Path, now: datetime) -> None:
    now = now.astimezone(timezone.utc)
    clips = payload.get('clips')
    if (payload.get('ready_for_video') is not True or
        payload.get('status') != 'READY' or
        payload.get('selected_count') != 10 or
        not isinstance(clips, list) or len(clips) != 10):
        raise TestVideoError('Vidéo non certifiée READY avec 10 pronostics')
    if payload.get('date_local_africa_lome') != '2026-11-10':
        raise TestVideoError('Date cible du test incorrecte')
    scores = []
    for clip in clips:
        if not isinstance(clip, dict) or not clip.get('match_id'):
            raise TestVideoError('Pronostics sans identifiant du match')
        if not clip.get('home_logo_url') or not clip.get('away_logo_url'):
            raise TestVideoError('Écusson réel absent')
        score = str(clip.get('display_score', ''))
        import re
        if not re.fullmatch(r'\d{1,2}-\d{1,2}', score):
            raise TestVideoError('Score exact non calculé')
        scores.append(score)
        try:
            kickoff = datetime.fromisoformat(str(clip['kickoff_utc']).replace('Z', '+00:00'))
            if kickoff.tzinfo is None or kickoff <= now:
                raise TestVideoError('Match déjà commencé, aucune publication')
        except (ValueError, KeyError):
            raise TestVideoError('Date de coup d’envoi manquante ou invalide') from None
    if not video.is_file() or not (60_000 < video.stat().st_size < 49_000_000):
        raise TestVideoError('MP4 manquant ou taille incorrecte')
    try:
        r = subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_name,width,height',
            '-of','json',str(video)],capture_output=True,text=True,timeout=20,check=True)
        streams = json.loads(r.stdout).get('streams',[])
    except (OSError, subprocess.SubprocessError, ValueError):
        raise TestVideoError('MP4 non vérifiable') from None
    if not (any(s.get('codec_name') == 'h264' and s.get('width') == 1080 and s.get('height') == 1920 for s in streams)
            and any(s.get('codec_name') == 'aac' for s in streams)):
        raise TestVideoError('Vidéo non conforme aux codecs/dimensions attendus')


def send_video(payload_path: Path, video_path: Path, *, token: str, chat: str,
               now: datetime | None = None, session=None):
    now = now or datetime.now(timezone.utc)
    payload = json.loads(payload_path.read_text(encoding='utf-8'))
    verify_assets(payload, video_path, now)
    # Always verify remote Telegram chat username, type and posting permissions.
    dest = validate_test_channel(chat, token)
    # Unmistakable TEST caption: predictions from an uncalibrated league extension.
    caption = ('🧪 MR XPRONOS — TEST UNIQUEMENT\n'
        '⚽ 10 SCORES EXACTS DU 10 NOVEMBRE 2026\n'
        'Scores prévisionnels du modèle Dixon-Coles (non garantis).\n'
        'Source des affiches/résultats historiques : ESPN, fournisseur tiers.\n'
        'Analyse expérimentale, pas une recommandation de pari.')
    session = session or requests.Session()
    try:
        with video_path.open('rb') as handle:
            response = session.post('https://api.telegram.org/bot'+token+'/sendVideo',
                data={'chat_id':dest['chat_id'],'caption':caption,
                      'supports_streaming':'true'},
                files={'video':('mrxpronos_scores_2026-11-10.mp4',handle,'video/mp4')},
                timeout=(15,120))
        if response.status_code != 200:
            raise TestVideoError(f'Telegram HTTP {response.status_code}; aucun envoi confirmé')
        response_data=response.json()
    except requests.RequestException:
        # Never display the URL, because it contains the bot token.
        raise TestVideoError('Erreur réseau Telegram, envoi non confirmé') from None
    except (ValueError,KeyError):
        raise TestVideoError('Réponse Telegram illisible') from None
    if response_data.get('ok') is not True:
        raise TestVideoError('Telegram n’a pas confirmé sendVideo')
    result = response_data.get('result') or {}
    message_id = result.get('message_id')
    if not isinstance(message_id,int):
        raise TestVideoError('Telegram n’a pas retourné un identifiant de message')
    return {'destination':'@predict_mrxp','message_id':message_id,
            'url':f'https://t.me/predict_mrxp/{message_id}',
            'size_bytes':video_path.stat().st_size,
            'match_count':len(payload['clips'])}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--payload',type=Path,required=True)
    parser.add_argument('--video',type=Path,required=True)
    a=parser.parse_args()
    try:
        result = send_video(a.payload,a.video,
            token=os.getenv('FOOTBALL_NEWS_BOT_TOKEN','').strip(),
            chat=(os.getenv('TELEGRAM_TEST_CHAT_ID') or '@predict_mrxp').strip())
    except (TestVideoError,TestChannelGuardError,OSError) as exc:
        print('TELEGRAM_TEST_VIDEO_ERROR',str(exc),file=sys.stderr)
        return 1
    print('TELEGRAM_TEST_VIDEO_SENT',json.dumps(result,ensure_ascii=False))
    return 0

if __name__=='__main__':raise SystemExit(main())
