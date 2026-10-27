"""MR XPRONOS — Football Stories / premium photographic visual system (phase 1).

Rules: full-bleed verified photography; never draw athletes, balls or pitches;
no slideshow-style content panels; layout variety; no photo = hard error.
Media rights and factual match content are checked by upstream modules.
"""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import math
import os
import re
import subprocess
import unicodedata
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageStat
from .story import Scene

W,H,FPS = 720,1280,24
INK=(247,249,248)
ORANGE=(255,113,37)
BLUE=(31,147,226)
BLACK=(4,10,18)
FONT_BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf'
FONT_REG='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
SAFE_X=46

class MissingLicensedMedia(ValueError):
    """A real football photograph with reuse rights is mandatory."""

@lru_cache(maxsize=128)
def ft(sz:int,bold:bool=True):
    font=FONT_BOLD if bold else FONT_REG
    return ImageFont.truetype(font,int(sz))

def run(cmd):
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=240)
    if p.returncode:raise RuntimeError(p.stderr[-1800:])
    return p.stdout

def duration(path:Path)->float:
    return float(run(['ffprobe','-v','error','-show_entries','format=duration','-of',
        'default=noprint_wrappers=1:nokey=1',str(path)]).strip())

def layout_for(kind:str)->str:
    return {
      'hook':'cover', 'stadium':'cinematic', 'versus':'duel',
      'score':'result', 'goal':'stat', 'pitch':'insight',
      'verdict':'reveal', 'source':'evidence', 'cta':'closing',
      'scorer':'ranking'
    }.get(kind,'editorial')

def _plain(text:str)->str:
    text=unicodedata.normalize('NFKC',str(text or ''))
    return re.sub(r'\s+',' ',text).strip()

def _crop_fill(path:Path,anchor:float=.50)->Image.Image:
    if not path or not Path(path).is_file():
        raise MissingLicensedMedia('Photo manquante: impossible de créer une scène sans image autorisée.')
    with Image.open(path) as raw:
        raw=raw.convert('RGB')
        sw,sh=raw.size
        if min(sw,sh)<600 or max(sw,sh)<960:
            raise MissingLicensedMedia(f'Photo trop petite: {sw}x{sh} ; minimum 600 px côté court.')
        scale=max(W/sw,H/sh)
        rw,rh=math.ceil(sw*scale),math.ceil(sh*scale)
        res=raw.resize((rw,rh),Image.Resampling.LANCZOS)
        left=round((rw-W)*max(0,min(1,anchor)))
        top=round((rh-H)*.52)
        return res.crop((left,top,left+W,top+H))

@lru_cache(maxsize=10)
def _shade(variant:str):
    yy=np.arange(H,dtype=np.float32)[:,None]
    if variant in ('cover','closing','ranking','result','reveal'):
        darkness=np.clip((yy-510)/700,0,1)**1.65 * .89 + .06
        darkness+=np.clip((210-yy)/260,0,1)*.32
    elif variant=='cinematic':
        darkness=np.clip((yy-360)/900,0,1)**2*.75+.16
    elif variant in ('duel','insight','evidence','editorial'):
        darkness=np.clip((yy-400)/800,0,1)*.79+.20
    else:
        darkness=np.clip((yy-520)/700,0,1)*.82+.14
    darkness=np.clip(darkness,0,.94)
    rgba=np.zeros((H,W,4),dtype=np.uint8)
    rgba[:,:,:3]=BLACK
    rgba[:,:,3]=np.broadcast_to((darkness*255).astype('uint8'),(H,W))
    return Image.fromarray(rgba,'RGBA')

def _width(d:ImageDraw.ImageDraw,t:str,f)->float:
    b=d.textbbox((0,0),t,font=f,stroke_width=0)
    return b[2]-b[0]

def _fit_size(d,text,max_w,max_size=84,min_size=30):
    for size in range(max_size,min_size-1,-2):
        if _width(d,text,ft(size))<=max_w: return size
    raise ValueError('Titre trop long pour une composition lisible : '+text[:100])

def _wrap(d,text,maxw,maxlines=3,max_size=80,min_size=34):
    """No clipping, no silent truncation: fit complete content or explicitly fail."""
    text=_plain(text).upper()
    words=text.split()
    for size in range(max_size,min_size-1,-2):
        f=ft(size)
        lines=[];cur=''
        for word in words:
            item=(cur+' '+word).strip()
            if _width(d,item,f)<=maxw:
                cur=item
            elif cur and _width(d,word,f)<=maxw:
                lines.append(cur);cur=word
            else:
                lines=[];break
        if cur:lines.append(cur)
        if 1<=len(lines)<=maxlines and all(_width(d,t,f)<=maxw for t in lines):
            return lines,size
    raise ValueError(f'Texte trop long pour {maxlines} lignes lisibles: {text[:105]}')

