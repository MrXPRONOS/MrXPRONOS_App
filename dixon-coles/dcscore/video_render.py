"""Mr XPRONOS reusable 9:16 football prediction video renderer.

Renders a self-contained motion-graphics MP4 from a strictly validated
`video_payload.json`; supports --preview only for editorial review.
No club crest, stock footage, third-party music, or external assets required.

Requires Pillow, numpy, FFmpeg with libx264+aac. All audio is original synthesis.
"""
from __future__ import annotations
import argparse
import json
import math
import os
import random
import re
import shutil
import subprocess
import tempfile
import wave
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 720, 1280
FPS = 25
INTRO = 2.70
PER = 3.05
OUTRO = 2.75
BG0 = (5, 14, 30)
BG1 = (10, 31, 53)
CYAN = (70, 234, 219)
ORANGE = (255, 169, 78)
WHITE = (245, 249, 253)
MUTED = (135, 160, 187)
FONT_DIR = Path(os.environ.get('DCSCORE_VIDEO_FONTS', '/usr/share/fonts/opentype/inter'))
FONT_TITLE = str(FONT_DIR / 'InterDisplay-Black.otf')
FONT_BOLD = str(FONT_DIR / 'Inter-Bold.otf')
FONT_MED = str(FONT_DIR / 'Inter-Medium.otf')
if not all(Path(z).exists() for z in (FONT_TITLE,FONT_BOLD,FONT_MED)):
    # Ubuntu runners usually have DejaVu; no copyrighted font files are bundled.
    FONT_TITLE = FONT_BOLD = FONT_MED = (
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        if Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf').exists()
        else 'DejaVuSans.ttf'
    )


def f(size, bold=False, black=False):
    return ImageFont.truetype(FONT_TITLE if black else FONT_BOLD if bold else FONT_MED, size=size)


def txt(d, xy, text, size=34, color=WHITE, bold=False, black=False, anchor='la', stroke=0):
    d.text(xy, str(text), font=f(size, bold, black), fill=color, anchor=anchor,
           stroke_width=stroke, stroke_fill=BG0)


def fittext(d, x, y, value, max_width=590, max_size=51, min_size=20, color=WHITE, bold=True, anchor='la'):
    for size in range(max_size, min_size-1, -1):
        bbox=d.textbbox((0,0), value, font=f(size, bold))
        if bbox[2]-bbox[0] <= max_width:
            txt(d,(x,y),value,size,color,bold=bold,anchor=anchor)
            return size
    txt(d,(x,y),value,min_size,color,bold=bold,anchor=anchor)
    return min_size


def rounded(d, xy, radius=18, fill=(12,34,57), outline=None, width=1):
    d.rounded_rectangle(xy,radius=radius,fill=fill,outline=outline,width=width)


def brand(d):
    # Custom vector mark / wordmark; not a copied third-party logo.
    d.rounded_rectangle((61,61,109,109),radius=13, fill=CYAN)
    d.line((74,74,97,96),fill=BG0,width=7)
    d.line((96,74,74,96),fill=BG0,width=7)
    txt(d,(122,79),'MR',24,WHITE,bold=True,anchor='lm')
    txt(d,(171,79),'XPRONOS',25,CYAN,bold=True,anchor='lm')


def base(day='09 NOV. 2026'):
    yy=np.linspace(0,1,H,dtype=np.float32)[:,None,None]
    top=np.array(BG0,dtype=np.float32)[None,None,:]
    bottom=np.array(BG1,dtype=np.float32)[None,None,:]
    arr=(top+(bottom-top)*yy)
    arr=np.broadcast_to(arr,(H,W,3)).copy()
    xx=np.linspace(-1,1,W,dtype=np.float32)[None,:,None]
    vignette=1-0.11*np.abs(xx)**1.4
    arr*=vignette
    img=Image.fromarray(np.uint8(np.clip(arr,0,255)),'RGB').convert('RGBA')
    d=ImageDraw.Draw(img,'RGBA')
    # stadium lens lighting and refined grid
    for cx,cy,r,col in [(610,310,280,(27,160,170,9)),(50,810,220,(160,104,68,8))]:
        d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=col)
    for x in range(64,W,76):
        d.line((x,140,x,1120),fill=(83,130,155,12),width=1)
    for y in range(170,1160,76):
        d.line((64,y,656,y),fill=(83,130,155,12),width=1)
    # diagonal sport graphic signature
    d.polygon([(550,120),(720,120),(720,480),(680,480)],fill=(63,228,218,9))
    d.line((0,1187,720,1187),fill=(85,144,161,75),width=1)
    brand(d)
    txt(d,(650,89),'09 NOV',20,MUTED,bold=True,anchor='rm')
    txt(d,(58,1220),'ANALYSE STATISTIQUE  •  18+',17,MUTED,bold=True)
    txt(d,(659,1220),'MR XPRONOS',17,CYAN,bold=True,anchor='ra')
    return img


