#!/usr/bin/env python3
"""Publication multiréseaux prudente : 2 API officielles, activation explicite.

Toute vidéo fictive, mal vérifiée, sans vraie voix, ou sans droits est BLOQUÉE.
Les extensions Meta/TikTok restent explicitement désactivées tant qu'elles ne sont
pas intégrées et validées (ne jamais prétendre que les envois ont fonctionné).
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import requests

SUPPORTED={'youtube','telegram'}

def telegram(file:Path,item:dict):
    token=os.environ.get('TELEGRAM_BOT_TOKEN');chat=os.environ.get('TELEGRAM_CHANNEL_ID')
    if not token or not chat: raise RuntimeError('Secrets Telegram manquants')
    with file.open('rb') as fd:
        r=requests.post(f'https://api.telegram.org/bot{token}/sendVideo',
             data={'chat_id':chat,'caption':(item['title']+'\n\n'+item['description'])[:1000],
                   'supports_streaming':'true'},files={'video':(file.name,fd,'video/mp4')},timeout=300)
    # Never include the Telegram bot token in errors or logs.
    if r.status_code!=200 or not r.json().get('ok'):raise RuntimeError('Telegram a refusé l’envoi')
    return str(r.json().get('result',{}).get('message_id',''))

def youtube(file:Path,item:dict):
    client=os.environ.get('YOUTUBE_CLIENT_ID');secret=os.environ.get('YOUTUBE_CLIENT_SECRET')
    refresh=os.environ.get('YOUTUBE_REFRESH_TOKEN')
    if not (client and secret and refresh):raise RuntimeError('Secrets YouTube manquants')
    token=requests.post('https://oauth2.googleapis.com/token',data={
           'client_id':client,'client_secret':secret,'refresh_token':refresh,'grant_type':'refresh_token'},timeout=40)
    token.raise_for_status();access=token.json()['access_token']
    privacy=os.getenv('FOOTBALL_YOUTUBE_PRIVACY','private').lower()
    if privacy not in {'private','unlisted','public'}:raise ValueError('FOOTBALL_YOUTUBE_PRIVACY invalide')
    info={'snippet':{'title':item['title'][:100],'description':item['description'][:4800],'categoryId':'17'},
          'status':{'privacyStatus':privacy,'selfDeclaredMadeForKids':False}}
    size=file.stat().st_size
    resp=requests.post('https://www.googleapis.com/upload/youtube/v3/videos',
         params={'uploadType':'resumable','part':'snippet,status'},
         headers={'Authorization':f'Bearer {access}','X-Upload-Content-Type':'video/mp4',
                  'X-Upload-Content-Length':str(size)},json=info,timeout=40)
    resp.raise_for_status();uri=resp.headers.get('Location')
    if not uri or not uri.startswith('https://www.googleapis.com/'):
        raise RuntimeError('URL d’upload YouTube inattendue')
    with file.open('rb') as fd:
        r=requests.put(uri,headers={'Content-Type':'video/mp4','Content-Length':str(size)},data=fd,timeout=300)
    r.raise_for_status();vid=r.json().get('id')
    if not vid: raise RuntimeError('Téléversement YouTube non confirmé')
    return vid

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',default='football_media_v2_output/productions.json')
    parser.add_argument('--state',default='football_media_v2_state.json')
    parser.add_argument('--networks',default=os.getenv('FOOTBALL_NETWORKS','telegram,youtube'))
    args=parser.parse_args(argv)
    entries=json.loads(Path(args.manifest).read_text('utf8'))
    if os.getenv('FOOTBALL_MEDIA_V2_PUBLISH','false').lower()!='true':
        print('[SAFE] Publication non activée. Vidéos seulement dans les artefacts.');return 0
    wanted=[x.strip() for x in args.networks.split(',') if x.strip()]
    if not wanted or any(n not in SUPPORTED for n in wanted):
        raise RuntimeError('Réseau non pris en charge : uniquement '+','.join(sorted(SUPPORTED)))
    current=Path(args.state)
    state=json.loads(current.read_text('utf8')) if current.exists() else {'seen':[],'receipts':{}}
    seen=set(state.get('seen',[])); receipts=state.setdefault('receipts',{});errors=[]
    for item in entries:
        if item.get('demo') or not item.get('quality',{}).get('ready_to_publish'):
            print('[BLOQUÉ] vidéo non conforme à tous les contrôles');continue
        file=Path(item['file'])
        if not file.is_file(): errors.append('Vidéo introuvable');continue
        key=item['state_key']
        if key in seen:print('[SKIP] contenu déjà envoyé');continue
        delivered=receipts.setdefault(key,{})
        try:
            for network in wanted:
                if network in delivered:
                    print('[SKIP] déjà envoyé à',network);continue
                delivered[network]=globals()[network](file,item)
                print('[PUBLIÉ]',network,delivered[network])
                # durable local receipt after each successful network upload
                current.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
            if all(network in delivered for network in wanted):
                seen.add(key)
                if item['kind']=='highlights':
                    seen.update('licensed:'+p for p in item.get('used_permissions',[]))
                state['seen']=sorted(seen)[-2500:]
                current.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
        except (RuntimeError,requests.RequestException,KeyError,ValueError) as exc:
            errors.append(f"{item.get('kind','unknown')}: {str(exc)[:130]}")
    if errors:
        for err in errors:print('[ERROR]',err)
        return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
