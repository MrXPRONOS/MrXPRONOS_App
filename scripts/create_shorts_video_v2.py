#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mr XPRONOS — générateur Shorts premium BSD V2.

Le script est volontairement séparé du générateur historique jusqu'à validation.
Stages de test cumulatifs:
1 = compatibilité BSD V2 + informations correctes
2 = identité premium (logo, Lato, hiérarchie, métriques)
3 = mouvement léger / transitions
4 = voix Edge TTS + sous-titres + sound design synthétique
5 = intro/outro, safe zones et finition finale
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import tempfile
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

# MoviePy 1.0.3 compatibility with Pillow >= 10.
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

ROOT = Path.cwd()
WORK = ROOT / "telegram_out" / "shorts_premium"
SCENES = WORK / "scenes"
AUDIO = WORK / "audio"
CACHE = WORK / "cache"
W, H = 1080, 1920
FPS = 30

COLORS = {
    "bg": "#090A0D",
    "panel": "#111319",
    "panel2": "#171A21",
    "gold": "#D6B04B",
    "gold2": "#F2D77D",
    "white": "#F8F8F6",
    "muted": "#A7ABB4",
    "green": "#34D399",
    "red": "#F87171",
}

CATEGORY_RANK = {"VIP": 3, "PRO": 2, "SIMPLE": 1}


@dataclass
class Pick:
    match_id: str
    event_date: str
    league: str
    home: str
    away: str
    home_logo: str
    away_logo: str
    category: str
    selection_key: str
    label: str
    confidence: float
    model_probability: float
    odds: Optional[float]
    fair_odds: Optional[float]
    odds_source: str
    estimated_odds: bool
    expected_goals_total: Optional[float]
    league_samples: Optional[int]
    home_recent_matches: Optional[int]
    away_recent_matches: Optional[int]
    recommendation_eligible: bool
    technical_fallback: bool = False


def rgb(hexv: str):
    h = hexv.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def fnum(v) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


def inum(v) -> Optional[int]:
    try:
        if v is None or v == "":
            return None
        return int(round(float(v)))
    except Exception:
        return None


def font_path(bold=False, premium=False):
    candidates = []
    if premium:
        candidates += [
            "/usr/share/fonts/truetype/lato/Lato-Heavy.ttf" if bold else "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
            "/usr/share/fonts/truetype/lato/Lato-Bold.ttf" if bold else "/usr/share/fonts/truetype/lato/Lato-Medium.ttf",
        ]
    candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    return ""


def font(size, bold=False, premium=False):
    p = font_path(bold, premium)
    if p:
        return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def fit_lines(draw, text, ft, max_width, max_lines=2):
    words = re.sub(r"\s+", " ", str(text or "")).strip().split()
    lines, cur = [], ""
    for word in words:
        test = (cur + " " + word).strip()
        box = draw.textbbox((0, 0), test, font=ft)
        if box[2]-box[0] <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and draw.textbbox((0,0), last+"…", font=ft)[2] > max_width:
            last = last[:-1]
        lines[-1] = last.rstrip()+"…"
    return lines