def demo_pill(d):
    rounded(d,(58,130,448,167),radius=11,fill=(67,37,34),outline=(206,131,87),width=2)
    txt(d,(76,148),'DÉMO  •  MODÈLES NON CALIBRÉS',16,(255,208,160),bold=True,anchor='lm')


def cover(number, preview, stage=2):
    """Three hard-cut hook cards within first 2.7 seconds for scroll-stopping pacing."""
    im=base()
    d=ImageDraw.Draw(im,'RGBA')
    if preview: demo_pill(d)
    # A consistent frame preserves identity while the copy changes on the beat.
    if stage==0:
        txt(d,(62,316),'DEMAIN,',67,MUTED,bold=True)
        rounded(d,(58,448,664,608),radius=26,fill=CYAN)
        txt(d,(360,529),f'{number} MATCHS.',83,BG0,black=True,anchor='mm')
        txt(d,(60,703),'DANS LE',57,WHITE,black=True)
        txt(d,(60,777),'VISEUR.',94,WHITE,black=True)
        txt(d,(61,939),'LES SCORES ARRIVENT...',28,ORANGE,bold=True)
    elif stage==1:
        txt(d,(62,320),'ET DONC...',65,MUTED,bold=True)
        rounded(d,(58,448,664,608),radius=26,fill=ORANGE)
        txt(d,(360,529),f'{number} SCORES.',78,BG0,black=True,anchor='mm')
        txt(d,(60,706),'LE PLUS',72,WHITE,black=True)
        txt(d,(60,782),'PROBABLES.',78,CYAN,black=True)
        txt(d,(61,939),'CALCULÉS, PAS DEVINÉS.',26,ORANGE,bold=True)
    else:
        txt(d,(62,297),'ET TOI ?',68,MUTED,bold=True)
        txt(d,(60,378),'TU EN',96,WHITE,black=True)
        txt(d,(60,479),'VALIDES',95,CYAN,black=True)
        rounded(d,(58,592,664,745),radius=26,fill=ORANGE)
        txt(d,(360,669),'COMBIEN ?',78,BG0,black=True,anchor='mm')
        txt(d,(61,832),'09 / 11 / 2026',40,WHITE,bold=True)
        txt(d,(61,925),'Un calcul. Pas une certitude.',28,MUTED)
    d.line((60,1021,390,1021),fill=CYAN,width=6)
    return im


def short_name(name):
    return name.strip().replace('Chivas Guadalajara','CHIVAS').replace('Real Sociedad B','REAL SOCIEDAD B').replace('Ebbsfleet United','EBBSFLEET')


def team_mark(d,cx,cy,label,accent):
    d.ellipse((cx-54,cy-54,cx+54,cy+54),fill=(20,51,69),outline=accent,width=3)
    parts=[p for p in re.split(r'\W+',label.upper()) if p]
    mono=''.join(x[0] for x in parts[:2]) if len(parts)>1 else label[:2].upper()
    txt(d,(cx,cy+1),mono[:3],32,accent,bold=True,anchor='mm')


