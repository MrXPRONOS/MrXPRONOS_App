"""Blank Arty Football premium templates + safe, data-only overlays.

Background frames belong exclusively to make_background(), never to overlay().
Generated/committed backgrounds are preferred; deterministic fallback is identical.
All coordinates are defined in 1080x1350 units (portrait Telegram photo).
"""
from __future__ import annotations

import math
import os
import re
import textwrap
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "images" / "arty_football"
W, H = 1080, 1350
GOLD = (241, 193, 92)
PALE = (252, 243, 219)
MUTED = (186, 193, 201)
DARK = (5, 14, 26)
SUPPORTED = (
    "composition", "kickoff", "goal", "mi_temps", "score_update",
    "statistique_avancee", "community_vote", "quiz", "debat", "reaction",
    "resultat_suivi", "suivi_interrompu",
)
HEADINGS = {
    "composition": "COMPOSITIONS OFFICIELLES",
    "kickoff": "COUP D'ENVOI",
    "goal": "BUUUUT !",
    "mi_temps": "MI-TEMPS",
    "score_update": "SCORE LIVE CONFIRMÉ",
    "statistique_avancee": "STATISTIQUE AVANCÉE",
    "community_vote": "VOTE DU MATCH",
    "quiz": "QUIZ FOOT",
    "debat": "DÉBAT FOOT",
    "reaction": "RÉACTION APRÈS MATCH",
    "resultat_suivi": "RÉSULTAT FINAL",
    "suivi_interrompu": "MATCH INTERROMPU",
}

FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)
FONT_REGULAR = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
    "C:/Windows/Fonts/arial.ttf",
)


@lru_cache(maxsize=100)
def font(size: int, bold: bool = True):
    for location in (FONT_PATHS if bold else FONT_REGULAR):
        if Path(location).is_file():
            return ImageFont.truetype(location, size)
    return ImageFont.load_default()


def clean(value: Any, cap: int = 1000) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", str(value or ""))).strip()[:cap]


def panel(draw: ImageDraw.ImageDraw, box, radius=18, width=3):
    draw.rounded_rectangle(box, radius=radius, fill=(8, 19, 32),
                           outline=(176, 126, 52), width=width)
    x1, y1, x2, _ = box
    draw.line((x1 + 24, y1 + 1, min(x2 - 24, x1 + 170), y1 + 1),
              fill=GOLD, width=2)


def dark_circle(draw: ImageDraw.ImageDraw, x: int, y: int, r: int):
    draw.ellipse((x-r-5, y-r-5, x+r+5, y+r+5),
                 fill=(5, 14, 26), outline=GOLD, width=5)
    draw.ellipse((x-r+5, y-r+5, x+r-5, y+r-5),
                 outline=(116, 94, 63), width=2)


def draw_text(draw, value, box, size=30, min_size=15, color=PALE,
              bold=True, align="center", max_lines=1):
    """Fit in a hard rectangle; return fitted text; never draw outside bounds."""
    text = clean(value)
    if not text:
        return ""
    x1,y1,x2,y2 = box
    avail_w,avail_h = x2-x1-12,y2-y1-10
    result, face, lh = [], font(min_size,bold), 0
    for px in range(size, min_size-1, -1):
        face = font(px,bold)
        words = text.split()
        lines, row = [], ""
        for word in words:
            candidate = (row + " " + word).strip()
            bbox=draw.textbbox((0,0),candidate,font=face)
            if bbox[2]-bbox[0] <= avail_w:
                row=candidate
            elif row:
                lines.append(row)
                row=word
            else:
                lines.append(word)
                row=""
        if row:
            lines.append(row)
        if len(lines)>max_lines:
            continue
        bbox=draw.textbbox((0,0),"Ag",font=face)
        lh=max(1,bbox[3]-bbox[1])+4
        if lh*len(lines) <= avail_h and all(
             draw.textbbox((0,0),l,font=face)[2] <= avail_w for l in lines):
            result=lines
            break
    if not result:
        face=font(min_size,bold)
        words=text.split()
        result=[]
        row=""
        for word in words:
            candidate=(row+" "+word).strip()
            if draw.textbbox((0,0),candidate,font=face)[2]<=avail_w:
                row=candidate
            else:
                if row: result.append(row)
                row=word
        if row: result.append(row)
        result=result[:max_lines]
        if not result:
            return ""
        last=result[-1]
        if len(result) >= max_lines and len(" ".join(result)) < len(text):
            while last and draw.textbbox((0,0),last+"…",font=face)[2]>avail_w:
                last=last[:-1]
            result[-1]=last+"…"
        lh=max(1,draw.textbbox((0,0),"Ag",font=face)[3])+4
    yy=(y1+y2-len(result)*lh)/2+lh/2
    for line in result:
        xx = (x1+x2)/2 if align=="center" else x1+7 if align=="left" else x2-7
        anchor="mm" if align=="center" else "lm" if align=="left" else "rm"
        draw.text((xx,yy),line,fill=color,font=face,anchor=anchor)
        yy+=lh
    return "\n".join(result)