def centered(draw, text, ft, y, fill, x=W//2):
    box = draw.textbbox((0, 0), text, font=ft)
    draw.text((x-(box[2]-box[0])/2, y), text, font=ft, fill=fill)


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def gradient(stage: int):
    base = Image.new("RGB", (W, H), rgb(COLORS["bg"]))
    if stage < 2:
        return base
    arr = np.array(base).astype(np.float32)
    yy = np.linspace(0, 1, H)[:, None, None]
    warm = np.array(rgb("#19150C"), dtype=np.float32)[None, None, :]
    arr = arr * (1-0.34*yy) + warm * (0.34*yy)
    img = Image.fromarray(np.clip(arr,0,255).astype(np.uint8)).convert("RGBA")
    glow = Image.new("RGBA", (W,H), (0,0,0,0))
    g = ImageDraw.Draw(glow)
    gold = rgb(COLORS["gold"])
    g.ellipse((-250,-220,680,650), fill=gold+(35,))
    g.ellipse((620,1250,1450,2150), fill=gold+(20,))
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    img = Image.alpha_composite(img, glow)
    # grille très subtile
    gd = ImageDraw.Draw(img)
    for x in range(0, W, 90):
        gd.line((x, 0, x, H), fill=(255,255,255,7), width=1)
    for y in range(0, H, 90):
        gd.line((0, y, W, y), fill=(255,255,255,6), width=1)
    return img.convert("RGB")


def market_label(pred: Dict):
    code = str(pred.get("selection_key") or pred.get("key") or "").upper().strip()
    explicit = pred.get("label") or pred.get("type") or pred.get("name")
    fixed = {
        "1": "Victoire domicile",
        "X": "Match nul",
        "2": "Victoire extérieur",
        "1X": "Double chance 1X",
        "X2": "Double chance X2",
        "12": "Double chance 12",
        "BTTS_YES": "Les deux équipes marquent · OUI",
        "BTTS_NO": "Les deux équipes marquent · NON",
        "OVER_15": "Total buts · Over 1,5",
        "OVER_25": "Total buts · Over 2,5",
        "OVER_35": "Total buts · Over 3,5",
        "OVER_45": "Total buts · Over 4,5",
        "UNDER_15": "Total buts · Under 1,5",
        "UNDER_25": "Total buts · Under 2,5",
        "UNDER_35": "Total buts · Under 3,5",
        "UNDER_45": "Total buts · Under 4,5",
    }
    return fixed.get(code) or str(explicit or code or "Pronostic")


def parse_pick(m: Dict, technical_fallback=False) -> Optional[Pick]:
    pred = m.get("prediction") or {}
    if not isinstance(pred, dict):
        return None
    key = str(pred.get("selection_key") or pred.get("key") or "").strip()
    if not key:
        # ancien format, uniquement pour robustesse
        key = str(pred.get("double_chance") or "").strip()
    if not key:
        return None
    audit = m.get("model_audit") or {}
    conf = fnum(pred.get("conservative_probability"))
    if conf is None:
        conf = fnum(pred.get("confidence"))
    if conf is None:
        conf = fnum(pred.get("model_probability"))
    conf = clamp(conf or 0, 0, 100)
    modelp = clamp(fnum(pred.get("model_probability")) or conf, 0, 100)
    return Pick(
        match_id=str(m.get("id") or m.get("source_event_id") or ""),
        event_date=str(m.get("event_date") or m.get("date") or ""),
        league=str(m.get("league") or "Football"),
        home=str(m.get("home_team") or "Équipe domicile"),
        away=str(m.get("away_team") or "Équipe extérieur"),
        home_logo=str(m.get("home_logo") or ""),
        away_logo=str(m.get("away_logo") or ""),
        category=str(m.get("category") or "SIMPLE").upper(),
        selection_key=key.upper(),
        label=market_label({**pred, "selection_key": key}),
        confidence=conf,
        model_probability=modelp,
        odds=fnum(pred.get("odds")),
        fair_odds=fnum(pred.get("fair_odds")),
        odds_source=str(pred.get("odds_source") or ""),
        estimated_odds=bool(pred.get("estimated_odds")),
        expected_goals_total=fnum(audit.get("expected_goals_total")),
        league_samples=inum(audit.get("league_samples")),
        home_recent_matches=inum(audit.get("home_recent_matches")),
        away_recent_matches=inum(audit.get("away_recent_matches")),
        recommendation_eligible=bool(m.get("recommendation_eligible", False)),
        technical_fallback=technical_fallback,
    )


def parse_dt(value: str):
    try:
        s = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.max.replace(tzinfo=timezone.utc)


def select_picks(data: Dict, limit=3) -> Tuple[List[Pick], bool]:
    now = datetime.now(timezone.utc)
    rows = data.get("matches") if isinstance(data, dict) else []
    rows = rows if isinstance(rows, list) else []
    valid = []
    fallback = []
    for m in rows:
        if not isinstance(m, dict) or m.get("is_finished"):
            continue
        dt = parse_dt(str(m.get("event_date") or m.get("date") or ""))
        if dt < now:
            continue
        p = parse_pick(m)
        if not p:
            continue
        fallback.append((m, p))
        if p.recommendation_eligible:
            valid.append((m, p))

    use_fallback = not valid
    source = fallback if use_fallback else valid

    def rank(item):
        m, p = item
        freshness = 1 if p.odds_source in ("bsd_consensus","bsd_bookmaker") and not p.estimated_odds else 0
        return (
            CATEGORY_RANK.get(p.category, 0),
            freshness,
            p.confidence,
            -parse_dt(p.event_date).timestamp(),
        )
    source.sort(key=rank, reverse=True)
    picks = []
    for m, p in source[:limit]:
        if use_fallback:
            p.technical_fallback = True
        picks.append(p)
    return picks, use_fallback


def fetch_asset(path_or_url: str, key: str) -> Optional[Path]:
    if not path_or_url:
        return None
    p = Path(path_or_url.replace("\\","/"))
    candidates = [p, ROOT/p]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    if path_or_url.startswith(("http://","https://")):
        CACHE.mkdir(parents=True, exist_ok=True)
        ext = Path(urlparse(path_or_url).path).suffix or ".png"
        out = CACHE / (re.sub(r"[^A-Za-z0-9_-]+","_",key)[:80] + ext)
        if out.exists() and out.stat().st_size > 100:
            return out
        try:
            r = requests.get(path_or_url, timeout=12, headers={"User-Agent":"MrXPRONOS-Shorts/2"})
            if r.ok and len(r.content) > 100:
                out.write_bytes(r.content)
                return out
        except Exception:
            return None
    return None


def circle_logo(path_or_url: str, team: str, size=170, premium=False):
    canvas = Image.new("RGBA",(size,size),(0,0,0,0))
    d = ImageDraw.Draw(canvas)
    d.ellipse((1,1,size-2,size-2), fill=rgb(COLORS["panel2"])+(255,), outline=rgb(COLORS["gold"])+(255,), width=3)
    p = fetch_asset(path_or_url, team)
    if p:
        try:
            im = Image.open(p).convert("RGBA")
            im = ImageOps.contain(im,(size-26,size-26))
            canvas.alpha_composite(im,((size-im.width)//2,(size-im.height)//2))
            return canvas
        except Exception:
            pass
    initials="".join(x[:1] for x in team.split()[:2]).upper()[:2] or "FC"
    ft=font(44,True,premium)
    box=d.textbbox((0,0),initials,font=ft)
    d.text(((size-(box[2]-box[0]))/2,(size-(box[3]-box[1]))/2-4),initials,font=ft,fill=rgb(COLORS["white"])+(255,))
    return canvas


def paste_brand_logo(img: Image.Image, stage: int):
    if stage < 2:
        return
    p = ROOT / "assets" / "images" / "mrxpronos-logo-maquette.png"
    if not p.exists():
        return
    try:
        logo = Image.open(p).convert("RGBA")
        logo.thumbnail((250,90), Image.Resampling.LANCZOS)
        img.alpha_composite(logo,(64,48))
    except Exception:
        pass


def fmt_time(value):
    dt=parse_dt(value)
    if dt.year >= 9999:
        return ""
    return dt.strftime("%d/%m · %H:%M UTC")


def metric_chip(draw, x, y, w, title, value, premium):
    rounded(draw,(x,y,x+w,y+114),25,fill=rgb(COLORS["panel2"])+(245,),outline=(255,255,255,18),width=1)
    draw.text((x+24,y+18),title,font=font(22,False,premium),fill=rgb(COLORS["muted"]))
    draw.text((x+24,y+51),value,font=font(32,True,premium),fill=rgb(COLORS["white"]))


def render_pick(p: Pick, idx: int, stage: int, out: Path):
    premium=stage>=2
    img=gradient(stage).convert("RGBA")
    d=ImageDraw.Draw(img)
    gold=rgb(COLORS["gold"])
    white=rgb(COLORS["white"])
    muted=rgb(COLORS["muted"])

    paste_brand_logo(img,stage)
    if stage < 2:
        d.text((64,58),"MR XPRONOS",font=font(44,True,False),fill=gold)
    d.text((64,150 if stage>=2 else 122),f"PRONO {idx}",font=font(24,True,premium),fill=muted)

    # badges
    cat=p.category
    cf=font(25,True,premium)
    cb=d.textbbox((0,0),cat,font=cf)
    bx=W-64-(cb[2]-cb[0])-54
    rounded(d,(bx,58,W-64,112),26,fill=gold+(255,))
    d.text((bx+27,70),cat,font=cf,fill=(10,10,10))
    if p.technical_fallback:
        rounded(d,(64,190,520,242),22,fill=rgb(COLORS["red"])+(35,),outline=rgb(COLORS["red"])+(180,),width=2)
        d.text((84,202),"TEST TECHNIQUE · non publiable",font=font(20,True,premium),fill=rgb(COLORS["red"]))

    top=270 if p.technical_fallback else 235
    rounded(d,(50,top,W-50,1280),44,fill=rgb(COLORS["panel"])+(240,),outline=gold+(180,),width=2)

    league = p.league.upper()
    lf=font(27,True,premium)
    for j,line in enumerate(fit_lines(d,league,lf,W-180,2)):
        centered(d,line,lf,top+48+j*34,muted)

    logo_y=top+190
    ls=178
    home_logo=circle_logo(p.home_logo,p.home,ls,premium)
    away_logo=circle_logo(p.away_logo,p.away,ls,premium)
    img.alpha_composite(home_logo,(146,logo_y))
    img.alpha_composite(away_logo,(W-146-ls,logo_y))
    centered(d,"VS",font(40,True,premium),logo_y+62,gold)

    tf=font(43,True,premium)
    for j,line in enumerate(fit_lines(d,p.home,tf,360,2)):
        box=d.textbbox((0,0),line,font=tf)
        d.text((235-(box[2]-box[0])/2,logo_y+220+j*49),line,font=tf,fill=white)
    for j,line in enumerate(fit_lines(d,p.away,tf,360,2)):
        box=d.textbbox((0,0),line,font=tf)
        d.text((W-235-(box[2]-box[0])/2,logo_y+220+j*49),line,font=tf,fill=white)

    centered(d,fmt_time(p.event_date),font(23,False,premium),logo_y+330,muted)

    # prediction hero
    py=top+625
    rounded(d,(100,py,W-100,py+250),34,fill=rgb(COLORS["panel2"])+(250,),outline=gold+(210,),width=2)
    centered(d,"PRONOSTIC",font(23,True,premium),py+28,muted)
    pf=font(48 if len(p.label)<28 else 40,True,premium)
    lines=fit_lines(d,p.label,pf,W-265,2)
    sy=py+86
    for line in lines:
        centered(d,line,pf,sy,gold)
        sy+=58

    # core metrics
    ctext=f"{p.confidence:.0f}%"
    otext=f"{p.odds:.2f}" if p.odds else "—"
    metric_chip(d,104,top+910,250,"Confiance modèle",ctext,premium)
    metric_chip(d,415,top+910,250,"Cote",otext,premium)
    source="BSD" if p.odds_source in ("bsd_consensus","bsd_bookmaker") and not p.estimated_odds else "Estimée"
    metric_chip(d,726,top+910,250,"Source cote",source,premium)

    # richer model facts at stage 2+
    if stage>=2:
        fact_y=1340
        rounded(d,(65,fact_y,W-65,fact_y+250),34,fill=rgb(COLORS["panel"])+(225,))
        d.text((100,fact_y+28),"LECTURE DU MODÈLE",font=font(24,True,premium),fill=muted)
        facts=[]
        if p.expected_goals_total is not None:
            facts.append(("Buts attendus",f"{p.expected_goals_total:.2f}"))
        if p.league_samples is not None:
            facts.append(("Matchs de ligue",str(p.league_samples)))
        recent=min(x for x in [p.home_recent_matches,p.away_recent_matches] if x is not None) if any(x is not None for x in [p.home_recent_matches,p.away_recent_matches]) else None
        if recent is not None:
            facts.append(("Forme récente",f"{recent}+ / équipe"))
        while len(facts)<3:
            facts.append(("Marché",p.selection_key))
        x=100
        for title,val in facts[:3]:
            draw_metric_width=280
            d.text((x,fact_y+86),title,font=font(20,False,premium),fill=muted)
            d.text((x,fact_y+122),val,font=font(31,True,premium),fill=white)
            x+=300

    # confidence bar
    by=1640 if stage>=2 else 1450
    d.text((90,by-45),"INDICE DE CONFIANCE",font=font(22,True,premium),fill=muted)
    rounded(d,(90,by,W-90,by+34),17,fill=(50,53,61,255))
    fill=int((W-180)*p.confidence/100)
    rounded(d,(90,by,90+fill,by+34),17,fill=gold+(255,))
    d.text((W-180,by-52),f"{p.confidence:.0f}%",font=font(28,True,premium),fill=white)

    # safe-zone footer
    footer_y=1775
    centered(d,"Analyse statistique • 18+ • Joue responsablement",font(22,False,premium),footer_y,muted)
    if stage>=5:
        centered(d,"mrxpronos.github.io",font(20,True,premium),footer_y+42,gold)

    out.parent.mkdir(parents=True,exist_ok=True)
    img.convert("RGB").save(out,quality=96,subsampling=0)


def render_intro(stage, out):
    img=gradient(stage).convert("RGBA")
    paste_brand_logo(img,stage)
    d=ImageDraw.Draw(img)
    white=rgb(COLORS["white"]); gold=rgb(COLORS["gold"]); muted=rgb(COLORS["muted"])
    centered(d,"3 PRONOS",font(92,True,True),650,white)
    centered(d,"À SURVEILLER",font(92,True,True),755,gold)
    centered(d,"AUJOURD’HUI",font(64,True,True),870,white)
    rounded(d,(290,1010,790,1070),30,fill=gold+(255,))
    centered(d,"BSD V2 · ANALYSE MODÈLE",font(22,True,True),1025,(10,10,10))
    centered(d,"Test visuel premium",font(26,False,True),1160,muted)
    centered(d,"18+ • Joue responsablement",font(22,False,True),1775,muted)
    out.parent.mkdir(parents=True,exist_ok=True)
    img.convert("RGB").save(out,quality=96)


def render_outro(stage,out):
    img=gradient(stage).convert("RGBA")
    paste_brand_logo(img,stage)
    d=ImageDraw.Draw(img)
    white=rgb(COLORS["white"]); gold=rgb(COLORS["gold"]); muted=rgb(COLORS["muted"])
    centered(d,"PLUS DE PRONOS",font(72,True,True),690,white)
    centered(d,"SUR MR XPRONOS",font(72,True,True),780,gold)
    rounded(d,(205,955,875,1055),35,fill=gold+(255,))
    centered(d,"mrxpronos.github.io",font(33,True,True),984,(10,10,10))
    centered(d,"Analyse • Discipline • Responsabilité",font(27,False,True),1180,muted)
    centered(d,"18+ • Joue responsablement",font(22,False,True),1775,muted)
    out.parent.mkdir(parents=True,exist_ok=True)
    img.convert("RGB").save(out,quality=96)


def narration(p: Pick, idx: int):
    odds = f" La cote affichée est {str(round(p.odds,2)).replace('.',',')}." if p.odds else ""
    return (
        f"Prono {idx}. {p.home} contre {p.away}. "
        f"Le modèle retient {p.label}. "
        f"Confiance conservatrice, environ {int(round(p.confidence))} pour cent."
        f"{odds}"
    )


async def edge_tts_to(text: str, out: Path):
    import edge_tts
    voice=os.getenv("TTS_VOICE","fr-FR-RemyMultilingualNeural")
    communicate=edge_tts.Communicate(text,voice=voice,rate="-4%",pitch="-1Hz")
    await communicate.save(str(out))


def synth_fx(path: Path, duration: float):
    sr=44100
    n=max(1,int(duration*sr))
    t=np.arange(n,dtype=np.float32)/sr
    y=np.zeros_like(t)
    # petit impact au départ
    mask=t<0.32
    y[mask]+=0.045*np.sin(2*np.pi*(300+700*t[mask])*t[mask])*np.exp(-11*t[mask])
    # pulse discret vers 45% de la scène
    t2=t-duration*0.45
    mask2=(t2>=0)&(t2<0.22)
    y[mask2]+=0.022*np.sin(2*np.pi*620*t2[mask2])*np.exp(-15*t2[mask2])
    pcm=np.int16(np.clip(y,-1,1)*32767)
    with wave.open(str(path),"wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr); wf.writeframes(pcm.tobytes())


def subtitle_png(text: str, premium: bool, out: Path):
    layer=Image.new("RGBA",(920,190),(0,0,0,0))
    d=ImageDraw.Draw(layer)
    rounded(d,(0,0,920,178),30,fill=(0,0,0,190),outline=(255,255,255,28),width=1)
    ft=font(36,True,premium)
    words=text.split()
    # 2 lignes maximum
    lines=fit_lines(d,text,ft,820,2)
    y=30
    for line in lines:
        box=d.textbbox((0,0),line,font=ft)
        d.text(((920-(box[2]-box[0]))/2,y),line,font=ft,fill=rgb(COLORS["white"])+(255,))
        y+=52
    out.parent.mkdir(parents=True,exist_ok=True)
    layer.save(out)


def chunks(text: str, size=6):
    words=text.split()
    return [" ".join(words[i:i+size]) for i in range(0,len(words),size)]


def build_video(picks: List[Pick], stage: int, out: Path):
    from moviepy.editor import (
        AudioFileClip, CompositeAudioClip, CompositeVideoClip,
        ImageClip, concatenate_videoclips
    )

    WORK.mkdir(parents=True,exist_ok=True)
    SCENES.mkdir(parents=True,exist_ok=True)
    AUDIO.mkdir(parents=True,exist_ok=True)

    clips=[]

    if stage>=5:
        intro_path=SCENES/"intro.jpg"
        render_intro(stage,intro_path)
        intro=ImageClip(str(intro_path)).set_duration(1.35)
        clips.append(intro)

    for idx,p in enumerate(picks,1):
        img_path=SCENES/f"pick_{idx:02d}.jpg"
        render_pick(p,idx,stage,img_path)
        text=narration(p,idx)

        duration=4.6
        voice=None
        if stage>=4:
            audio_path=AUDIO/f"voice_{idx:02d}.mp3"
            asyncio.run(edge_tts_to(text,audio_path))
            voice=AudioFileClip(str(audio_path))
            duration=max(5.3,float(voice.duration)+0.35)

        base=ImageClip(str(img_path)).set_duration(duration)
        if stage>=3:
            # zoom cinématique très léger, sans sortir des safe zones
            zoom=base.resize(lambda t: 1.0 + 0.012*(t/max(duration,0.1))).set_position("center")
            base=CompositeVideoClip([zoom],size=(W,H)).set_duration(duration)

        if stage>=4:
            overlays=[base]
            seq=chunks(text,6)
            slot=max(0.55,duration/max(1,len(seq)))
            for j,part in enumerate(seq):
                sub=SCENES/f"sub_{idx:02d}_{j:02d}.png"
                subtitle_png(part,True,sub)
                start=min(duration-0.2,j*slot)
                subclip=(ImageClip(str(sub),transparent=True)
                         .set_start(start)
                         .set_duration(min(slot+0.08,max(0.2,duration-start)))
                         .set_position(("center",1480)))
                overlays.append(subclip)
            comp=CompositeVideoClip(overlays,size=(W,H)).set_duration(duration)
            fx_path=AUDIO/f"fx_{idx:02d}.wav"
            synth_fx(fx_path,duration)
            fx=AudioFileClip(str(fx_path)).volumex(0.75)
            comp=comp.set_audio(CompositeAudioClip([voice.volumex(1.0),fx]))
            base=comp

        clips.append(base)

    if stage>=5:
        outro_path=SCENES/"outro.jpg"
        render_outro(stage,outro_path)
        outro=ImageClip(str(outro_path)).set_duration(1.75)
        clips.append(outro)

    if stage>=3 and len(clips)>1:
        final=concatenate_videoclips(clips,method="compose",padding=-0.12)
    else:
        final=concatenate_videoclips(clips,method="compose")

    out.parent.mkdir(parents=True,exist_ok=True)
    final.write_videofile(
        str(out),fps=FPS,codec="libx264",audio_codec="aac",
        preset="medium",threads=4,bitrate="5500k",
        ffmpeg_params=["-pix_fmt","yuv420p","-movflags","+faststart"],
        verbose=False,logger="bar"
    )
    try: final.close()
    except Exception: pass


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data",default="data.json")
    ap.add_argument("--out",default="daily_pronos_shorts_v2_test.mp4")
    ap.add_argument("--stage",type=int,default=1)
    ap.add_argument("--limit",type=int,default=3)
    args=ap.parse_args()
    stage=int(clamp(args.stage,1,5))
    data=load_json(Path(args.data),{})
    picks,fallback=select_picks(data,limit=max(1,min(4,args.limit)))
    if not picks:
        raise SystemExit("Aucun match futur exploitable dans data.json pour le test vidéo.")
    print(f"SHORTS_TEST_STAGE={stage}")
    print(f"BSD_SOURCE={data.get('source')} MODEL_VERSION={data.get('model_version')}")
    print(f"TECHNICAL_FALLBACK={fallback}")
    for i,p in enumerate(picks,1):
        print(json.dumps({
            "n":i,"match":f"{p.home} vs {p.away}","market":p.selection_key,
            "label":p.label,"confidence":p.confidence,"odds":p.odds,
            "recommendation_eligible":p.recommendation_eligible
        },ensure_ascii=False))
    build_video(picks,stage,Path(args.out).resolve())
    meta={
        "stage":stage,
        "fallback":fallback,
        "picks":[p.__dict__ for p in picks],
        "generated_at":datetime.now(timezone.utc).isoformat(),
    }
    (WORK/"test_manifest.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