def _headline(d,text,y,maxsize=72,maxlines=3,color=INK,spacing=1.11):
    lines,size=_wrap(d,text,W-2*SAFE_X,maxlines=maxlines,max_size=maxsize)
    step=round(size*spacing)
    for line in lines:
        d.text((SAFE_X,y),line,font=ft(size),fill=color,stroke_width=0)
        y+=step
    return y

def _small(d,text,xy,size=22,color=INK,bold=False,maxw=None):
    content=_plain(text).upper()
    if maxw:
        while size>16 and _width(d,content,ft(size,bold))>maxw:size-=1
        if _width(d,content,ft(size,bold))>maxw:
            raise ValueError('Étiquette trop longue: '+content[:80])
    d.text(xy,content,font=ft(size,bold),fill=color)

def _brand(d):
    # Compact signature, no black header bar and no fake shield/logo.
    _small(d,'MR', (SAFE_X,56),26,INK,True)
    _small(d,'XPRONOS',(SAFE_X+55,55),26,ORANGE,True)
    d.line((SAFE_X,102,135,102),fill=ORANGE,width=4)

def _sub(d,text,y,maxlines=2):
    if not _plain(text):return
    lines,size=_wrap(d,text,W-2*SAFE_X,maxlines=maxlines,max_size=30,min_size=21)
    for line in lines:
        d.text((SAFE_X,y),line,font=ft(size,False),fill=(230,234,236))
        y+=round(size*1.4)

def _accent(d,y=785):
    d.line((SAFE_X,y,SAFE_X+72,y),fill=ORANGE,width=6)