def _stadium_base():
    image=Image.new("RGB",(W,H))
    d=ImageDraw.Draw(image)
    for y in range(H):
        t=y/(H-1)
        d.line((0,y,W,y),fill=(
            int(4+7*t),int(13+10*t),int(26+10*t)))
    # Spotlight haze, dark stands and perspective lines stay behind data slots.
    for index in range(10):
        delta=index*11
        d.arc((-250-delta, -30-delta, 1330+delta, 1050+delta),
              184, 356, fill=(38+min(70,index*3), 42+min(50,index*3), 46),width=2)
    for x,y in ((48,115),(1032,115),(110,1010),(970,1010)):
        for r in range(75,2,-9):
            factor=max(0,1-r/85)
            d.ellipse((x-r,y-r,x+r,y+r),
                      outline=(int(55+190*factor),int(46+151*factor),
                               int(34+78*factor)),width=2)
    for j in range(9):
        yy=820+j*38
        d.line((0,yy,W,yy),fill=(17+j*2,29+j*2,38+j*2),width=2)
    # Clean metallic outer rim and modest footer identity.
    d.rounded_rectangle((22,20,W-22,H-22),radius=35,
                        outline=(140,103,51),width=3)
    d.line((70,1293,375,1293),fill=GOLD,width=2)
    d.line((705,1293,1010,1293),fill=GOLD,width=2)
    draw_text(d,"MR XPRONOS  •  ARTY FOOTBALL",(385,1266,695,1320),
              size=17,min_size=15,color=GOLD)
    return image


def make_background(category: str) -> Image.Image:
    """Produce the blank template once. Never draw frames again in overlay()."""
    if category not in SUPPORTED:
        raise ValueError("Unknown category: "+category)
    image=_stadium_base()
    d=ImageDraw.Draw(image)
    heading=HEADINGS[category]
    panel(d,(74,84,1006,228),radius=21)
    draw_text(d,heading,(100,99,980,202),size=59,min_size=30,color=GOLD)
    if category=="composition":
        dark_circle(d,180,324,83)
        dark_circle(d,900,324,83)
        panel(d,(63,423,502,479))
        panel(d,(579,423,1018,479))
        panel(d,(345,273,735,342))
        panel(d,(55,509,512,1214),radius=26)
        panel(d,(568,509,1025,1214),radius=26)
        # Exactly eleven subtle baselines per side, no second filled rectangles.
        for i in range(11):
            yy=564+i*55
            for x1,x2 in ((83,484),(596,997)):
                d.line((x1,yy+33,x2,yy+33),fill=(87,86,82),width=1)
        draw_text(d,"VS",(510,669,572,756),size=44,color=GOLD)
    elif category in {"kickoff","goal","mi_temps","score_update","reaction",
                       "community_vote","resultat_suivi","suivi_interrompu"}:
        y=452 if category!="reaction" else 440
        dark_circle(d,196,y,97)
        dark_circle(d,884,y,97)
        panel(d,(45,y+110,438,y+180))
        panel(d,(642,y+110,1035,y+180))
        panel(d,(424,y-74,656,y+106))
        if category=="reaction":
            panel(d,(62,710,1018,1130),radius=28)
        elif category=="community_vote":
            panel(d,(95,710,985,852))
            for j in range(3):
                panel(d,(64+j*341,934,334+j*341,1097))
        elif category=="goal":
            panel(d,(90,760,990,864))
            panel(d,(220,925,860,1000))
            panel(d,(220,1060,860,1134))
        elif category=="suivi_interrompu":
            panel(d,(90,796,990,1120))
        else:
            panel(d,(218,768,862,837))
            panel(d,(122,898,958,994))
        panel(d,(284,264,796,330))
    elif category=="statistique_avancee":
        panel(d,(94,260,986,375))
        panel(d,(130,400,950,476))
        panel(d,(66,508,1014,874),radius=26)
        for y in (908,1080):
            panel(d,(65,y,515,y+144))
            panel(d,(565,y,1015,y+144))
    elif category=="quiz":
        panel(d,(65,278,1015,675),radius=28)
        for x1 in (66,567):
            for y1 in (716,920):
                panel(d,(x1,y1,x1+447,y1+170))
        panel(d,(120,1116,960,1187))
    elif category=="debat":
        panel(d,(60,281,1020,668),radius=28)
        panel(d,(60,705,1020,1080),radius=28)
        panel(d,(150,1120,930,1198))
    return image


