"""Render football prediction cards, following the supplied basketball receipt layout.

These are analytical prediction cards, not bookmaker-issued betting slips.
All odds originate from verified BSD fields; no placement or payout is implied.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from io import BytesIO
from urllib.parse import urlparse
import ipaddress
import socket
import requests
from PIL import Image, ImageDraw, ImageFont
from bsd_h2h import _utc

ROOT=Path(__file__).resolve().parent.parent
ASSETS=ROOT/"assets/images"
BALL=ASSETS/"bsd-football-generated.png"
BRAND_ONE=ASSETS/"1xbet.webp"
BRAND_TWO=ASSETS/"melbet.webp"
INK="#12334c"; MUTED="#6a8ba2"; GREEN="#34b466"; BORDER="#dde3e8"
W,H=1080,1300
ALLOWED_ODD_SOURCES=("bsd_consensus","bsd_bookmaker")

def font(size,bold=False):
    for p in (["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
               "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"] if bold else
              ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
               "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]):
        if Path(p).exists():return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def width(draw,s,f):
    return draw.textbbox((0,0),str(s),font=f)[2]

def write(draw,text,x,y,*,size=30,bold=False,color=INK,maximum=None,align="left"):
    text=str(text or "")
    f=font(size,bold)
    if maximum:
        while width(draw,text,f)>maximum and len(text)>3:
            text=text[:-2].rstrip("…")+"…"
    measured=width(draw,text,f)
    if align=="right":x-=measured
    elif align=="center":x-=measured/2
    draw.text((int(x),int(y)),text,font=f,fill=color)
    return measured

def wrap_name(draw,name,max_width,size=32,max_lines=2):
    words=str(name or "Équipe").split()
    lines=[""]
    for word in words:
        candidate=(lines[-1]+" "+word).strip()
        if lines[-1] and width(draw,candidate,font(size,True))>max_width and len(lines)<max_lines:
            lines.append(word)
        else:lines[-1]=candidate
    while width(draw,lines[-1],font(size,True))>max_width and len(lines[-1])>3:
        lines[-1]=lines[-1][:-2]+"…"
    return lines

def paste_asset(canvas,path,x,y,box_w,box_h,required=False):
    if not Path(path).is_file():
        if required:raise FileNotFoundError("Required logo not found: "+str(path))
        return False
    with Image.open(path) as raw:icon=raw.convert("RGBA")
    icon.thumbnail((box_w,box_h),Image.Resampling.LANCZOS)
    canvas.paste(icon,(int(x+(box_w-icon.width)/2),int(y+(box_h-icon.height)/2)),icon)
    return True

def _public_https(url):
    parsed=urlparse(str(url or ""))
    if parsed.scheme!="https" or not parsed.hostname or parsed.username:
        return False
    host=parsed.hostname.lower()
    if host in ("localhost",) or host.endswith(".local"):return False
    try:
        addr=ipaddress.ip_address(host)
        return addr.is_global
    except ValueError:pass
    # Explicit host allowlist prevents malicious BSD payloads from reaching
    # GitHub runner metadata/internal addresses.
    return host in ("media.api-sports.io","cdn.sofascore.com",
                    "img.sofascore.com","cdn.bzzoiro.com",
                    "sports.bzzoiro.com","media.bzzoiro.com",
                    "www.thesportsdb.com","r2.thesportsdb.com")

def _team_image(match,side,*,session=None):
    for key in (side+"_logo",side+"_team_logo",side+"_logo_url"):
        source=match.get(key)
        if _public_https(source):
            try:
                session=session or requests.Session()
                response=session.get(source,timeout=7,headers={"Accept":"image/png,image/webp,image/jpeg"})
                response.raise_for_status()
                if len(response.content)>1000000:continue
                with Image.open(BytesIO(response.content)) as original:
                    if original.width*original.height>4000000:continue
                    return original.convert("RGBA")
            except (requests.RequestException,ValueError,OSError):
                pass
    return None

def team_logo(canvas,draw,match,side,x,y,*,size=92,session=None):
    image=_team_image(match,side,session=session)
    if image is not None:
        image.thumbnail((size,size),Image.Resampling.LANCZOS)
        canvas.paste(image,(int(x+(size-image.width)/2),int(y+(size-image.height)/2)),image)
        return True
    # A neutral fallback shows that the true team crest is unavailable.
    draw.ellipse((x+5,y+5,x+size-5,y+size-5),fill="#eff3f6",outline="#cfdce4",width=2)
    name=str(match.get(side+"_team") or "")
    acronym="".join(part[:1] for part in name.split()[:2]).upper() or "FC"
    write(draw,acronym,x+size/2,y+size/2-19,size=27,bold=True,
          color=MUTED,align="center")
    return False

def _odds(match):
    p=match.get("prediction") or {}
    odds=p.get("odds")
    try:
        odds=float(odds)
        if not (1.20<=odds<=100 and p.get("odds_source") in ALLOWED_ODD_SOURCES):
            return None
        return odds
    except (ValueError,TypeError):return None

def render(match,output,*,win=False,stake=500000,now=None,session=None):
    now=now or datetime.now(timezone.utc)
    kickoff=_utc(match["event_date"])
    pred=match.get("prediction") or {}
    odds=_odds(match)
    price=f"{odds:.2f}" if odds is not None else "Indisponible"
    gross=f"{round(stake*odds):,}".replace(","," ")+" F" if odds else "—"
    image=Image.new("RGB",(W,H),"#f0f2f5")
    d=ImageDraw.Draw(image)
    d.rectangle((0,0,W,128),fill="#070707")
    # Use the brand's original image files already committed to the site.
    paste_asset(image,BRAND_ONE,28,32,224,65,required=True)
    write(d,"ou",280,52,size=30,color="#dfdfdf")
    paste_asset(image,BRAND_TWO,336,32,244,65,required=True)
    d.rounded_rectangle((630,28,1050,101),radius=9,fill="#ffda34")
    write(d,"Code Promo: XPVIP",839,47,size=31,bold=True,color="#121212",align="center")
    d.rounded_rectangle((18,145,1062,1270),radius=26,fill="#ffffff",outline="#dce3e8",width=2)
    paste_asset(image,BALL,50,181,104,104,required=True)
    write(d,now.strftime("%d.%m.%Y (%H:%M)"),181,181,size=31,color=MUTED)
    write(d,"Simple",181,226,size=51,bold=True)
    write(d,"N° "+str(match.get("id") or "—"),181,297,size=28,maximum=815)
    d.line((34,376,1046,376),fill=BORDER,width=3)
    # Aligned left/right financial summary; "gain" is projected, not confirmed payment.
    rows=(("Cotes:",price),("Mise:",f"{stake:,}".replace(","," ")+" F"),
          ("Gains potentiels:",gross),
          ("Statut:","Pronostic gagnant" if win else "Pronostic"))
    for i,(key,value) in enumerate(rows):
        y=408+i*64
        write(d,key,56,y,size=31,color=MUTED)
        write(d,value,1018,y,size=31,bold=i<3,color=GREEN if win and i==3 else INK,align="right")
    d.rounded_rectangle((18,690,1062,1210),radius=24,fill="#ffffff",outline=BORDER,width=2)
    paste_asset(image,BALL,54,727,70,70,required=True)
    write(d,"Football. "+str(match.get("league") or "Compétition"),136,722,
          size=29,color=MUTED,maximum=840)
    write(d,kickoff.strftime("%d.%m.%Y (%H:%M UTC)"),136,764,size=25,color=MUTED)
    # Ticket arrangement: left name -> left crest -> VS/score -> right crest -> right name.
    left=str(match.get("home_team") or "Équipe domicile")
    right=str(match.get("away_team") or "Équipe extérieur")
    y_center=908
    for line_index,line in enumerate(wrap_name(d,left,264,size=33)):
        write(d,line,281,y_center-52+line_index*43,size=33,bold=True,align="right",maximum=255)
    team_logo(image,d,match,"home",302,y_center-50,session=session)
    middle=(str(match.get("home_score"))+":"+str(match.get("away_score"))) if win else "VS"
    write(d,middle,540,y_center-39,size=52,bold=True,align="center",maximum=175)
    team_logo(image,d,match,"away",686,y_center-50,session=session)
    for line_index,line in enumerate(wrap_name(d,right,255,size=33)):
        write(d,line,795,y_center-52+line_index*43,size=33,bold=True,maximum=255)
    d.line((56,1019,1022,1019),fill=BORDER,width=2)
    write(d,pred.get("type") or pred.get("label") or "Pronostic",58,1044,
          size=31,bold=True,maximum=740)
    write(d,price,1020,1044,size=31,bold=True,align="right")
    write(d,"Statut:",58,1125,size=29,color=MUTED)
    write(d,"Gain" if win else "Pronostic",1017,1125,size=32,
          color=GREEN if win else INK,bold=win,align="right")
    write(d,"Parier responsablement.",540,1234,size=23,color=MUTED,align="center")
    destination=Path(output)
    destination.parent.mkdir(parents=True,exist_ok=True)
    image.save(destination,"PNG",optimize=True)
    return destination
