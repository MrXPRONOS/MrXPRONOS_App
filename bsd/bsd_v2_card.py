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
from bsd_v2_stakes import single_stake,gain_potentiel,money
from bsd_v2_labels import market_label
from bsd_v2_assets import bsd_logo_url

ROOT=Path(__file__).resolve().parent.parent
ASSETS=ROOT/"assets/images"
BALL=ASSETS/"bsd-football-generated.png"
BRAND_ONE=ASSETS/"1xbet.webp"
BRAND_TWO=ASSETS/"melbet.webp"
TEAM_ICON_CACHE={}
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
    return host in ("sports.bzzoiro.com","media.api-sports.io","cdn.sofascore.com",
                    "img.sofascore.com","cdn.bzzoiro.com",
                    "sports.bzzoiro.com","media.bzzoiro.com",
                    "www.thesportsdb.com","r2.thesportsdb.com")

def _lookup_team_badge(name,session):
    """Optional public team-logo resolution, never guess an ID or badge.

    Successful lookup requires exact normalized team name to avoid mistaking
    similarly named clubs from different countries.
    """
    import unicodedata
    def norm(value):
        return "".join(ch for ch in unicodedata.normalize("NFKD",str(value).casefold())
                       if ch.isalnum())
    target=norm(name)
    if not target:return None
    if target in TEAM_ICON_CACHE:return TEAM_ICON_CACHE[target]
    badge=None
    try:
        response=session.get("https://www.thesportsdb.com/api/v1/json/3/searchteams.php",
                             params={"t":name},timeout=8)
        response.raise_for_status()
        teams=response.json().get("teams") or []
        exact=[t for t in teams if norm(t.get("strTeam"))==target
               and str(t.get("strSport") or "").lower()=="soccer"]
        if len(exact)==1:
            candidate=exact[0].get("strBadge") or exact[0].get("strTeamBadge")
            if _public_https(candidate):badge=candidate
    except (requests.RequestException,ValueError,TypeError,AttributeError):
        pass
    TEAM_ICON_CACHE[target]=badge
    return badge


def _team_image(match,side,*,session=None):
    session=session or requests.Session()
    sources=[bsd_logo_url("team",match.get(side+"_team_id"))]
    sources.extend(match.get(key) for key in (side+"_logo",side+"_team_logo",side+"_logo_url"))
    # A named external fallback is only attempted when official BSD artwork fails.
    sources.append(None)
    for source in sources:
        if source is None:
            source=_lookup_team_badge(match.get(side+"_team") or "",session)
        if _public_https(source):
            try:
                response=session.get(source,timeout=8,
                  headers={"Accept":"image/png,image/webp,image/jpeg"},
                  allow_redirects=False)
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

def render(match,output,*,win=False,stake=None,now=None,session=None):
    """All simple/day/night/winning cards share the reference-style layout."""
    from bsd_v2_ticket_ui import render_single
    return render_single(match,output,win=win,stake=stake,now=now,session=session)