def blank_path(category: str) -> Path:
    return ASSETS / (category+".png")


def export_blank_templates(directory: str | Path = ASSETS) -> list[Path]:
    output=Path(directory)
    output.mkdir(parents=True,exist_ok=True)
    made=[]
    for category in SUPPORTED:
        file=output/(category+".png")
        make_background(category).save(file,format="PNG",optimize=True)
        made.append(file)
    return made


def background(category: str) -> Image.Image:
    # Real, committed blank assets if present; same fallback also works on a clean checkout.
    file=blank_path(category)
    if file.is_file():
        with Image.open(file) as source:
            return ImageOps.fit(source.convert("RGB"),(W,H),method=Image.Resampling.LANCZOS)
    return make_background(category)


def logo(image: Image.Image, url: str, center: tuple[int,int], width: int = 148):
    if not clean(url): return False
    from programme_styles import load_logo
    source=load_logo(url,width)
    if source is None:return False
    source=source.convert("RGBA")
    source.thumbnail((width,width),Image.Resampling.LANCZOS)
    x,y=center
    image.paste(source,(x-source.width//2,y-source.height//2),source)
    return True


def _score(payload):
    v=payload.get("scores",payload.get("score",""))
    if isinstance(v,(tuple,list)) and len(v)==2:
        return f"{v[0]} - {v[1]}"
    return clean(v,25).replace("–","-").replace("—","-")


def overlay(category: str,payload: dict[str,Any]) -> Image.Image:
    """Write only dynamic text / logo pixels in original blank slots."""
    image=background(category)
    d=ImageDraw.Draw(image)
    home=clean(payload.get("home"),80)
    away=clean(payload.get("away"),80)
    comp=clean(payload.get("competition") or payload.get("league"),100)
    source=clean(payload.get("source"),90)
    score=_score(payload)
    if category=="composition":
        a=[clean(x,90) for x in (payload.get("home_players") or []) if clean(x)]
        b=[clean(x,90) for x in (payload.get("away_players") or []) if clean(x)]
        if len(a)!=11 or len(b)!=11:
            raise ValueError("Composition: onze titulaires vérifiés nécessaires pour chaque équipe")
        if not home or not away:
            raise ValueError("Composition: équipes manquantes")
        if not payload.get("home_logo") or not payload.get("away_logo"):
            raise ValueError("Composition: logos officiels manquants")
        draw_text(d,home,(75,425,492,477),size=29,min_size=18)
        draw_text(d,away,(590,425,1005,477),size=29,min_size=18)
        draw_text(d,comp+" • "+clean(payload.get("time"),15),(359,282,720,328),size=21,min_size=15,color=GOLD)
        logo(image,payload["home_logo"],(180,324),144)
        logo(image,payload["away_logo"],(900,324),144)
        for idx in range(11):
            cy=544+idx*55
            draw_text(d,f"{idx+1:>2}.  "+a[idx],(78,cy,488,cy+50),
                      size=24,min_size=15,align="left")
            draw_text(d,f"{idx+1:>2}.  "+b[idx],(589,cy,997,cy+50),
                      size=24,min_size=15,align="left")
        return image
    if category in {"kickoff","goal","mi_temps","score_update","reaction",
                    "community_vote","resultat_suivi","suivi_interrompu"}:
        y=452 if category!="reaction" else 440
        logo(image,clean(payload.get("home_logo")),(196,y),167)
        logo(image,clean(payload.get("away_logo")),(884,y),167)
        draw_text(d,home,(52,y+116,430,y+174),size=30,min_size=16)
        draw_text(d,away,(650,y+116,1027,y+174),size=30,min_size=16)
        draw_text(d,score if category!="community_vote" else "VS",
                  (435,y-62,645,y+92),size=72,min_size=33,color=GOLD)
        draw_text(d,comp,(302,268,783,325),size=25,min_size=16,color=GOLD)
        if category=="reaction":
            draw_text(d,clean(payload.get("question") or payload.get("reaction") or
                        payload.get("commentary")), (93,763,983,1079),
                      size=37,min_size=22,max_lines=6)
        elif category=="community_vote":
            draw_text(d,clean(payload.get("question")),(118,740,958,824),
                      size=38,min_size=24,max_lines=2)
            for i,option in enumerate((payload.get("options") or [])[:3]):
                draw_text(d,re.sub(r"^[^\\wÀ-ÿ]+", "", clean(option)),(80+341*i,970,318+341*i,1059),
                          size=24,min_size=15,max_lines=2)
        elif category=="goal":
            goal=payload.get("goal") or {}
            draw_text(d,goal.get("player") or payload.get("scorer") or
                      "BUT CONFIRMÉ",(114,782,966,846),
                      size=42,min_size=25,color=GOLD)
            draw_text(d,goal.get("minute_text") or payload.get("minute") or "",
                      (237,939,837,989),size=31,min_size=21)
            draw_text(d,source,(240,1076,842,1122),size=21,min_size=16)
        elif category=="suivi_interrompu":
            draw_text(d,payload.get("status") or "Rencontre interrompue",
                      (118,826,962,1086),size=38,min_size=23,max_lines=3)
        else:
            draw_text(d,payload.get("minute") or payload.get("time") or "",
                      (240,781,840,823),size=29,min_size=18,color=GOLD)
            draw_text(d,source or payload.get("status") or "",
                      (145,919,935,966),size=23,min_size=16)
        return image
    if category=="statistique_avancee":
        draw_text(d,payload.get("headline") or payload.get("title"),
                  (115,274,965,351),size=35,min_size=19,max_lines=2)
        draw_text(d,comp or source,(158,413,923,464),size=25,min_size=17,color=GOLD)
        headline_value = clean(payload.get("headline") or payload.get("title"))
        number = re.search(r"(?<!\\d)\\d+(?:[.,]\\d+)?%?", headline_value)
        draw_text(d,payload.get("value") or payload.get("stat_value") or
                  payload.get("stat") or (number.group(0) if number else headline_value),
                  (120,544,960,821),size=108,min_size=38,max_lines=3,color=GOLD)
        metrics=(payload.get("lines") or payload.get("metrics") or [])[:4]
        for j,v in enumerate(metrics):
            x=83+(j%2)*500
            y=929+(j//2)*172
            draw_text(d,v,(x,y,x+410,y+99),size=28,min_size=17,max_lines=2)
        return image
    if category=="quiz":
        draw_text(d,payload.get("question"),(100,324,984,613),
                  size=47,min_size=23,max_lines=5)
        for i,v in enumerate((payload.get("options") or [])[:4]):
            x=90+(i%2)*500
            y=762+(i//2)*203
            draw_text(d,str("ABCD"[i])+". "+clean(v),(x,y,x+396,y+105),
                      size=26,min_size=16,max_lines=3)
        draw_text(d,source,(153,1129,937,1177),size=20,min_size=15)
        return image
    if category=="debat":
        draw_text(d,payload.get("question") or payload.get("headline"),
                  (99,336,977,610),size=46,min_size=25,max_lines=4)
        draw_text(d,payload.get("summary") or payload.get("description"),
                  (96,752,980,1012),size=30,min_size=19,max_lines=5)
        draw_text(d,source,(175,1133,909,1182),size=21,min_size=15)
        return image
    raise ValueError("Template non supporté: "+category)