def slide(clip, number, total, preview):
    im=base()
    d=ImageDraw.Draw(im,'RGBA')
    if preview: demo_pill(d)
    idx=int(clip.get('order',number))
    txt(d,(61,209),f'RENCONTRE {idx:02d} / {total:02d}',23,CYAN,bold=True)
    comp=str(clip.get('competition','FOOTBALL')).upper()
    rounded(d,(60,265,660,318),radius=13,fill=(20,54,76),outline=(64,112,133),width=2)
    fittext(d,79,290,comp,540,25,16,WHITE,True,anchor='lm')
    headline=str(clip['headline'])
    if ' - ' in headline: home,away=headline.split(' - ',1)
    elif ' – ' in headline: home,away=headline.split(' – ',1)
    else:home,away=headline,'ADVERSAIRE'
    home,away=short_name(home),short_name(away)
    team_mark(d,166,407,home,CYAN)
    team_mark(d,553,407,away,ORANGE)
    fittext(d,166,488,home.upper(),285,39,17,WHITE,True,anchor='mm')
    fittext(d,553,488,away.upper(),285,39,17,WHITE,True,anchor='mm')
    txt(d,(360,406),'VS',27,MUTED,bold=True,anchor='mm')
    # Main result panel
    rounded(d,(59,565,661,876),radius=26,fill=(18,47,68),outline=(63,145,151),width=2)
    txt(d,(360,615),'SCORE LE PLUS PROBABLE',25,CYAN,bold=True,anchor='mm')
    # Score and probability are added as animated, staggered text per frame.
    # Leaving this card blank here lets the score *arrive* on its own beat.
    txt(d,(61,932),'AUTRES SCÉNARIOS',25,MUTED,bold=True)
    tops=clip.get('top_3',[])
    if not tops:
        tops=[{'score':clip['display_score'],'probability':pct/100.}]
    # Show three distinct plausible scores rather than repeat main, if possible
    alts=[x for x in tops if x['score']!=clip['display_score']][:2]
    for i,row in enumerate(alts):
        yy=982+i*58
        txt(d,(61,yy),row['score'].replace('-', ' – '),28,WHITE,bold=True)
        rounded(d,(237,yy+2,538,yy+18),radius=8,fill=(24,55,75))
        p=float(row['probability']);p=p/100 if p>1 else p
        bar=int(301*min(p/.22,1))
        if bar>0:rounded(d,(237,yy+2,237+bar,yy+18),radius=8,fill=CYAN if i==0 else ORANGE)
        txt(d,(652,yy),f'{p*100:.1f}%'.replace('.',','),24,MUTED,bold=True,anchor='ra')
    # disclaimer stays within safe zone
    txt(d,(60,1148),'Pas de score garanti  •  Aucune mise conseillée',17,MUTED)
    return im


def ending(n,preview):
    im=base()
    d=ImageDraw.Draw(im,'RGBA')
    if preview:demo_pill(d)
    txt(d,(60,294),'ÇA SE JOUE',60,MUTED,bold=True)
    txt(d,(60,367),'SUR LE',79,WHITE,black=True)
    txt(d,(60,465),'TERRAIN.',91,CYAN,black=True)
    d.line((60,587,468,587),fill=ORANGE,width=7)
    txt(d,(60,665),'TON SCORE ?',73,WHITE,black=True)
    txt(d,(60,746),'EN COMMENTAIRE',44,ORANGE,bold=True)
    rounded(d,(59,866,663,965),radius=20,fill=CYAN)
    txt(d,(360,917),'MR XPRONOS',53,BG0,black=True,anchor='mm')
    txt(d,(60,1031),'Les probabilités ne sont pas des garanties.',21,MUTED)
    return im