def scene_poster(scene:Scene,out:Path,index:int,total:int,watermark=False,photo:Path|None=None):
    """Photo-first scene, full-bleed, deliberately different visual composition per role.

    A source photo is mandatory. Never silently substitute vector art or pretend
    a generic photograph shows the narrated match/player.
    """
    kind=layout_for(scene.kind)
    if total<1 or index<0 or index>=total:raise ValueError('Index de scène invalide')
    if photo is None:raise MissingLicensedMedia('Pas de photo autorisée pour la scène '+scene.kind)
    anchors={'cover':.60,'cinematic':.45,'duel':.30,'result':.55,'stat':.62,
             'insight':.25,'reveal':.48,'evidence':.65,'closing':.50,'ranking':.65}
    base=_crop_fill(Path(photo),anchors.get(kind,.5)).convert('RGBA')
    base=Image.alpha_composite(base,_shade(kind))
    d=ImageDraw.Draw(base,'RGBA')
    _brand(d)
    if kind=='cover':
        _small(d,scene.eyebrow,(SAFE_X,744),23,ORANGE,True,maxw=610)
        _accent(d,793)
        bottom=_headline(d,scene.headline,828,86,3)
        _sub(d,scene.sub,min(bottom+18,1084))
    elif kind=='cinematic':
        _small(d,scene.eyebrow,(SAFE_X,790),21,ORANGE,True,maxw=608)
        bottom=_headline(d,scene.headline,833,89,2)
        _sub(d,scene.sub,min(1070,bottom+24))
    elif kind=='duel':
        _small(d,scene.eyebrow,(SAFE_X,664),21,ORANGE,True,maxw=600)
        bottom=_headline(d,scene.headline,716,69,3)
        d.line((SAFE_X,bottom+12,230,bottom+12),fill=ORANGE,width=4)
        _sub(d,scene.sub,min(bottom+46,1086))
    elif kind=='result':
        _small(d,scene.eyebrow,(SAFE_X,701),22,ORANGE,True,maxw=615)
        text=_plain(scene.headline).replace('  :  ',':').replace(' : ',':')
        fsize=_fit_size(d,text,W-2*SAFE_X,152,66)
        d.text((SAFE_X,755),text,font=ft(fsize),fill=INK,stroke_width=0)
        _sub(d,scene.sub,1002)
    elif kind=='stat':
        _small(d,scene.eyebrow,(SAFE_X,720),22,ORANGE,True,maxw=615)
        line=scene.headline.strip().upper()
        if re.match(r'^\d{1,3}\b',line):
            num=line.split()[0];rest=' '.join(line.split()[1:])
            d.text((SAFE_X,755),num,font=ft(176),fill=INK)
            _small(d,rest,(SAFE_X+9,990),31,ORANGE,True,maxw=610)
            _sub(d,scene.sub,1052)
        else:
            bottom=_headline(d,line,790,71,3);_sub(d,scene.sub,min(bottom+28,1100))
    elif kind=='ranking':
        _small(d,scene.eyebrow,(SAFE_X,730),25,ORANGE,True,maxw=600)
        bottom=_headline(d,scene.headline,805,69,3)
        _sub(d,scene.sub,min(bottom+32,1080))
    elif kind=='reveal':
        _small(d,scene.eyebrow,(SAFE_X,744),21,ORANGE,True,maxw=615)
        _accent(d,788)
        bottom=_headline(d,scene.headline,813,68,3)
        _sub(d,scene.sub,min(bottom+20,1082))
    elif kind=='insight':
        _small(d,scene.eyebrow,(SAFE_X,746),22,ORANGE,True,maxw=615)
        bottom=_headline(d,scene.headline,810,66,3)
        _sub(d,scene.sub,min(bottom+26,1080))
    elif kind=='evidence':
        _small(d,scene.eyebrow,(SAFE_X,771),21,ORANGE,True,maxw=615)
        bottom=_headline(d,scene.headline,819,70,2)
        _sub(d,scene.sub,min(bottom+24,1081))
    elif kind=='closing':
        _small(d,scene.eyebrow,(SAFE_X,741),22,ORANGE,True,maxw=608)
        bottom=_headline(d,scene.headline,813,84,2)
        _sub(d,scene.sub,min(bottom+29,1080))
    else:
        _small(d,scene.eyebrow,(SAFE_X,758),22,ORANGE,True,maxw=610)
        bottom=_headline(d,scene.headline,821,69,3)
        _sub(d,scene.sub,min(bottom+24,1080))
    # Precise source/fiction disclosure, retained outside main focal area.
    if watermark:
        d.rectangle((0,1136,W,1200),fill=(110,22,21,222))
        _small(d,'DÉMONSTRATION FICTIVE — NON PUBLIABLE',(SAFE_X,1154),20,INK,True,maxw=W-2*SAFE_X)
    if not watermark:
        _small(d,'PHOTO D’ILLUSTRATION — VOIR CRÉDITS', (SAFE_X,1176),17,(225,229,233),False,maxw=620)
    _small(d,'FOOTBALL STORIES',(SAFE_X,1219),17,(219,224,229),True)
    # A short editorial progress mark, not a full width glowing bar.
    d.line((W-125,1236,W-45,1236),fill=(215,223,232,90),width=3)
    d.line((W-125,1236,W-125+int(80*(index+1)/total),1236),fill=ORANGE,width=3)
    out.parent.mkdir(parents=True,exist_ok=True)
    base.convert('RGB').save(out,quality=92,optimize=True)
    return {'layout':kind,'photo':str(photo),'scene':index,'font_policy':'photo_first'}


def scene_video(image:Path,out:Path,seconds:float,index:int):
    """Slow restrained Ken Burns movement; avoids jumpy synthetic stadium movement."""
    frames=max(24,int(seconds*FPS))
    zoom='min(zoom+0.0008,1.065)' if index%2==0 else 'if(eq(on,0),1.065,max(1.0,zoom-0.0008))'
    motion=(f"zoompan=z='{zoom}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:"
        f"s={W}x{H}:fps={FPS},format=yuv420p")
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-loop','1','-framerate',str(FPS),
         '-i',str(image),'-frames:v',str(frames),'-vf',motion,'-c:v','libx264',
         '-preset',os.getenv('FOOTBALL_FFMPEG_PRESET','veryfast'),'-crf','24','-pix_fmt',
         'yuv420p','-an',str(out)])


def licensed_clip_video(source:Path,out:Path,seconds:float):
    vf=f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=yuv420p'
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(source),'-t',str(seconds),
         '-vf',vf,'-an','-c:v','libx264','-preset','veryfast','-crf','23',str(out)])


def concat_video(files:list[Path],output:Path):
    concat=output.parent/'segments.txt'
    concat.write_text(''.join("file '"+str(p.resolve()).replace("'","'\\''")+"'\n" for p in files),'utf8')
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0',
         '-i',str(concat),'-c','copy',str(output)])
    concat.unlink(missing_ok=True)
