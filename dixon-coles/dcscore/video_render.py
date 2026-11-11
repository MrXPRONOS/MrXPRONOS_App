"""Mr XPRONOS minimalist vertical score-reveal studio (V2).

One match per screen: 2 real club crests, their names and ONE calculated score.
No probabilities, weather, betting odds or clutter in the video itself.
Production requires ten fresh verified forecasts and real club crest assets.
A demo may display clearly labelled non-official initials when assets unavailable.
Original generated sound; no external music or bundled trademark artwork.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import hashlib
import json
import math
import re
import shutil
import subprocess
import tempfile
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

W, H = 720, 1280
FPS = 25
INTRO = 1.05
PER = 1.95
OUTRO = 1.35
INK = (6, 14, 30)
INK2 = (10, 25, 45)
TEAL = (53, 229, 207)
AMBER = (255, 162, 72)
WHITE = (247, 251, 253)
PALE = (164, 185, 203)
from .logo_policy import valid_logo_url as _valid_logo_url
MAX_LOGO_BYTES = 650_000


def _font_path(bold=False):
    options = (
        ('/usr/share/fonts/opentype/inter/InterDisplay-Black.otf',
         '/usr/share/fonts/opentype/inter/Inter-Bold.otf') if bold else
        ('/usr/share/fonts/opentype/inter/Inter-Medium.otf',
         '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    )
    for p in (*options, '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(p).is_file():
            return p
    return 'DejaVuSans.ttf'


@lru_cache(maxsize=55)
def font(size, bold=False):
    return ImageFont.truetype(_font_path(bold), size)


def text_center(draw, x, y, value, size, fill=WHITE, *, bold=True, max_width=None):
    value=str(value)
    while max_width and size>20:
        bbox=draw.textbbox((0,0),value,font=font(size,bold))
        if bbox[2]-bbox[0]<=max_width:break
        size-=2
    draw.text((x,y),value,font=font(size,bold),fill=fill,anchor='mm')


def _bg():
    top=np.asarray(INK,dtype=np.float32)
    bottom=np.asarray(INK2,dtype=np.float32)
    y=np.linspace(0,1,H,dtype=np.float32)[:,None,None]
    base=np.broadcast_to(top[None,None,:]*(1-y)+bottom[None,None,:]*y,(H,W,3)).copy()
    # Only one soft beam. Simplicity beats distracting effects.
    xx=np.linspace(-1,1,W,dtype=np.float32)[None,:,None]
    base*=1-.11*np.abs(xx)**1.3
    return Image.fromarray(np.uint8(np.clip(base,0,255)),'RGB').convert('RGBA')


@lru_cache(maxsize=1)
def background():
    im=_bg()
    d=ImageDraw.Draw(im,'RGBA')
    # Keep the pitch-dark background clean; avoid oversized colored shapes.
    d.line((56,1190,664,1190),fill=(75,123,150,52),width=2)
    return im


def _brand(draw):
    draw.rounded_rectangle((52,60,98,106),radius=10,fill=TEAL)
    draw.line((63,71,87,96),fill=INK,width=7)
    draw.line((87,71,63,96),fill=INK,width=7)
    draw.text((111,85),'MR XPRONOS',font=font(25,True),fill=WHITE,anchor='lm')


def _demo_tag(draw):
    # Always present when displaying non-published / fictional games.
    text_center(draw,W//2,1162,'DÉMO · MATCHS ET SCORES FICTIFS',17,AMBER)


def _progress(draw, index, total):
    left=58;right=W-58;gap=6
    part=(right-left-gap*(total-1))/total
    for i in range(total):
        x=int(left+i*(part+gap))
        draw.rounded_rectangle((x,1125,x+part,1132),radius=3,
                               fill=TEAL if i<=index else (40,70,88))


def cover(n, preview=False, stage=0):
    im=background().copy();d=ImageDraw.Draw(im)
    _brand(d)
    text_center(d,360,459,f'{n:02d}',214,TEAL)
    text_center(d,360,603,'MATCHS',67,WHITE)
    d.rounded_rectangle((118,682,602,692),radius=5,fill=AMBER)
    text_center(d,360,794,f'{n} SCORES EXACTS',45,WHITE,max_width=640)
    if preview:_demo_tag(d)
    return im


def ending(n, preview=False):
    im=background().copy();d=ImageDraw.Draw(im)
    _brand(d)
    text_center(d,360,504,'TU EN VALIDES',53,WHITE,max_width=650)
    text_center(d,360,636,'COMBIEN ?',80,TEAL,max_width=660)
    d.rounded_rectangle((222,749,498,759),radius=5,fill=AMBER)
    text_center(d,360,918,'EN COMMENTAIRE',29,WHITE)
    if preview:_demo_tag(d)
    else:text_center(d,360,1158,'Scores estimés • 18+ • Joue responsablement',16,PALE)
    return im


def split_names(headline):
    if not isinstance(headline,str):raise ValueError('Affiche invalide')
    if ' - ' in headline:return tuple(x.strip() for x in headline.split(' - ',1))
    if ' – ' in headline:return tuple(x.strip() for x in headline.split(' – ',1))
    raise ValueError('L’affiche doit séparer les clubs par « - » ou « – ».')


def _rasterize(raw):
    # Permit only common raster formats or self-contained sanitized SVG.
    if raw.lstrip().startswith((b'<?xml',b'<svg')):
        if any(x in raw.lower() for x in (b'<!doctype',b'<!entity',b'<image',b'<use',b'url(',b'@import',b'<script',b'<foreignobject',b'href=',b'src=',b'file:')):
            raise ValueError('SVG externe ou actif non autorisé')
        try:
            import cairosvg
        except ImportError as exc:raise ValueError('Installer le paquet video pour les écussons SVG') from exc
        raw=cairosvg.svg2png(bytestring=raw,output_width=300,output_height=300)
    try:
        with Image.open(BytesIO(raw)) as img:
            if img.format not in ('PNG','JPEG','WEBP'):
                raise ValueError('Format logo non autorisé')
            if img.width*img.height>6_000_000:
                raise ValueError('Résolution logo excessive')
            rgba=img.convert('RGBA')
            rgba.thumbnail((248,248),Image.Resampling.LANCZOS)
            return rgba.copy()
    except (UnidentifiedImageError,OSError) as exc:raise ValueError('Image de logo illisible') from exc


def _fetch_logo(url,session=None):
    if not _valid_logo_url(url):raise ValueError('URL logo non autorisée')
    if session is None:
        import requests
        session=requests.Session()
    r=session.get(url,timeout=(8,18),stream=True,allow_redirects=False,
                  headers={'User-Agent':'MrXPRONOS-Crest-Renderer/2.0','Accept':'image/png,image/webp,image/jpeg,image/svg+xml'})
    try:
        if r.status_code!=200:raise ValueError(f'Logo indisponible (HTTP {r.status_code})')
        buffer=bytearray()
        for part in r.iter_content(32768):
            buffer.extend(part)
            if len(buffer)>MAX_LOGO_BYTES:raise ValueError('Fichier logo trop volumineux')
        return _rasterize(bytes(buffer))
    finally:
        r.close()


def _asset_path(asset,root):
    if not isinstance(asset,str) or not re.fullmatch(r'[A-Za-z0-9_./-]{1,180}',asset):
        raise ValueError('Chemin de logo non autorisé')
    rel=Path(asset)
    if rel.is_absolute() or '..' in rel.parts:raise ValueError('Chemin de logo hors dossier')
    path=(Path(root)/rel).resolve()
    if not path.is_relative_to(Path(root).resolve()):raise ValueError('Chemin de logo hors dossier')
    return path


def _mock_badge(name,order,side):
    """Plain fictitious crest ONLY for labelled preview; never in production."""
    colors=[(49,213,201),(255,171,74),(96,147,239),(237,99,119),(151,120,240),(111,204,129)]
    color=colors[(order*3+side)%len(colors)]
    tile=Image.new('RGBA',(252,252),(0,0,0,0));d=ImageDraw.Draw(tile)
    d.rounded_rectangle((19,15,233,240),radius=42,fill=(18,37,56),outline=color,width=9)
    d.polygon(((48,88),(126,36),(204,88),(195,179),(126,223),(57,179)),outline=color,width=6)
    bits=re.findall(r'[A-ZÀ-Ÿ0-9]+',name.upper());letters=''.join(b[0] for b in bits[:2]) if len(bits)>1 else name[:2].upper()
    text_center(d,126,128,letters[:3],72,color,max_width=173)
    return tile


@dataclass
class Crest:
    image: Image.Image
    real: bool


class LogoCache:
    def __init__(self,cache_dir,asset_root=None,preview=False):
        self.cache_dir=Path(cache_dir);self.cache_dir.mkdir(parents=True,exist_ok=True)
        self.asset_root=Path(asset_root or '.')
        self.preview=preview
        self.loaded={}
        self.real_count=0;self.fallback_count=0

    def get(self,clip,side,index):
        name=split_names(clip['headline'])[0 if side=='home' else 1]
        asset=clip.get(f'{side}_logo_asset')
        url=clip.get(f'{side}_logo_url')
        key=(str(asset),str(url),side,name)
        if key in self.loaded:
            # Counters represent requested logo *instances* in the video,
            # not just distinct downloaded files. A club appearing twice
            # must not cause a false missing-logo failure.
            cached=self.loaded[key]
            if cached.real:self.real_count+=1
            else:self.fallback_count+=1
            return cached
        try:
            if asset:
                p=_asset_path(asset,self.asset_root)
                if not p.is_file():raise ValueError('Écusson local introuvable')
                if p.stat().st_size>MAX_LOGO_BYTES:raise ValueError('Écusson local trop volumineux')
                image=_rasterize(p.read_bytes())
            elif url:
                if not _valid_logo_url(url):raise ValueError('URL logo non autorisée')
                p=self.cache_dir/(hashlib.sha256(url.encode()).hexdigest()+'.png')
                if p.is_file():image=_rasterize(p.read_bytes())
                else:
                    image=_fetch_logo(url)
                    image.save(p,format='PNG')
            else:
                raise ValueError('Écusson non fourni')
            found=Crest(image,True);self.real_count+=1
        except (OSError,ValueError,RuntimeError) as exc:
            if not self.preview:
                raise ValueError(f'Logo réel obligatoire pour {name} : {exc}') from exc
            found=Crest(_mock_badge(name,index,0 if side=='home' else 1),False)
            self.fallback_count+=1
        self.loaded[key]=found
        return found


def _logo_area(name,crest,accent):
    # Transparent logo on subtle backing. No fake ring atop authentic crest.
    canvas=Image.new('RGBA',(302,410),(0,0,0,0));d=ImageDraw.Draw(canvas)
    d.ellipse((54,22,250,218),fill=(15,40,60,255))
    d.ellipse((54,22,250,218),outline=(*accent,65),width=2)
    logo=crest.image.copy();logo.thumbnail((170,170),Image.Resampling.LANCZOS)
    canvas.alpha_composite(logo,(152-logo.width//2,120-logo.height//2))
    label=name.upper()
    pieces=label.split()
    if len(label)>14 and len(pieces)>1:
        center=len(pieces)//2
        lines=(' '.join(pieces[:center]),' '.join(pieces[center:]))
        for yy,line in zip((273,314),lines):
            text_center(d,152,yy,line,32,WHITE,max_width=290)
    else:
        text_center(d,152,286,label,37,WHITE,max_width=290)
    return canvas


def _match_scene(clip,index,total,logos,preview,tm):
    im=background().copy();d=ImageDraw.Draw(im)
    _brand(d)
    text_center(d,620,87,f'{index:02d}/{total:02d}',23,TEAL)
    h,a=split_names(clip['headline'])
    # Panels and score are composed at actual frame time in render().
    _progress(d,index-1,total)
    if preview:_demo_tag(d)
    return im,(_logo_area(h,logos[0],TEAL),_logo_area(a,logos[1],AMBER))


def slide(clip,number,total,preview=False):
    """Compatibility view for static quality checks: final composed single frame."""
    cache=LogoCache(Path(tempfile.gettempdir())/'mrx-preview-logos',preview=preview)
    crests=(cache.get(clip,'home',number),cache.get(clip,'away',number))
    frame,layers=_match_scene(clip,number,total,crests,preview,1.)
    frame.alpha_composite(layers[0],(45,350));frame.alpha_composite(layers[1],(371,350))
    d=ImageDraw.Draw(frame)
    text_center(d,360,782,clip['display_score'].replace('-', ' : '),151,WHITE,max_width=620)
    return frame


def soundtrack(path,duration,starts,volume=.40):
    """Original rhythm without copyrighted music, melody or samples."""
    rate=32000;n=int(duration*rate);out=np.zeros(n,dtype=np.float32)
    rng=np.random.default_rng(53)
    def add(t,signal):
        a=max(0,round(t*rate));end=min(n,a+len(signal))
        if end>a:out[a:end]+=signal[:end-a]
    beat=60/112
    for i in range(int(duration/beat)+2):
        t=i*beat
        xx=np.arange(int(.21*rate),dtype=np.float32)/rate
        kick=np.sin(2*np.pi*(62*xx+38*(1-np.exp(-30*xx))/30))*np.exp(-23*xx)
        add(t,.37*kick)
        hh=np.arange(int(.08*rate),dtype=np.float32)/rate
        add(t+beat/2,.048*rng.standard_normal(len(hh)).astype('float32')*np.exp(-54*hh))
    for t in starts[1:]:
        xx=np.arange(int(.18*rate),dtype=np.float32)/rate
        pip=np.sin(2*np.pi*(575*xx+350*xx*xx))*np.exp(-27*xx)
        add(t,.22*pip)
    pcm=np.int16(np.clip(np.tanh(out)*volume,-1,1)*32767)
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate)
        w.writeframes(pcm.astype('<i2').tobytes())


def validate_payload(data,preview=False,allow_partial_preview=False,
                     allow_partial_production=False):
    if not isinstance(data,dict):raise ValueError('Payload JSON invalide')
    clips=data.get('clips')
    if not isinstance(clips,list) or not 1<=len(clips)<=15:
        raise ValueError('Nombre de clips invalide')
    if not preview:
        if data.get('ready_for_video') is not True or data.get('status')!='READY':
            raise ValueError('Publication vidéo interdite : payload NOT READY')
        if allow_partial_production:
            if (data.get('publication_mode')!='flexible'
                    or not 1 <= len(clips) <= 10
                    or int(data.get('selected_count',-1))!=len(clips)):
                raise ValueError('Le mode flexible exige des matchs réels cohérents (1 à 10)')
        elif int(data.get('selected_count',-1))!=10 or len(clips)!=10:
            raise ValueError('Le mode production exige 10 matchs validés')
        now=datetime.now(timezone.utc)
        from datetime import date
        day=date.fromisoformat(data['date_local_africa_lome'])
        if day<now.date() or (day-now.date()).days>1:raise ValueError('Date périmée ou trop éloignée')
        generated=datetime.fromisoformat(str(data.get('generated_at_utc','')).replace('Z','+00:00'))
        if generated.tzinfo is None:raise ValueError('Horodatage non UTC')
        age=(now-generated.astimezone(timezone.utc)).total_seconds()
        if age < -120 or age>4*3600:raise ValueError('Pronostics trop anciens pour un rendu automatique')
        for c in clips:
            kickoff=datetime.fromisoformat(str(c.get('kickoff_utc','')).replace('Z','+00:00'))
            if kickoff.tzinfo is None or kickoff<=now:raise ValueError('Match commencé ou heure du coup d’envoi invalide')
    elif not allow_partial_preview and len(clips)<10:
        raise ValueError('Prévisualisation partielle non autorisée sans --allow-partial-preview')
    for clip in clips:
        if not isinstance(clip,dict) or 'headline' not in clip or 'display_score' not in clip:
            raise ValueError('Clip incomplet')
        split_names(clip['headline'])
        if len(clip['headline'])>128:raise ValueError('Affiche trop longue')
        if not re.fullmatch(r'\d{1,2}-\d{1,2}',str(clip['display_score'])):
            raise ValueError('Score exact mal formé')
        if 'display_probability_percent' in clip:
            pct=float(clip['display_probability_percent'])
            if not 0<pct<100:raise ValueError('Probabilité hors limites')
        if not preview:
            for side in ('home','away'):
                url=clip.get(f'{side}_logo_url')
                asset=clip.get(f'{side}_logo_asset')
                if not ((url and _valid_logo_url(url)) or asset):
                    raise ValueError(f'Logo officiel/réel requis : {side}')
                if asset and not re.fullmatch(r'[A-Za-z0-9_./-]{1,180}',asset):
                    raise ValueError('Chemin logo invalide')
    return clips


def ease(x):
    x=max(0.,min(1.,x))
    return 1-(1-x)**3


def render(payload,output,preview=False,allow_partial_preview=False,fps=FPS,fullhd=False,
           asset_root='.',logo_cache=None):
    clips=validate_payload(payload,preview=preview,allow_partial_preview=allow_partial_preview)
    if shutil.which('ffmpeg') is None:raise RuntimeError('ffmpeg introuvable')
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    total=INTRO+len(clips)*PER+OUTRO
    nframes=int(round(total*fps))
    starts=[0,INTRO]+[INTRO+PER*i for i in range(1,len(clips)+1)]
    with tempfile.TemporaryDirectory(prefix='mrx-minimal-studio-') as tmp:
        cache=LogoCache(logo_cache or Path(tmp)/'logos',asset_root,preview)
        logos=[(cache.get(c,'home',i),cache.get(c,'away',i)) for i,c in enumerate(clips,1)]
        panels=[_match_scene(c,i,len(clips),logos[i-1],preview,1.) for i,c in enumerate(clips,1)]
        # Preview logos may be fictional placeholders; production never substitutes fake crests.
        sound=Path(tmp)/'rhythm.wav';soundtrack(sound,total,starts)
        silent=Path(tmp)/'silent.mp4'
        cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo',
             '-pixel_format','rgb24','-video_size',f'{W}x{H}','-framerate',str(fps),'-i','pipe:0',
             '-c:v','libx264','-preset','veryfast','-pix_fmt','yuv420p','-crf','19','-movflags','+faststart',str(silent)]
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        assert proc.stdin
        try:
            for k in range(nframes):
                t=k/fps
                if t<INTRO:
                    frame=cover(len(clips),preview)
                    d=ImageDraw.Draw(frame)
                    # One quick oversized reveal on the first second.
                    if t<.25:d.rectangle((0,0,W,H),fill=(5,14,30,int(230*(1-ease(t/.25)))))
                elif t<INTRO+len(clips)*PER:
                    z=t-INTRO;idx=min(len(clips)-1,int(z/PER));u=z-idx*PER
                    frame=panels[idx][0].copy()
                    left,right=panels[idx][1]
                    entry=ease(u/.34)
                    shift=int((1-entry)*32)
                    frame.alpha_composite(left,(45-shift,350))
                    frame.alpha_composite(right,(371+shift,350))
                    # The score follows the crests in 0.2 s. No percentage or decorative data.
                    d=ImageDraw.Draw(frame)
                    pulse=ease((u-.12)/.29)
                    size=int(125+27*pulse)
                    score=clips[idx]['display_score'].replace('-', ' : ')
                    text_center(d,360,782,score,size,WHITE,max_width=614)
                    # One understated underline under the score that fills on entry.
                    width=int(150*ease((u-.26)/.35))
                    d.rounded_rectangle((360-width,900,360+width,908),radius=4,fill=TEAL)
                    if u>PER-.14:
                        fade=(u-(PER-.14))/.14
                        veil=Image.new('RGBA',(W,H),(6,14,30,int(95*fade)))
                        frame.alpha_composite(veil)
                else:
                    frame=ending(len(clips),preview)
                d=ImageDraw.Draw(frame)
                d.rectangle((0,0,int(W*(k+1)/nframes),5),fill=TEAL)
                proc.stdin.write(frame.convert('RGB').tobytes())
            proc.stdin.close()
            if proc.wait(timeout=240):raise RuntimeError(proc.stderr.read().decode(errors='replace')[-1400:])
        except Exception:
            try:proc.stdin.close()
            except (OSError,ValueError):pass
            proc.kill();proc.wait()
            raise
        cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(silent),'-i',str(sound)]
        if fullhd:cmd+=['-vf','scale=1080:1920:flags=lanczos',
                          '-c:v','libx264','-preset','medium','-pix_fmt','yuv420p','-crf','18']
        else:cmd+=['-c:v','copy']
        cmd+=['-c:a','aac','-b:a','160k','-ar','44100','-shortest','-movflags','+faststart',str(output)]
        subprocess.run(cmd,capture_output=True,check=True)
    return {'output':str(output),'duration_seconds':round(total,2),
            'resolution':'1080x1920' if fullhd else f'{W}x{H}',
            'fps':fps,'clips':len(clips),'preview':preview,
            'real_logo_instances':cache.real_count,
            'preview_placeholder_instances':cache.fallback_count,
            'size_bytes':output.stat().st_size}


def cli():
    parser=argparse.ArgumentParser(description='Mr XPRONOS minimal logo + score video')
    parser.add_argument('--payload',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--fullhd',action='store_true')
    parser.add_argument('--allow-partial-preview',action='store_true')
    parser.add_argument('--assets-root',default='.')
    parser.add_argument('--logo-cache',default=None)
    args=parser.parse_args()
    payload=json.loads(Path(args.payload).read_text(encoding='utf-8'))
    out=render(payload,args.output,preview=args.preview,fullhd=args.fullhd,
               allow_partial_preview=args.allow_partial_preview,
               asset_root=args.assets_root,logo_cache=args.logo_cache)
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__':cli()