def soundtrack(path,duration,scene_starts,volume=.50):
    """Entirely original synthetic soundbed; no samples or existing compositions."""
    rate=32000
    n=int(duration*rate)
    out=np.zeros(n,dtype=np.float32)
    rng=np.random.default_rng(22)
    def add(t,sig):
        a=max(0,int(t*rate));end=min(a+len(sig),n)
        if end>a:out[a:end]+=sig[:end-a]
    # light chordless synth pulse, rhythm in 104 bpm (not a copied melody)
    bps=104/60
    for i in range(int(duration*bps)+1):
        t=i/bps
        count=int(rate*.30)
        x=np.arange(count)/rate
        kick=np.sin(2*np.pi*(77*x+42*x*np.exp(-24*x)))*np.exp(-18*x)
        add(t,.37*kick)
        for off in [0,.5]:
            xx=np.arange(int(rate*.095))/rate
            hat=rng.normal(0,1,len(xx)).astype(np.float32)*np.exp(-55*xx)
            add(t+off/bps,.047*hat)
    # fresh tonal stabs with no recognizable tune
    for i in range(int(duration*1.28)):
        t=i/1.28+.18
        length=int(rate*.24)
        x=np.arange(length)/rate
        hz=[147,196,174,220][i%4]
        sig=(np.sin(2*np.pi*hz*x)+.27*np.sin(2*np.pi*(2*hz)*x))*np.exp(-14*x)
        add(t,.075*sig)
    # scene change clicks / short sweeps
    for t in scene_starts[1:]:
        x=np.arange(int(.20*rate))/rate
        sw=np.sin(2*np.pi*(460*x+980*x*x))*np.exp(-25*x)
        add(t,.25*sw)
    out=np.tanh(out*1.3)*volume
    pcm=(np.clip(out,-1,1)*32767).astype('<i2')
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def validate_payload(data, preview=False, allow_partial_preview=False):
    if not isinstance(data,dict):raise ValueError('Payload JSON invalide')
    clips=data.get('clips')
    if not isinstance(clips,list) or len(clips)==0 or len(clips)>15:
        raise ValueError('Nombre de clips invalide')
    if not preview:
        if data.get('ready_for_video') is not True or data.get('status')!='READY':
            raise ValueError('Publication vidéo interdite : payload NOT READY')
        if int(data.get('selected_count',-1))!=10 or len(clips)!=10:
            raise ValueError('Le mode production exige 10 matchs validés')
        now=datetime.now(timezone.utc)
        # The job must not render yesterday's cached list or matches in progress.
        from datetime import date
        day=date.fromisoformat(data['date_local_africa_lome'])
        if day<now.date() or (day-now.date()).days>1:
            raise ValueError('Date périmée ou trop éloignée')
        generated_str=data.get('generated_at_utc')
        if not generated_str:
            raise ValueError('Horodatage de génération manquant')
        generated=datetime.fromisoformat(str(generated_str).replace('Z','+00:00'))
        if generated.tzinfo is None:
            raise ValueError('Horodatage non UTC')
        age=(now-generated.astimezone(timezone.utc)).total_seconds()
        if age< -120 or age>4*3600:
            raise ValueError('Pronostics trop anciens pour un rendu automatique')
        for c in clips:
            t=c.get('kickoff_utc')
            if not t:raise ValueError('Coup d’envoi manquant')
            kickoff=datetime.fromisoformat(str(t).replace('Z','+00:00'))
            if kickoff.tzinfo is None or kickoff<=now:
                raise ValueError('Match commencé ou heure du coup d’envoi invalide')
    elif not allow_partial_preview and len(clips)<10:
        raise ValueError('Prévisualisation partielle non autorisée sans --allow-partial-preview')
    for i,c in enumerate(clips):
        if not isinstance(c,dict) or 'headline' not in c or 'display_score' not in c or 'display_probability_percent' not in c:
            raise ValueError('Clip incomplet')
        if not re.fullmatch(r'[0-9]{1,2}-[0-9]{1,2}',str(c['display_score'])):
            raise ValueError('Score exact mal formé')
        pct=float(c['display_probability_percent'])
        if not 0<pct<100:raise ValueError('Probabilité hors limites')
        if len(c['headline'])>120 or len(c.get('competition',''))>120:raise ValueError('Texte trop long')
    return clips


def ease(t):
    t=max(0,min(1,t));return 1-(1-t)**3


