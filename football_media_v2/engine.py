#!/usr/bin/env python3
"""Mr XPRONOS Football Media Engine V2 — indépendant des coupons.

Usage:
    python -m football_media_v2.engine --demo --mode match
    python -m football_media_v2.engine --mode auto
    python -m football_media_v2.engine --mode highlights

Production uniquement à partir de résultats vérifiés / médias explicitement autorisés.
Publication impossible sur du contenu fictif, non sonore ou de qualité insuffisante.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import random
import traceback
import requests
from .story import Scene,parse_match,select_match,match_scenes,parse_scorers,scorers_scenes,demo_match
from .rights import cleared
from .commons import get_photos
from .visuals import W,H,FPS,scene_poster,scene_video,licensed_clip_video,concat_video,run,duration,layout_for,MissingLicensedMedia
from .audio import voice_edge,summary_narration,beat,soundtrack

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent

def matches_today(today:dt.date)->list[dict]:
    token=os.environ.get('FOOTBALL_DATA_TOKEN','').strip()
    if not token: raise RuntimeError('FOOTBALL_DATA_TOKEN absent : aucune donnée football inventée')
    response=requests.get('https://api.football-data.org/v4/matches',
              params={'dateFrom':(today-dt.timedelta(days=2)).isoformat(),
                      'dateTo':today.isoformat(),'status':'FINISHED'},
              headers={'X-Auth-Token':token},timeout=30)
    response.raise_for_status()
    result=response.json().get('matches')
    if not isinstance(result,list): raise ValueError('Données API inattendues')
    return result

def scorers_current(code:str)->dict | None:
    token=os.environ.get('FOOTBALL_DATA_TOKEN','').strip()
    if not token: raise RuntimeError('FOOTBALL_DATA_TOKEN absent')
    code=code.upper()
    if code not in {'PL','PD','BL1','SA','FL1','DED','PPL','CL'}:
        raise ValueError('Compétition non autorisée')
    response=requests.get(f'https://api.football-data.org/v4/competitions/{code}/scorers',
                     params={'limit':5},headers={'X-Auth-Token':token},timeout=30)
    if response.status_code in {403,404}: return None # option payante ou indisponible
    response.raise_for_status()
    return parse_scorers(response.json(),code=code)

def ffprobe_video(path:Path)->dict:
    return json.loads(run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)]))

def qa_video(path:Path,scenes:int,voice_kind:str,is_demo:bool,facts_ok:bool,rights_ok:bool)->dict:
    info=ffprobe_video(path)
    streams=info.get('streams',[])
    videos=[s for s in streams if s.get('codec_type')=='video']
    audio=[s for s in streams if s.get('codec_type')=='audio']
    sec=float(info.get('format',{}).get('duration',0))
    gates={
       'correct_vertical_format':bool(videos and int(videos[0].get('width',0))==W and int(videos[0].get('height',0))==H),
       'length_16_to_58s':16<=sec<=58,
       'audio_track_present':bool(audio),
       'natural_voice_present':voice_kind=='edge_neural',
       'at_least_six_shots':scenes>=6,
       'source_verified':facts_ok,
       'rights_clear':rights_ok,
       'not_demo':not is_demo,
       'file_reasonable_size':path.stat().st_size>110_000,
    }
    return {'ready_to_publish':all(gates.values()),'gates':gates,
            'seconds':round(sec,2),'resolution':f'{W}x{H}','voice_engine':voice_kind}

def prepare_scenes(scenes:list[Scene],work:Path,voice_len:float|None,photos:list[dict]|None=None):
    # Ensure narration ends before CTA, without creating ten-second static cards.
    total=sum(s.duration for s in scenes)
    scale=max(1., min(1.7, ((voice_len or 0)+1.2)/total))
    if not photos: raise MissingLicensedMedia('Aucun visuel utilisable : ne pas générer un diaporama artificiel.')
    clips=[]; stops=[]; clock=0
    for i,scene in enumerate(scenes):
        png=work/f'frame_{i:02}.png';seg=work/f'clip_{i:02}.mp4'
        media=Path(photos[i%len(photos)]['file'])
        scene_poster(scene,png,i,len(scenes),watermark=False,photo=media)
        seconds=round(scene.duration*scale,3)
        scene_video(png,seg,seconds,i)
        clips.append(seg); clock+=duration(seg);stops.append(clock)
    return clips,stops

def render_analysis(kind:str,data:dict,out:Path,demo:bool):
    out.mkdir(parents=True,exist_ok=True)
    scenes=match_scenes(data) if kind=='match' else scorers_scenes(data)
    narration=summary_narration(kind,data)
    voice,vtype=voice_edge(narration,out/'narration.mp3')
    # A demo without voice gets the soundtrack, but remains unpublishable.
    if demo:
        # Original synthetic asset is only a fixture, NEVER acceptable for real publishing.
        fixture=ROOT/'assets'/'demo_synthetic_football.jpg'
        photos=[{'file':str(fixture),'title':'TEST VISUEL IA (SCÈNE FICTIVE)',
                 'author':'Mr XPRONOS / démo', 'license':'DEMO ONLY', 'source':'none'}] if fixture.exists() else []
    else:
        photos=get_photos(out/'illustrations',maximum=6) if os.environ.get('FOOTBALL_USE_COMMONS','true').lower()=='true' else []
        # Minimum three distinct photographs; we refuse slides, vectors and lookalike repeats.
        if len(photos)<3 or len({hashlib.sha256(Path(p['file']).read_bytes()).hexdigest() for p in photos})<3:
            raise MissingLicensedMedia('Au moins 3 photographies autorisées différentes sont nécessaires. Aucune publication.')
    seq,ends=prepare_scenes(scenes,out,duration(voice) if voice else None,photos=photos)
    video=out/'silent.mp4'
    concat_video(seq,video)
    bed=out/'original_music.wav'
    beat(bed,duration(video),ends)
    final=out/f'{kind}_short.mp4'
    soundtrack(video,final,voice,bed)
    if demo:
        # watermarked demo scenes are included in the actual rendered video, not just metadata
        # stamp unequivocally at video level for safe sharing (no accidental fictional claims).
        demo_file=out/f'{kind}_watermarked.mp4'
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(final),'-vf',
             "drawbox=x=0:y=ih-115:w=iw:h=65:color=red@0.86:t=fill,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='TEST FICTIF - NE PAS PUBLIER':fontcolor=white:fontsize=24:x=(w-text_w)/2:y=h-95",
             '-c:v','libx264','-preset','veryfast','-crf','23','-c:a','copy',str(demo_file)])
        final=demo_file
    score=qa_video(final,len(scenes),vtype,demo,True,True)
    score['gates']['licensed_football_illustrations']=not demo and len(photos)>=3
    score['gates']['visual_layout_diversity']=len({layout_for(s.kind) for s in scenes})>=6
    score['gates']['premium_photo_first']=len(photos)>0
    score['ready_to_publish']=all(score['gates'].values())
    if kind=='match':
        title=f"{data['home']} {data['a']}-{data['b']} {data['away']} | Le score qui fait réagir ⚽"
        key='match:'+data['id']
        source=f"Score confirmé : {data['home']} {data['a']}-{data['b']} {data['away']} ({data['competition']}, {data['date']}). Source : football-data.org."
    else:
        title=f"TOP BUTEURS : qui domine la {data['competition']} ?"
        key='scorers:'+data['code']+':'+hashlib.sha256(json.dumps(data['scorers'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:16]
        source='Classement des buteurs issu de football-data.org : '+', '.join(f"{p['name']} {p['goals']}" for p in data['scorers'])
    return {'file':str(final),'title':title[:100],
      'description':source+'\nImages d’illustration (ne représentent pas cette rencontre) :\n'+
          '\n'.join(f"{p['title']} — {p['author']} — {p['license']} — {p['source']}" for p in photos)+
          '\n#football #foot #mrxpronos #shorts','illustration_credits':photos,
      'kind':kind,'source':'football-data.org','demo':demo,'quality':score,'state_key':key,
      'storyboard':[{'kind':s.kind,'headline':s.headline,'seconds':s.duration} for s in scenes],
      'voice_text':narration}

def render_highlights(entries:list[tuple[dict,Path]],out:Path,demo=False):
    out.mkdir(parents=True,exist_ok=True)
    if len(entries)<2:return None
    rights=entries[:4]
    count=len(rights)
    intro=Scene('hook','CLIPS LICENCIÉS',f'{count} MOMENTS.','LEQUEL EST TON PRÉFÉRÉ ?',
                'Tu vas voir des séquences de football publiées avec autorisation. Laquelle préfères-tu ?',2.4)
    end=Scene('cta','ET TOI ?', 'TON TOP 1 ?', 'RÉPONDS EN COMMENTAIRE',
              'Quel extrait méritait la première place ? Abonne-toi à Mister X Pronos.',3.)
    parts=[];cutpoints=[]
    def capture_frame(source:Path,target:Path):
        # Frame taken from a clip already cleared for derivative/commercial use.
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss','0.3','-i',str(source),
             '-frames:v','1','-vf','scale=1200:-2',str(target)])
        return target
    cover_photo=capture_frame(rights[0][1],out/'cover_licensed_frame.jpg')
    first=out/'intro.png';scene_poster(intro,first,0,count+2,photo=cover_photo)
    opener=out/'intro.mp4';scene_video(first,opener,2.4,0);parts.append(opener)
    credits=[]
    for i,(lic,path) in enumerate(rights):
        flash=Scene('verdict',f'CLIP NUMÉRO {i+1}',lic.get('display_title','MOMENT FOOT').upper()[:30],
                    'SÉQUENCE PUBLIÉE AVEC AUTORISATION','',0.7)
        flashpng=out/f'flash_{i}.png';flashvideo=out/f'flash_{i}.mp4'
        flash_photo=capture_frame(path,out/f'licensed_still_{i}.jpg')
        scene_poster(flash,flashpng,i+1,count+2,photo=flash_photo)
        scene_video(flashpng,flashvideo,0.7,i+1);parts.append(flashvideo)
        output=out/f'licensed_{i}.mp4'
        d=min(7.,duration(path))
        if d<3.:return None
        licensed_clip_video(path,output,d)
        parts.append(output)
        credits.append(f"{lic['rights_holder']} — {lic['permission_id']} — {lic['source_url']} — {lic['license']}")
    last=out/'outro.png';scene_poster(end,last,count+1,count+2,photo=cover_photo)
    finalpart=out/'outro.mp4';scene_video(last,finalpart,3,9);parts.append(finalpart)
    silent=out/'silent.mp4';concat_video(parts,silent)
    voice,vtype=voice_edge(intro.voice+' '+end.voice,out/'narration.mp3')
    bed=out/'original_music.wav';beat(bed,duration(silent),[2.4+i*7.7 for i in range(count)])
    final=out/'highlights_short.mp4'
    soundtrack(silent,final,voice,bed)
    qa=qa_video(final,len(parts),vtype,demo,True,True)
    # Source rights are documentary inputs; all must be reviewed by human.
    return {'file':str(final),'title':'Moments forts du football | Mr XPRONOS',
      'description':'Extraits exploités sous licences / autorisations explicites.\n'+ '\n'.join(credits)+'\n#football #mrxpronos',
      'kind':'highlights','demo':demo,'quality':qa,'state_key':'highlights:'+':'.join(x[0]['permission_id'] for x in rights),
      'used_permissions':[x[0]['permission_id'] for x in rights]}


def main(argv=None):
    parser=argparse.ArgumentParser(description='Football Media Engine V2 : vidéos attractives, faits vérifiés')
    parser.add_argument('--mode',choices=['auto','match','scorers','highlights'],default='auto')
    parser.add_argument('--demo',action='store_true')
    parser.add_argument('--out',default='football_media_v2_output')
    parser.add_argument('--state',default='football_media_v2_state.json')
    parser.add_argument('--platforms',default='youtube,telegram')
    args=parser.parse_args(argv)
    if args.demo and args.mode=='highlights':
        parser.error('Test de highlights : fournir des clips autorisés ; mode démo seulement pour les matchs fictifs')
    out=Path(args.out).resolve();out.mkdir(exist_ok=True,parents=True)
    state=Path(args.state)
    saved=json.loads(state.read_text('utf-8')) if state.exists() else {'seen':[]}
    seen=set(saved.get('seen',[]));produced=[]
    try:
        mode='match' if args.demo else args.mode
        if mode=='auto':
            # Mix éditorial périodique ; fallback si statistiques non incluses dans le plan gratuit.
            mode='scorers' if dt.date.today().weekday() in (1,4) else 'match'
        if mode=='match':
            data=demo_match() if args.demo else select_match(matches_today(dt.datetime.now(dt.timezone.utc).date()),seen)
            if data:produced.append(render_analysis('match',data,out/'match',args.demo))
        if mode=='scorers':
            code=os.environ.get('FOOTBALL_COMPETITION','PL')
            try: data=scorers_current(code)
            except (requests.RequestException,ValueError) as exc:
                print('[INFO] Buteurs indisponibles :',str(exc)[:160]);data=None
            if data:
                newkey='scorers:'+data['code']+':'+hashlib.sha256(json.dumps(data['scorers'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:16]
                if newkey not in seen:produced.append(render_analysis('scorers',data,out/'scorers',False))
            if not produced:
                # valid fallback: actual match data, not invented list
                data=select_match(matches_today(dt.datetime.now(dt.timezone.utc).date()),seen)
                if data:produced.append(render_analysis('match',data,out/'match',False))
        if mode=='highlights':
            manifest=ROOT/'licensed_clips'/'manifest.json'
            entries=cleared(manifest,PROJECT,set(args.platforms.split(',')))
            entries=[(m,path) for m,path in entries if 'licensed:'+m['permission_id'] not in seen]
            if len(entries)>=2:
                entry=render_highlights(entries,out/'highlights')
                if entry:produced.append(entry)
        if not produced:print('[INFO] Aucun contenu nouveau, factuel et autorisé ; pas de vidéo inventée.')
    except (RuntimeError,requests.RequestException,ValueError,OSError) as exc:
        print('[ERROR] Échec du moteur :',exc)
        raise
    finally:
        path=out/'productions.json'
        path.write_text(json.dumps(produced,ensure_ascii=False,indent=2),encoding='utf8')
    for p in produced:
        ok=p['quality']['ready_to_publish']
        print('[VIDEO]',p['kind'],p['file'],'PUBLISHABLE' if ok else 'DRAFT / QUALITY GATE FAIL',p['quality']['gates'])
    return 0

if __name__=='__main__':raise SystemExit(main())
