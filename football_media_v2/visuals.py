"""Studio de motion design football 9:16, indépendant du générateur de coupons.

Art procédural original (tribunes, projecteurs, terrain, ballon et éclairages).
Ce ne sont ni des images de matchs réels, ni des reconstitutions d'événements.
"""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import hashlib
import math
import os
import random
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from .story import Scene

W,H,FPS=720,1280,24
WHITE=(247,249,252); GOLD=(255,192,44); CYAN=(49,217,245); DARK=(7,12,23)
BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf'
REG='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

@lru_cache(maxsize=35)
def ft(sz,bold=True):
    return ImageFont.truetype(BOLD if bold else REG,sz)

def run(command):
    result=subprocess.run(command,capture_output=True,text=True,timeout=240)
    if result.returncode: raise RuntimeError(result.stderr[-1800:])
    return result.stdout

def duration(path:Path)->float:
    out=run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)])
    return float(out.strip())

@lru_cache(maxsize=1)
def backdrop():
    y,x=np.mgrid[0:H,0:W].astype(np.float32)
    v=np.clip(y/H,0,1)
    warm=np.maximum(0,1-np.sqrt(((x-W*.82)/(W*.8))**2+((y-H*.22)/(H*.75))**2))
    stadium=np.zeros((H,W,3),dtype=np.uint8)
    stadium[:,:,0]=np.clip(6+v*4+warm*24,0,255)
    stadium[:,:,1]=np.clip(12+v*24+warm*12,0,255)
    stadium[:,:,2]=np.clip(27+v*11+warm*6,0,255)
    im=Image.fromarray(stadium)
    d=ImageDraw.Draw(im,'RGBA')
    rng=random.Random(10021)
    for _ in range(270):
        x1=rng.randrange(0,W); yy=rng.randrange(300,985)
        rr=rng.choice([1,1,2,2,3]); light=rng.randrange(16,90)
        d.ellipse((x1-rr,yy-rr,x1+rr,yy+rr),fill=(182,206,227,light))
    for j in range(11):
        y0=535+j*29
        d.arc((-340,y0-200,1050,y0+170),0,180,fill=(145,154,175,15),width=2)
    for x0,y0 in ((-110,60),(785,40)):
        d.polygon([(x0,y0),(W*.5,H*.8),(x0+175,y0+70)],fill=(155,186,255,17))
        for i in range(3):
            d.ellipse((x0+i*17,y0+i*9,x0+13+i*17,y0+14+i*9), fill=(250,254,255,180))
    d.ellipse((-200,780,920,1580),fill=(7,30,28,245))
    # stadium pitch perspective
    d.polygon([(42,920),(W-42,920),(W+190,H+30),(-190,H+30)],fill=(12,77,63,200))
    for x0 in range(4):
        yy=938+x0*80
        d.line([(60-x0*30,yy),(W-60+x0*30,yy)],fill=(80,214,150,30),width=2)
    d.line((W//2,926,W//2,H),fill=(163,246,201,38),width=3)
    d.ellipse((270,990,450,1170),outline=(153,239,198,48),width=3)
    # gold rim on left
    d.line((0,0,0,H),fill=(*GOLD,120),width=6)
    return im

def glow(im,center,colour,radius=175):
    overlay=Image.new('RGBA',(W,H),(0,0,0,0)); o=ImageDraw.Draw(overlay,'RGBA')
    for j in range(8,0,-1):
        rr=int(radius*j/8)
        o.ellipse((center[0]-rr,center[1]-rr,center[0]+rr,center[1]+rr),fill=(*colour,int(4+j/2)))
    im.alpha_composite(overlay)

def football(d:ImageDraw.ImageDraw,cx,cy,r=120):
    # Ball illustration made in code, NOT a real match photograph.
    d.ellipse((cx-r+12,cy-r+18,cx+r+20,cy+r+26),fill=(0,0,0,80))
    d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=(239,249,250,255),outline=(135,202,215,230),width=7)
    pts=[]
    for k in range(5):
        t=-math.pi/2+k*math.tau/5
        pts.append((cx+int(r*.38*math.cos(t)),cy+int(r*.38*math.sin(t))))
    d.polygon(pts,fill=(22,35,50,255))
    for k in range(5):
        a=pts[k]; t=-math.pi/2+k*math.tau/5
        edge=(cx+int(r*.9*math.cos(t)),cy+int(r*.9*math.sin(t)))
        d.line((a,edge),fill=(35,54,74,255),width=7)
    d.arc((cx-r+12,cy-r+10,cx+r-10,cy+r-5),190,270,fill=(156,175,194,230),width=4)

def stadium_athlete(d,side=1):
    # Purely symbolic silhouette; never represents a real player or a factual match action.
    sx=(418 if side==1 else 190); cy=810; ink=(9,19,35,240)
    d.ellipse((sx-40,cy-140,sx+25,cy-74),fill=ink)
    d.polygon([(sx-28,cy-80),(sx+25,cy-65),(sx+64,cy+46),(sx-72,cy+48)],fill=ink)
    d.line((sx-55,cy-34,sx-140,cy+35),fill=ink,width=29)
    d.line((sx+34,cy-33,sx+102,cy-90),fill=ink,width=27)
    d.line((sx-35,cy+28,sx-90,cy+130),fill=ink,width=40)
    d.line((sx+35,cy+27,sx+108,cy+120),fill=ink,width=40)
    d.ellipse((sx-75,cy-115,sx+65,cy+60),outline=(*GOLD,95),width=3)

def text_fit(d,text,maxwidth,maxsize,minsize=30):
    # Visual prominence: no word clipped or microscopic body.
    text=str(text).upper()
    for size in range(maxsize,minsize-1,-2):
        f=ft(size)
        if d.textbbox((0,0),text,font=f)[2]<=maxwidth:
            return f
    return ft(minsize)

def lines(text,maxchars=22,maxlines=3):
    words=str(text).split(); result=[]; cur=''
    for word in words:
        nxt=(cur+' '+word).strip()
        if len(nxt)>maxchars and cur:
            result.append(cur);cur=word
        else: cur=nxt
    if cur:result.append(cur)
    return result[:maxlines]

def scene_poster(scene:Scene,out:Path,index:int,total:int,watermark=False,photo:Path|None=None):
    im=backdrop().copy().convert('RGBA')
    if photo is not None and photo.is_file():
        try:
            with Image.open(photo) as source:
                source=source.convert('RGB')
                sw,sh=source.size
                # art-directed photograph with tinted overlay; never presented as real clip of this match
                factor=max(W/sw,H/sh)
                rw,rh=round(sw*factor),round(sh*factor)
                source=source.resize((rw,rh),Image.Resampling.LANCZOS)
                xx=max(0,(rw-W)//2);yy=max(0,(rh-H)//2)
                source=source.crop((xx,yy,xx+W,yy+H)).convert('RGBA')
                tint=Image.new('RGBA',(W,H),(1,7,15,115))
                source=Image.alpha_composite(source,tint)
                # preserve photographic action from midline to near bottom
                im.alpha_composite(source)
        except (OSError,ValueError):pass
    d=ImageDraw.Draw(im,'RGBA')
    special=scene.kind
    if special in ('hook','goal','verdict','score','scorer'):
        glow(im,(W*.68,H*.55),GOLD if special in ('hook','goal') else CYAN,220)
    if special in ('pitch','versus','stadium','source','cta'):
        glow(im,(W*.48,H*.48),CYAN,260)
    d=ImageDraw.Draw(im,'RGBA')
    # Original illustrative athlete/ball only when no licensed illustrative photograph.
    if photo is None and special in ('stadium','pitch','versus','cta'):
        stadium_athlete(d,side=(1 if index%2 else -1))
        football(d, 485 if index%2 else 175, 930, 56)
    if photo is None and special in ('hook','goal','score','verdict','scorer','source'):
        football(d, 535, 755, 115 if special in ('hook','goal') else 76)
        for step in range(4):
            d.arc((180-step*13,490-step*13,790+step*13,1110+step*13),205,290,
                  fill=(*GOLD,55-step*8),width=5)
    # translucent horizontal panel for bold typography
    d.rounded_rectangle((28,265,692,638),radius=25,fill=(5,10,20,210),outline=(220,234,249,35),width=2)
    d.rounded_rectangle((33,270,40,635),radius=3,fill=(*GOLD,255))
    d.rectangle((0,0,W,128),fill=(7,11,22,240))
    d.text((40,33),'MR',font=ft(33),fill=WHITE)
    d.text((104,33),'XPRONOS',font=ft(33),fill=GOLD)
    d.text((470,50),'FOOTBALL',font=ft(22),fill=(*CYAN,255))
    d.rectangle((40,147,140,154),fill=(*GOLD,245))
    d.text((44,184),scene.eyebrow.upper(),font=text_fit(d,scene.eyebrow,625,29,18),fill=(*GOLD,255))
    chunks=lines(scene.headline,20,3)
    # Fit largest heading to panel height; no text overflow
    size=94
    for attempt in range(94,43,-2):
        if len(chunks)*(attempt+12)<=240 and all(d.textbbox((0,0),v,font=ft(attempt))[2]<=610 for v in chunks):
            size=attempt;break
    else: size=44
    y=309 + max(0,(225-len(chunks)*(size+12))//2)
    for line in chunks:
        d.text((58,y),line,font=ft(size),fill=(*WHITE,255),stroke_width=1,stroke_fill=(7,10,20,255))
        y+=size+12
    # Flashy concise subtitle at scene midpoint
    caption=lines(scene.sub,18,2)
    y=660
    for line in caption:
        f=text_fit(d,line,614,34,22)
        d.rounded_rectangle((37,y-7,683,y+53),radius=12,fill=(19,31,46,210))
        d.text((53,y),line,font=f,fill=(*CYAN,255))
        y+=66
    if special in ('score','goal','scorer'):
        d.rectangle((65,882,655,885),fill=(*GOLD,160))
        for n in range(23):
            xa=68+n*24; ha=round(24+13*math.sin(n*1.2))
            d.rectangle((xa,925-ha,xa+10,925+ha),fill=(*GOLD,90))
    if photo is not None:
        d.rounded_rectangle((35,1106,290,1144),radius=8,fill=(6,11,21,220))
        d.text((47,1113),'PHOTO D’ILLUSTRATION',font=ft(18),fill=WHITE)
    d.rounded_rectangle((28,1160,692,1220),radius=10,fill=(8,13,25,245),outline=(255,192,44,90),width=2)
    d.text((45,1176),'MR XPRONOS  /  FOOTBALL STORIES',font=ft(24),fill=WHITE)
    d.text((610,1177),f'{index+1:02}',font=ft(23),fill=GOLD)
    # top progress line, generated frame by frame in ffmpeg overlay omitted deliberately
    d.rectangle((28,1250,692,1257),fill=(42,56,68,255))
    d.rectangle((28,1250,28+int(664*(index+1)/total),1257),fill=(*GOLD,255))
    if watermark:
        d.rectangle((0,1060,720,1110),fill=(128,0,0,220))
        d.text((50,1071),'DÉMONSTRATION FICTIVE • NON PUBLIABLE',font=ft(21),fill=WHITE)
    out.parent.mkdir(parents=True,exist_ok=True)
    im.convert('RGB').save(out,quality=95)


def scene_video(image:Path,out:Path,seconds:float,index:int):
    # Real motion via animated camera and a scale/position change, not static slide encoding.
    frames=max(30,int(seconds*FPS))
    zoom='min(zoom+0.0014,1.13)' if index%2==0 else 'if(eq(on,0),1.12,max(1.0,zoom-0.0014))'
    motion=f"zoompan=z='{zoom}':x='iw/2-iw/zoom/2+sin(on/18)*7':y='ih/2-ih/zoom/2':d=1:s={W}x{H}:fps={FPS},eq=contrast=1.045:saturation=1.10,format=yuv420p"
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-loop','1','-framerate',str(FPS),'-i',str(image),
         '-frames:v',str(frames),'-vf',motion,'-c:v','libx264','-preset',os.getenv('FOOTBALL_FFMPEG_PRESET','veryfast'),
         '-crf','24','-pix_fmt','yuv420p','-an',str(out)])


def licensed_clip_video(source:Path,out:Path,seconds:float):
    # Never include the source audio (rights are different), use synthetic soundtrack.
    vf=f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},eq=contrast=1.03:saturation=1.10,format=yuv420p'
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(source),'-t',str(seconds),
         '-vf',vf,'-an','-c:v','libx264','-preset','veryfast','-crf','23',str(out)])


def concat_video(files:list[Path],output:Path):
    concat=output.parent/'segments.txt'
    concat.write_text(''.join("file '"+str(p.resolve()).replace("'","'\\''")+"'\n" for p in files),'utf8')
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(concat),'-c','copy',str(output)])
    concat.unlink(missing_ok=True)
