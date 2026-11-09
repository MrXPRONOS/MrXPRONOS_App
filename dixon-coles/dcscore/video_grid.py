"""Mr XPRONOS: one-screen 2x5 exact-score reveal (no intro, no outro).

All ten cards, crests and team names remain on screen throughout the video.
Scores are revealed sequentially, without pretending to show live-match results.
Production retains the existing strict validation and crest allowlist.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
from PIL import Image, ImageDraw

from .video_render import (
    W, H, FPS, INK, TEAL, AMBER, WHITE, PALE, LogoCache,
    font, text_center, split_names, soundtrack, validate_payload, ease,
)

CARD_COLS = 2
CARD_ROWS = 5
CARD_X = (23, 368)
CARD_Y0 = 202
CARD_W = 329
CARD_H = 179
CARD_GAP_Y = 12
FIRST_REVEAL = .62
REVEAL_INTERVAL = 1.22
REVEAL_EFFECT = .42
FINAL_HOLD = 3.2
DATE_LOCALE = {
    1:'JANVIER', 2:'FÉVRIER', 3:'MARS', 4:'AVRIL', 5:'MAI', 6:'JUIN',
    7:'JUILLET', 8:'AOÛT', 9:'SEPTEMBRE', 10:'OCTOBRE', 11:'NOVEMBRE', 12:'DÉCEMBRE'
}


def _title_date(payload):
    raw=payload.get('date_local_africa_lome')
    try: day=date.fromisoformat(raw)
    except (ValueError, TypeError):
        if not payload.get('status')=='PREVIEW_ONLY':
            raise ValueError('Date locale obligatoire dans le storyboard quotidien')
        return 'DATE DE DÉMONSTRATION'
    return f'DU {day.day} {DATE_LOCALE[day.month]} {day.year}'


def layout_positions(n=10):
    """Two equally sized columns; first in left, second in right, row-major."""
    if n<1 or n>10:raise ValueError('La grille contient 1 à 10 cartes')
    return [(CARD_X[i%2], CARD_Y0+(i//2)*(CARD_H+CARD_GAP_Y)) for i in range(n)]


def _background():
    # Full-bleed night-blue frame: no unused giant margins or colored bars.
    im=Image.new('RGB',(W,H),(7,17,34))
    d=ImageDraw.Draw(im)
    for j in range(H):
        # faint top-to-bottom gradient; stays visually quiet.
        t=j/H
        color=(int(7+5*t),int(17+9*t),int(34+11*t))
        d.line((0,j,W,j),fill=color)
    d.text((W//2,30),'MR XPRONOS',font=font(23,True),fill=TEAL,anchor='mm')
    text_center(d,W//2,85,'SCORES EXACTS',49,WHITE,max_width=690)
    return im


def _short_team_name(draw,center,y,name,max_width):
    """One or two compact centered lines that cannot overlap adjacent names."""
    name=name.upper().replace(' FOOTBALL CLUB',' FC')
    words=name.split()
    lines=[name]
    if len(words)>1 and len(name)>12:
        # Balance the two lines by measured width, rather than splitting words.
        options=[(' '.join(words[:i]),' '.join(words[i:])) for i in range(1,len(words))]
        lines=list(min(options,key=lambda z:max(
            draw.textbbox((0,0),p,font=font(17,True))[2] for p in z)))
    if len(lines)==2:
        positions=(y-10,y+12)
    else:
        positions=(y,)
    for line,yy in zip(lines,positions):
        size=19
        while size>13 and draw.textbbox((0,0),line,font=font(size,True))[2]>max_width:
            size-=1
        if draw.textbbox((0,0),line,font=font(size,True))[2]>max_width:
            while len(line)>2 and draw.textbbox((0,0),line+'…',font=font(size,True))[2]>max_width:
                line=line[:-1]
            line+='…'
        draw.text((center,yy),line,font=font(size,True),fill=WHITE,anchor='mm')


def _scaled_crest(crest):
    x=crest.image.copy()
    x.thumbnail((72,72),Image.Resampling.LANCZOS)
    return x


def _static_frame(payload, clips, logos,preview):
    frame=_background().convert('RGBA')
    draw=ImageDraw.Draw(frame,'RGBA')
    text_center(draw,W//2,141,_title_date(payload),25,PALE,max_width=688)
    draw.line((24,177,696,177),fill=(72,115,142,100),width=2)
    for i,((x,y),clip,crests) in enumerate(zip(layout_positions(len(clips)),clips,logos)):
        draw.rounded_rectangle((x,y,x+CARD_W,y+CARD_H),radius=20,
                               fill=(22,38,62,255),outline=(56,79,107,255),width=2)
        home,away=split_names(clip['headline'])
        # logos, displayed from very first frame, do not move/flash
        for cx,crest in ((x+75,crests[0]),(x+CARD_W-75,crests[1])):
            img=_scaled_crest(crest)
            frame.alpha_composite(img,(round(cx-img.width/2),y+24))
        _short_team_name(draw,x+75,y+130,home,135)
        _short_team_name(draw,x+CARD_W-75,y+130,away,135)
    # Single understated demo statement, required to prevent fictional scores being misleading.
    if preview:
        text_center(draw,W//2,1230,'DÉMO · SCORES ET AFFICHES FICTIFS',18,AMBER,max_width=665)
    return frame


def _card_score(frame,clip,x,y,elapsed):
    """Animation only changes the score area. All cards/logos/names stay fixed."""
    draw=ImageDraw.Draw(frame,'RGBA')
    px=x+CARD_W//2
    display=clip['display_score'].replace('-', ' : ')
    # Before reveal, show an intentionally ambiguous dash, never a fake 0-0 match result.
    if elapsed < 0:
        text_center(draw,px,y+74,'— : —',29,(114,142,167,255),max_width=126)
        return
    phase=min(1.0,elapsed/REVEAL_EFFECT)
    if phase<.34:
        visible='— : —'
    elif phase<.70:
        visible=display.split(' : ')[0]+' : —'
    else:
        visible=display
    # Short one-shot accent flash, fades to stable cards.
    flash=(1.0-phase)**2
    if flash>.001:
        draw.rounded_rectangle((x+3,y+3,x+CARD_W-3,y+CARD_H-3),radius=18,
                               outline=(int(72+85*flash),int(205+45*flash),193,int(190*flash)),width=3)
        draw.rounded_rectangle((x+13,y+CARD_H-8,x+CARD_W-13,y+CARD_H-5),radius=1,
                               fill=(53,229,207,int(210*flash)))
    font_size=int(32+7*ease(max(0,(phase-.34)/.66)))
    c=(241,249,253,255) if phase>=.70 else (158,204,219,255)
    text_center(draw,px,y+75,visible,font_size,c,max_width=126)


def compose_frame(base,clips,t,*,reveal_starts):
    """Pure deterministic image composition, convenient for video and visual tests."""
    if len(clips)!=len(reveal_starts):raise ValueError('Schedule des révélations invalide')
    frame=base.copy()
    for clip,(x,y),start in zip(clips,layout_positions(len(clips)),reveal_starts):
        _card_score(frame,clip,x,y,t-start)
    return frame


def render(payload,output,*,preview=False,allow_partial_preview=False,
           fps=FPS,fullhd=False,asset_root='.',logo_cache=None):
    clips=validate_payload(payload,preview=preview,allow_partial_preview=allow_partial_preview)
    if len(clips)>10:raise ValueError('Maximum 10 matchs dans la grille')
    if not preview and len(clips)!=10:raise ValueError('La vidéo quotidienne exige dix matchs')
    if not shutil.which('ffmpeg'):raise RuntimeError('ffmpeg introuvable')
    if fps<5 or fps>60:raise ValueError('Fréquence image invalide')
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    reveal_starts=[FIRST_REVEAL+i*REVEAL_INTERVAL for i in range(len(clips))]
    duration=round(reveal_starts[-1]+REVEAL_EFFECT+FINAL_HOLD,3)
    frame_count=int(round(duration*fps))
    with tempfile.TemporaryDirectory(prefix='mrx-top10-grid-') as tmp:
        cache=LogoCache(logo_cache or Path(tmp)/'logos',asset_root,preview)
        logos=[(cache.get(c,'home',i),cache.get(c,'away',i)) for i,c in enumerate(clips,1)]
        base=_static_frame(payload,clips,logos,preview)
        audio=Path(tmp)/'original.wav'
        soundtrack(audio,duration,[0.0,*reveal_starts],volume=.55)
        silent=Path(tmp)/'silent.mp4'
        cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo',
             '-pixel_format','rgb24','-video_size',f'{W}x{H}',
             '-framerate',str(fps),'-i','pipe:0','-c:v','libx264',
             '-preset','veryfast','-pix_fmt','yuv420p','-crf','18',
             '-movflags','+faststart',str(silent)]
        p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            for k in range(frame_count):
                image=compose_frame(base,clips,k/fps,reveal_starts=reveal_starts)
                p.stdin.write(image.convert('RGB').tobytes())
            p.stdin.close()
            if p.wait(timeout=240):
                raise RuntimeError('Échec FFmpeg: '+p.stderr.read().decode(errors='replace')[-800:])
        except Exception:
            try:p.stdin.close()
            except (OSError,ValueError):pass
            p.kill();p.wait()
            raise
        mux=['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(silent),'-i',str(audio)]
        if fullhd:
            mux+=['-vf','scale=1080:1920:flags=lanczos',
                  '-c:v','libx264','-preset','medium','-pix_fmt','yuv420p','-crf','17']
        else:
            mux+=['-c:v','copy']
        mux+=['-c:a','aac','-b:a','160k','-ar','44100','-shortest','-movflags','+faststart',str(output)]
        subprocess.run(mux,capture_output=True,check=True,timeout=240)
    return {
        'output':str(output),'format':'single_screen_grid_2x5','intro':False,'outro':False,
        'duration_seconds':duration,'resolution':'1080x1920' if fullhd else f'{W}x{H}',
        'fps':fps,'matches_visible_from_first_frame':len(clips),
        'scores_revealed_sequentially':len(clips), 'preview':preview,
        'real_logo_instances':cache.real_count,'preview_placeholder_instances':cache.fallback_count,
        'size_bytes':output.stat().st_size,
    }


def cli():
    parser=argparse.ArgumentParser(description='Mr XPRONOS · 10 matchs, un écran, scores révélés')
    parser.add_argument('--payload',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--allow-partial-preview',action='store_true')
    parser.add_argument('--fullhd',action='store_true')
    parser.add_argument('--assets-root',default='.')
    parser.add_argument('--logo-cache',default=None)
    args=parser.parse_args()
    data=json.loads(Path(args.payload).read_text(encoding='utf-8'))
    result=render(data,args.output,preview=args.preview,
                  allow_partial_preview=args.allow_partial_preview,
                  fullhd=args.fullhd,asset_root=args.assets_root,logo_cache=args.logo_cache)
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':cli()
