"""Neutral, reference-style bookmaker-interface layouts for MR XPRONOS.

Renders the layout of a mobile bet detail screen: white surfaces, light blue-gray
labels, a five-row summary, fixture tile, team emblems and selection. It is a
forecast visual, NOT a bookmaker receipt. Do not claim Accepted/Paid unless
those states have been externally verified; this code does not verify them.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import math
from PIL import Image, ImageDraw
from bsd_h2h import _utc
from bsd_v2_labels import market_label
from bsd_v2_stakes import single_stake, combination_stake, gain_potentiel

WIDTH = 1080
SINGLE_HEIGHT = 1080
COMBO_HEIGHT = 1580
NAVY = "#12375A"
SECONDARY = "#6087A4"
ACCENT = "#4C98D8"
PALE = "#F2F4F7"
DIVIDER = "#E8ECF0"
WHITE = "#FFFFFF"
MISSING = "#879CAF"


def _draw():
    # Import lazily: bsd_v2_card in turn delegates to these functions.
    from bsd_v2_card import write, font, team_logo, width
    return write, font, team_logo, width


def _money(amount, *, precision=0):
    if amount is None:
        return "—"
    if precision:
        return f"{float(amount):,.2f}".replace(",", " ") + " F"
    return f"{int(amount):,}".replace(",", " ") + " F"


def public_ref(obj):
    """Public display ID does not expose bsd: prefixes or invent a bet ID."""
    val = str(obj.get("source_event_id") or obj.get("id") or "—")
    if val.startswith("bsd:"):
        val = val[4:]
    if val.startswith("combo:"):
        val = val[6:17]
    return val


def competition_name(match):
    """Resolve provided BSD names only; never substitute the word Football twice."""
    for key in ("league", "league_name", "competition_name", "tournament_name"):
        name = match.get(key)
        if isinstance(name, dict):
            name = name.get("name") or name.get("title")
        if isinstance(name, str):
            cleaned = " ".join(name.strip().split())
            if cleaned and cleaned.casefold() not in ("football", "soccer", "unknown", "none"):
                return cleaned
    lid = match.get("league_id")
    if lid not in (None, "", "0", 0):
        return f"Compétition n° {lid}"
    return None


def competition_line(match):
    comp = competition_name(match)
    return "Football · " + comp if comp else "Football"


def _soccer_icon(draw, center_x, center_y, r=26, pale=True):
    col = SECONDARY if pale else NAVY
    bg = PALE if pale else WHITE
    draw.ellipse((center_x-r, center_y-r, center_x+r, center_y+r), fill=bg)
    edge = r*.67
    draw.ellipse((center_x-edge, center_y-edge, center_x+edge, center_y+edge),
                 outline=col, width=3)
    pts = [(center_x,center_y-r*.30), (center_x+r*.30,center_y-r*.08),
           (center_x+r*.18,center_y+r*.29), (center_x-r*.18,center_y+r*.29),
           (center_x-r*.30,center_y-r*.08)]
    draw.polygon(pts, fill=col)
    for idx in range(5):
        x1,y1=pts[idx]
        x2,y2=(center_x+(x1-center_x)*1.9,center_y+(y1-center_y)*1.9)
        draw.line((x1,y1,x2,y2),fill=col,width=3)


def _header(draw):
    write, _, _, _ = _draw()
    # Navigation iconography reproduces the size and alignment of the sample,
    # but these pixels are a visual mockup, not functioning bookmaker controls.
    draw.line([(94,44),(76,65),(94,86)],fill=SECONDARY,width=5,joint="curve")
    write(draw,"Informations sur le pari",540,40,
          size=33,bold=True,color=SECONDARY,align="center",maximum=630)
    # Bell outline + notification dot
    draw.arc((861,43,896,82),190,355,fill=SECONDARY,width=4)
    draw.line((864,63,864,82,892,82,892,63),fill=SECONDARY,width=3)
    draw.ellipse((876,83,882,88),fill=SECONDARY)
    for x in (964,989,1014):
        draw.ellipse((x-5,58,x+5,68),fill=SECONDARY)


def _top_meta(canvas,draw,*,kind,reference,time_text):
    write, _, _, _ = _draw()
    _soccer_icon(draw,100,212,58)
    draw.ellipse((123,243,164,284),fill=ACCENT,outline=WHITE,width=4)
    # Blue circle denotes BSD-verified odds, not bookmaker bet acceptance.
    draw.line([(132,261),(141,269),(155,253)],fill=WHITE,width=4)
    write(draw,time_text,184,161,size=27,bold=True,color=SECONDARY)
    write(draw,kind,184,202,size=41,bold=True,color=NAVY)
    write(draw,"N° "+reference,184,251,size=26,bold=True,color=NAVY,maximum=760)
    write(draw,"Simulation · Non placé",1055,274,size=20,
          color=SECONDARY,align="right")
    draw.line((0,309,WIDTH,309),fill=DIVIDER,width=2)


def _quote(price, digits=3):
    if type(price) not in (int,float) or not math.isfinite(price) or price<=1:
        return "—"
    return f"{price:.{digits}f}"


def _summary(draw,*,price,stake,won=False):
    write, _, _, _ = _draw()
    gross=gain_potentiel(stake,price)
    rows=[
        ("Cotes:",_quote(price),NAVY),
        ("Mise:",_money(stake),NAVY),
        ("Versé:","—",NAVY),   # No payment from an unplaced forecast
        ("Gains potentiels:",_money(gross),NAVY),
        ("Statut:","Pronostic gagnant" if won else "Simulation",ACCENT),
    ]
    for i,(title,value,col) in enumerate(rows):
        y=342+i*58
        write(draw,title,36,y,size=35,bold=True,color=SECONDARY)
        write(draw,value,1041,y,size=35,bold=True,color=col,align="right",maximum=650)


def _teams(canvas,draw,match,*,cy,left_name_x=395,right_name_x=711,
           home_logo_x=400,away_logo_x=601,logo_size=84,scored=False,session=None):
    write, _, team_logo, width = _draw()
    left=str(match.get("home_team") or "Équipe domicile")
    right=str(match.get("away_team") or "Équipe extérieure")
    # The reference positions are name, crest, VS, crest, name in one row.
    def fit_name(text,limit=250,initial=34):
        size=initial
        while size>22 and width(draw,text,font(size,True))>limit:
            size-=1
        if width(draw,text,font(size,True))>limit:
            while len(text)>4 and width(draw,text+"…",font(size,True))>limit:
                text=text[:-1]
            text+="…"
        return text,size
    from bsd_v2_card import font
    left,ls=fit_name(left,310)
    right,rs=fit_name(right,326)
    write(draw,left,left_name_x,cy-25,size=ls,bold=True,color=NAVY,align="right")
    team_logo(canvas,draw,match,"home",home_logo_x,cy-43,size=logo_size,session=session)
    write(draw,(f"{match['home_score']} : {match['away_score']}" if scored and
          type(match.get("home_score")) is int and
          type(match.get("away_score")) is int else "VS"),540,cy-23,
          size=43,bold=True,color=NAVY,align="center")
    team_logo(canvas,draw,match,"away",away_logo_x,cy-43,size=logo_size,session=session)
    write(draw,right,right_name_x,cy-25,size=rs,bold=True,color=NAVY)


def _fixture_tile(canvas,draw,match,*,top,bottom,winning=False,
                  session=None,compact=False):
    write, _, _, _ = _draw()
    draw.rounded_rectangle((8,top,1072,bottom),radius=25,fill=PALE)
    draw.rounded_rectangle((21,top+12,1059,bottom-10),radius=22,fill=WHITE)
    y=top
    _soccer_icon(draw,75,y+83,32)
    write(draw,competition_line(match),126,y+50,size=30,bold=True,
          color=SECONDARY,maximum=910)
    try:
        date=_utc(match["event_date"]).strftime("%d.%m.%Y (%H:%M)")
    except (KeyError,ValueError,TypeError):
        date="Horaire à confirmer"
    write(draw,date,126,y+92,size=29,bold=True,color=SECONDARY)
    cy=y+(220 if not compact else 205)
    _teams(canvas,draw,match,cy=cy,scored=winning,session=session,
           home_logo_x=401,away_logo_x=604)
    separator=y+(278 if not compact else 265)
    draw.line((30,separator,1050,separator),fill=DIVIDER,width=3)
    pick=match.get("prediction") or {}
    market=market_label(pick.get("selection_key"),pick.get("type") or pick.get("label") or "Pronostic")
    try:price=float(pick.get("odds"))
    except (ValueError,TypeError):price=None
    write(draw,market,44,separator+21,size=34,bold=True,color=NAVY,maximum=765)
    write(draw,_quote(price),1037,separator+21,size=33,bold=True,color=NAVY,align="right")
    write(draw,"Statut:",46,separator+81,size=32,bold=True,color=SECONDARY)
    write(draw,"Gagnant" if winning else "Simulation",1036,separator+81,
          size=32,bold=True,color=ACCENT,align="right")


def render_single(match,output,*,win=False,stake=None,now=None,session=None):
    from bsd_v2_card import _odds
    now=now or datetime.now(timezone.utc)
    price=_odds(match)
    if stake is None:
        stake=single_stake(price)
    canvas=Image.new("RGB",(WIDTH,SINGLE_HEIGHT),WHITE)
    d=ImageDraw.Draw(canvas)
    _header(d)
    _top_meta(canvas,d,kind="Simple",reference=public_ref(match),
              time_text=now.astimezone(timezone.utc).strftime("%d.%m.%Y (%H:%M)"))
    _summary(d,price=price,stake=stake,won=win)
    _fixture_tile(canvas,d,match,top=658,bottom=1077,winning=win,session=session)
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(path,"PNG",optimize=True)
    return path


def render_combined(combo,output,*,now=None,session=None):
    now=now or datetime.now(timezone.utc)
    legs=combo.get("legs") or []
    if len(legs)!=2:
        raise ValueError("Exactement deux rencontres exigées")
    price=float(combo["combined_odds"])
    stake=combination_stake()
    canvas=Image.new("RGB",(WIDTH,COMBO_HEIGHT),WHITE)
    d=ImageDraw.Draw(canvas)
    _header(d)
    _top_meta(canvas,d,kind="Combiné",reference=public_ref(combo),
              time_text=now.astimezone(timezone.utc).strftime("%d.%m.%Y (%H:%M)"))
    _summary(d,price=price,stake=stake,won=False)
    for i,leg in enumerate(legs):
        top=660+i*456
        _fixture_tile(canvas,d,leg,top=top,bottom=top+443,
                      session=session,compact=True)
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(path,"PNG",optimize=True)
    return path
