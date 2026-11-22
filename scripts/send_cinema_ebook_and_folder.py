#!/usr/bin/env python3
"""Two distinct campaigns, one verified cine/anime/series channel list.

Security properties:
- The selection is returned only by a service-role-guarded Supabase RPC. Private
  titles and identifiers are never printed or committed to the repository.
- Only verified channel-admin account + bot with Telegram posting permission.
- Explicit protected-channel exclusions and per-campaign/per-day atomic claims.
- No automatic replay after an ambiguous Telegram request.
- Posts are sent through the Bot API, not a Telegram user session.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
EBOOK_IMAGE = ROOT / 'assets/marketing/telegram-ebook-2026-11/affiche-promo-1938-fcfa.jpg'
FOLDER_IMAGE = ROOT / 'assets/telegram/mrxpronos_f_folder_promo.jpg'
FOLDER_VIDEO = ROOT / 'assets/telegram/mrxpronos_f_folder_promo.mp4'
BOT_ID = 8586885516
BOT_USERNAME = 'mrxpronos_canal_bot'
EXPECTED_BASE = '.supabase.co'
RPC_PATH = 'rpc/mrx_cinema_campaign_targets_v1'
RECEIPTS = 'telegram_channel_broadcast_receipts'
FOLDER_CAMPAIGN_PREFIX = 'mrxp_folder_f_daily_v1_'
EBOOK_CAMPAIGN_PREFIX = 'mrxp_telegram_ebook_ficsell_v1_'
EXCLUDED_IDS = {-1003919448551, -1003902962214, -1001733080826, -1003741349066}
EXCLUDED_NAMES = {'actufoot_mrxp','actucrypto_mrxp','mrxpronosfr','mr_xpronos_vip'}
FOLDER_LINK = 'https://t.me/addlist/ZmW4vfwcrMAwNzJk'
EXTRACT_LINK = 'https://mr-xpronos.myficsell.com/njtp54yjw'
GUIDE_LINK = 'https://mr-xpronos.myficsell.com/favxph7ge'

FOLDER_CAPTION = (
    '🎬 <b>FILMS • SÉRIES • ANIMÉS 🍿</b>\n'
    '🔥 <b>TOUT DANS UN SEUL DOSSIER TELEGRAM !</b>\n'
    '📂 <i>Tes chaînes de divertissement réunies au même endroit.</i>\n'
    '👇 <b>AJOUTE MR XPRONOS F GRATUITEMENT !</b>'
)
EBOOK_CAPTION = (
    '💰 <b>Et si Telegram devenait une nouvelle source de revenus ?</b>\n'
    '<blockquote>📘 <i>Découvre 10 méthodes concrètes pour le monétiser.</i></blockquote>\n'
    '📈 Apprends à <b>attirer des abonnés</b> et à développer ton activité.\n'
    '🎁 <i>Inclus : plan de 30 jours + bonus Canal Manager X.</i>\n'
    '👇 Clique sur le bouton ci-dessous pour obtenir ton guide à <b>1 938 FCFA</b> !'
)
FOLDER_BUTTONS = {'inline_keyboard': [[{'text': '📥 AJOUTER LE DOSSIER', 'url': FOLDER_LINK, 'style': 'primary'}]]}
EBOOK_BUTTONS = {'inline_keyboard': [
    [{'text': 'Voir l’extrait du PDF', 'url': EXTRACT_LINK, 'style': 'primary'}],
    [{'text': 'Télécharger mon guide', 'url': GUIDE_LINK, 'style': 'primary'}],
]}


class SafeFailure(RuntimeError):
    pass


def validate_files():
    for path in (EBOOK_IMAGE, FOLDER_IMAGE):
        if not path.is_file() or path.stat().st_size < 10000 or path.open('rb').read(3) != b'\xff\xd8\xff':
            raise SafeFailure('Missing or invalid JPEG asset: ' + path.name)
    if FOLDER_VIDEO.is_file() and b'ftyp' not in FOLDER_VIDEO.open('rb').read(36):
        raise SafeFailure('Invalid movie folder MP4')
    for caption in (EBOOK_CAPTION, FOLDER_CAPTION):
        if len(caption) > 1024:
            raise SafeFailure('Telegram caption exceeds 1024 chars')
    if len(EBOOK_BUTTONS['inline_keyboard']) != 2:
        raise SafeFailure('Ebook buttons missing')
    for markup in (EBOOK_BUTTONS, FOLDER_BUTTONS):
        for row in markup['inline_keyboard']:
            if len(row) != 1 or row[0].get('style') != 'primary' or not row[0]['url'].startswith('https://'):
                raise SafeFailure('Button styles/urls invalid')
    print('CAMPAIGN_ASSETS_OK: ebook, folder, 3 blue buttons, HTML captions')


class Storage:
    def __init__(self):
        self.base = os.environ.get('SUPABASE_URL', '').strip().rstrip('/')
        self.key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '').strip()
        if not re.fullmatch(r'https://[a-z0-9-]+\.supabase\.co', self.base) or not self.key:
            raise SafeFailure('Supabase service role configuration missing')
        self.session = requests.Session()
        self.session.headers.update({'apikey':self.key,'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})

    def fetch_targets(self):
        try:
            r = self.session.post(self.base+'/rest/v1/'+RPC_PATH, json={}, timeout=(8,30))
            if r.status_code != 200:
                raise SafeFailure('Secure cinema RPC failed (HTTP '+str(r.status_code)+')')
            rows=r.json()
        except (requests.RequestException,ValueError):
            raise SafeFailure('Secure cinema inventory not available') from None
        if not isinstance(rows,list) or not rows:
            raise SafeFailure('No verified eligible channels found')
        ids=[]
        for row in rows:
            if not isinstance(row,dict):
                raise SafeFailure('Invalid secure inventory row')
            cid=row.get('channel_id')
            if not isinstance(cid,int) or cid>=-1000000000000 or cid in EXCLUDED_IDS:
                raise SafeFailure('Invalid or excluded destination in secure inventory')
            name=str(row.get('public_username') or '').lower().lstrip('@')
            if name in EXCLUDED_NAMES or 'torrent9' in name:
                raise SafeFailure('Excluded channel in secure inventory')
            if bool(row.get('is_private')) == bool(name):
                raise SafeFailure('Private/public metadata mismatched')
            ids.append(cid)
        if len(ids)!=len(set(ids)) or len(ids)>250:
            raise SafeFailure('Duplicate / too many destinations')
        print('SECURE_TARGETS_VERIFIED',len(ids),'PRIVATE',sum(bool(x['is_private']) for x in rows),'PUBLIC',sum(not x['is_private'] for x in rows))
        return rows

    def reserve(self,campaign,channel_id):
        # Existing unique constraint (campaign_id, bot_id, channel_id) rejects reruns.
        try:
            r=self.session.post(self.base+'/rest/v1/'+RECEIPTS,
                headers={'Prefer':'return=representation'}, json={'campaign_id':campaign,'bot_id':BOT_ID,'channel_id':channel_id,'delivery_status':'reserved'},timeout=(8,25))
        except requests.RequestException:
            raise SafeFailure('Supabase claim uncertain; delivery blocked') from None
        if r.status_code==409:
            return False
        if r.status_code!=201:
            raise SafeFailure('Supabase reservation HTTP '+str(r.status_code))
        return True

    def mark(self,campaign,channel_id,status,*,msg_id=None,reason=None):
        payload={'delivery_status':status}
        if msg_id is not None:
            payload.update(message_id=msg_id,sent_at=dt.datetime.now(dt.timezone.utc).isoformat())
        if reason:
            payload['error_kind']=reason[:75]
        try:
            r=self.session.patch(self.base+'/rest/v1/'+RECEIPTS,
                params={'campaign_id':'eq.'+campaign,'bot_id':'eq.'+str(BOT_ID),'channel_id':'eq.'+str(channel_id)},
                json=payload,headers={'Prefer':'return=minimal'},timeout=(8,25))
            return r.status_code in (200,204)
        except requests.RequestException:
            return False


class Telegram:
    def __init__(self):
        self.token=(os.getenv('TELEGRAM_BOT_TOKEN') or '').strip()
        if not self.token:
            raise SafeFailure('TELEGRAM_BOT_TOKEN not configured')
        self.base='https://api.telegram.org/bot'+self.token+'/'
        self.http=requests.Session()

    def call(self,method,payload):
        try:
            response=self.http.post(self.base+method,json=payload,timeout=(8,25))
            body=response.json()
        except (requests.RequestException,ValueError):
            # Exception string may contain secret token. Never print it.
            raise SafeFailure('Telegram verification transport unavailable') from None
        if not response.ok or not isinstance(body,dict) or body.get('ok') is not True:
            raise SafeFailure('Telegram verification refused')
        return body['result']

    def verify_identity(self):
        me=self.call('getMe',{})
        if me.get('id')!=BOT_ID or str(me.get('username') or '').lower()!=BOT_USERNAME:
            raise SafeFailure('Wrong Telegram bot token')
        print('TELEGRAM_BOT_IDENTITY_VERIFIED')

    def can_post(self,channel_id):
        try:
            chat=self.call('getChat',{'chat_id':channel_id})
            member=self.call('getChatMember',{'chat_id':channel_id,'user_id':BOT_ID})
        except SafeFailure:
            return False
        return (chat.get('id')==channel_id and chat.get('type')=='channel' and
                (member.get('status')=='creator' or
                 (member.get('status')=='administrator' and member.get('can_post_messages') is True)))

    def send_media(self,channel_id,kind):
        if kind=='folder':
            image=FOLDER_VIDEO if FOLDER_VIDEO.is_file() else FOLDER_IMAGE
            file_key='animation' if image.suffix=='.mp4' else 'photo'
            mime='video/mp4' if file_key=='animation' else 'image/jpeg'
            method='sendAnimation' if file_key=='animation' else 'sendPhoto'
            caption=FOLDER_CAPTION
            buttons=FOLDER_BUTTONS
        else:
            image=EBOOK_IMAGE
            file_key='photo'
            mime='image/jpeg'
            method='sendPhoto'
            caption=EBOOK_CAPTION
            buttons=EBOOK_BUTTONS
        try:
            with image.open('rb') as f:
                response=self.http.post(self.base+method,data={
                    'chat_id':str(channel_id), 'caption':caption,'parse_mode':'HTML',
                    'reply_markup':json.dumps(buttons,ensure_ascii=False)
                },files={file_key:(image.name,f,mime)},timeout=(8,55))
                body=response.json()
        except (requests.RequestException,ValueError):
            raise SafeFailure('telegram_transport_uncertain') from None
        if response.status_code==429:
            raise SafeFailure('telegram_rate_limited')
        if not response.ok or not isinstance(body,dict) or body.get('ok') is not True:
            raise SafeFailure('telegram_refused_http_'+str(response.status_code))
        message_id=(body.get('result') or {}).get('message_id')
        if not isinstance(message_id,int):
            raise SafeFailure('telegram_missing_message_id')
        return message_id


def run(*,dry_run=False):
    validate_files()
    if dry_run:
        print('DRY_RUN_PASS: no Supabase or Telegram calls')
        return 0
    db=Storage()
    targets=db.fetch_targets()
    bot=Telegram()
    bot.verify_identity()
    today=dt.datetime.now(dt.timezone.utc).date().isoformat()
    campaign_ids={'folder':FOLDER_CAMPAIGN_PREFIX+today,'ebook':EBOOK_CAMPAIGN_PREFIX+today}
    counts={k:{'sent':0,'already_recorded':0,'permission_missing':0,'failed':0,'uncertain':0} for k in campaign_ids}
    public_links=[]
    total=len(targets)
    for idx,row in enumerate(targets,1):
        channel_id=row['channel_id']
        # Check the bot again immediately before posting; metadata may have become stale.
        if not bot.can_post(channel_id):
            for k in campaign_ids:counts[k]['permission_missing']+=1
            print('SKIP_PERMISSION_UNAVAILABLE',idx,'of',total)
            continue
        for kind,campaign in campaign_ids.items():
            try:
                reserved=db.reserve(campaign,channel_id)
            except SafeFailure:
                counts[kind]['uncertain']+=1
                print('CLAIM_UNCERTAIN',kind,idx)
                continue
            if not reserved:
                counts[kind]['already_recorded']+=1
                continue
            try:
                mid=bot.send_media(channel_id,kind)
            except SafeFailure as exc:
                reason=str(exc)
                state='uncertain' if reason in ('telegram_transport_uncertain','telegram_missing_message_id') else 'failed'
                counts[kind][state]+=1
                db.mark(campaign,channel_id,state,reason=reason)
                print('DELIVERY_REJECTED',kind,idx,state)
                continue
            counts[kind]['sent']+=1
            receipt_ok=db.mark(campaign,channel_id,'sent',msg_id=mid)
            print('DELIVERY_CONFIRMED',kind,idx,'receipt_updated' if receipt_ok else 'receipt_update_failed')
            if not row['is_private'] and row.get('public_username'):
                public_links.append('https://t.me/'+row['public_username'].lstrip('@')+'/'+str(mid))
            time.sleep(1.1)
    print('COMBINED_CINEMA_CAMPAIGN_RESULT',json.dumps(counts,ensure_ascii=False))
    path=os.getenv('GITHUB_STEP_SUMMARY')
    if path:
        with Path(path).open('a',encoding='utf-8') as f:
            f.write('## Dossier MR XPRONOS F + e-book Telegram\n\n')
            f.write(f'Sélection cinéma administrée et vérifiée : {total} chaînes (privées incluses).\n\n')
            for name,data in counts.items():f.write(f'- {name}: {json.dumps(data,ensure_ascii=False)}\n')
            f.write('\nLiens des publications publiques (aucun identifiant privé):\n')
            for u in public_links:f.write('- '+u+'\n')
    if any(counts[k]['failed'] or counts[k]['uncertain'] or counts[k]['permission_missing'] for k in counts):
        return 1
    return 0


if __name__=='__main__':
    try:
        ap=argparse.ArgumentParser()
        ap.add_argument('--check',action='store_true')
        ap.add_argument('--send',action='store_true')
        args=ap.parse_args()
        if args.check==args.send:
            raise SafeFailure('Use exactly --check or --send')
        sys.exit(run(dry_run=args.check))
    except SafeFailure as exc:
        print('::error::COMBINED_CINEMA_CAMPAIGN_ABORTED',str(exc))
        sys.exit(1)