def render(payload,output,preview=False,allow_partial_preview=False,fps=FPS,fullhd=False):
    clips=validate_payload(payload,preview=preview,allow_partial_preview=allow_partial_preview)
    if shutil.which('ffmpeg') is None: raise RuntimeError('ffmpeg introuvable')
    total=INTRO+len(clips)*PER+OUTRO
    nframes=round(total*fps)
    starts=[0,INTRO/3,2*INTRO/3,INTRO]+[INTRO+PER*i for i in range(1,len(clips)+1)]
    hook_cards=[cover(len(clips),preview,stage=i) for i in range(3)]
    slides=[hook_cards[-1]]+[slide(c,i,len(clips),preview) for i,c in enumerate(clips,1)]+[ending(len(clips),preview)]
    # encoded frames, each static scene with animated opening + progress line + reveal mask
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='mrxvideo-') as tmp:
        sound=Path(tmp)/'sound.wav'
        soundtrack(sound,total,starts)
        video_raw=Path(tmp)/'silent.mp4'
        cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pixel_format','rgb24',
             '-video_size',f'{W}x{H}','-framerate',str(fps),'-i','pipe:0',
             '-c:v','libx264','-preset','veryfast','-pix_fmt','yuv420p','-crf','20','-movflags','+faststart',str(video_raw)]
        process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        assert process.stdin is not None
        try:
            for frame in range(nframes):
                t=frame/fps
                if t<INTRO:scene=0;within=t;seg=INTRO
                elif t<INTRO+len(clips)*PER:
                    rel=t-INTRO;scene=1+min(len(clips)-1,int(rel/PER));within=rel%PER;seg=PER
                else:scene=len(slides)-1;within=t-INTRO-len(clips)*PER;seg=OUTRO
                bg=(hook_cards[min(2,int(within/(INTRO/3)))] if scene==0 else slides[scene])
                # micro zoom/pan adds movement without shaking reading content
                shift=round(8*(1-ease(within/.55)))
                out=Image.new('RGBA',(W,H),BG0+(255,))
                out.alpha_composite(bg,dest=(0,shift))
                d=ImageDraw.Draw(out,'RGBA')
                # top timeline (global progress) and corner motion graphic
                d.rectangle((0,0,int(W*(frame+1)/nframes),7),fill=CYAN)
                if within<.35:
                    opacity=int(140*(1-ease(within/.35)))
                    d.rectangle((0,0,W,H),fill=(72,217,217,opacity//6))
                # subtle scanning beam, low contrast and away from text
                beam=int(660*((within/seg)))-20
                d.rounded_rectangle((beam,1193,beam+64,1197),radius=2,fill=(70,234,219,140))
                # scene label counter in safe top overlay
                if scene>0 and scene<len(slides)-1:
                    # Staggered kinetic type: score reveal, then the percentage.
                    c=clips[scene-1]
                    reveal=ease((within-.10)/.33)
                    fontsize=int(83+32*reveal)
                    # A tiny bounce makes the score pop without harming readability.
                    if .32<within<.58:
                        fontsize+=int(4*math.sin(math.pi*(within-.32)/.26))
                    score=c['display_score'].replace('-', ' — ')
                    txt(d,(360,728),score,fontsize,WHITE,black=True,anchor='mm')
                    pct=float(c['display_probability_percent'])
                    pillwidth=int(248*ease((within-.36)/.28))
                    if pillwidth>20:
                        rounded(d,(360-pillwidth//2,793,360+pillwidth//2,847),radius=25,fill=ORANGE)
                        if within>.62:
                            txt(d,(360,821),f'{pct:.1f} %'.replace('.',','),37,BG0,black=True,anchor='mm')
                    d.rounded_rectangle((580,135,658,166),radius=10,fill=(18,52,70,235))
                    txt(d,(620,151),f'{scene:02d}/{len(clips):02d}',17,CYAN,bold=True,anchor='mm')
                process.stdin.write(out.convert('RGB').tobytes())
            process.stdin.close()
            rc=process.wait(timeout=240)
            if rc!=0:raise RuntimeError(process.stderr.read().decode('utf-8',errors='replace')[-1400:])
        except Exception:
            try:process.stdin.close()
            except Exception:pass
            process.kill();process.wait()
            raise
        cmd2=['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(video_raw),'-i',str(sound)]
        if fullhd:
            cmd2+=['-vf','scale=1080:1920:flags=lanczos',
                   '-c:v','libx264','-preset','veryfast','-pix_fmt','yuv420p','-crf','19']
        else:
            cmd2+=['-c:v','copy']
        cmd2+=['-c:a','aac','-b:a','160k','-ar','44100',
               '-shortest','-movflags','+faststart',str(output)]
        subprocess.run(cmd2,check=True,capture_output=True)
    return {'output':str(output),'duration_seconds':round(total,2),'resolution':'1080x1920' if fullhd else f'{W}x{H}',
            'fps':fps,'clips':len(clips),'preview':preview,'size_bytes':output.stat().st_size}


def cli():
    p=argparse.ArgumentParser(description='Mr XPRONOS automatic football motion graphics video')
    p.add_argument('--payload',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--preview',action='store_true')
    p.add_argument('--fullhd',action='store_true',help='Exporter 1080x1920 avec Lanczos')
    p.add_argument('--allow-partial-preview',action='store_true')
    args=p.parse_args()
    data=json.loads(Path(args.payload).read_text(encoding='utf-8'))
    print(json.dumps(render(data,args.output,preview=args.preview,allow_partial_preview=args.allow_partial_preview,fullhd=args.fullhd),ensure_ascii=False,indent=2))

if __name__=='__main__': cli()
