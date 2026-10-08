"""Rendu PNG dynamique BSD V2, inspiré de la maquette utilisateur.

Il s'agit d'un PRONOSTIC SIMULÉ, pas d'un reçu 1xBet/MelBet,
ni d'une preuve qu'une mise a été engagée ou gagnée.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from bsd_h2h import _utc

ROOT=Path(__file__).resolve().parent.parent
BALL=ROOT/"assets/images/bsd-football-generated.png"
NAVY="#18384a"; SLATE="#8195a3"; BLUE="#409bd5"; GREEN="#209951"

def font(size,bold=False):
    candidates=(["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"] if bold else
                ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"])
    for p in candidates:
        if Path(p).exists():return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def clipped(draw,text,x,y,max_width,size=31,bold=False,fill=NAVY):
    text=str(text or "")
    f=font(size,bold)
    while draw.textbbox((0,0),text,font=f)[2]>max_width and len(text)>3:
        text=text[:-2].rstrip()
        if not text.endswith("…"):text+="…"
    draw.text((x,y),text,font=f,fill=fill)

def right(draw,text,right_x,y,size=28,bold=False,fill=NAVY):
    f=font(size,bold); w=draw.textbbox((0,0),str(text),font=f)[2]
    draw.text((right_x-w,y),str(text),font=f,fill=fill)

def icon(canvas,x,y,d=56):
    if BALL.is_file():
        img=Image.open(BALL).convert("RGBA");img.thumbnail((d,d),Image.Resampling.LANCZOS)
        canvas.paste(img,(x,y),img)

def render(match,output,*,win=False,stake=500000,now=None):
    now=now or datetime.now(timezone.utc)
    kick=_utc(match["event_date"])
    pred=match.get("prediction") or {}
    odds=pred.get("odds")
    source=pred.get("odds_source")
    if odds is not None:
        try:
            odds=float(odds)
            if odds<=1.0:odds=None
        except (ValueError,TypeError):odds=None
    if odds is not None and not source:
        # Legacy/fictitious prices are never represented as actual BSD quotes.
        odds=None
    label=f"{odds:.2f}" if odds is not None else "Non disponible"
    gross=f"{int(round(stake*odds)):,}".replace(","," ")+" F" if odds else "—"
    canvas=Image.new("RGB",(1080,1260),"#edf3f6")
    d=ImageDraw.Draw(canvas)
    d.rectangle((0,0,1080,124),fill="#050505")
    clipped(d,"1X",32,27,100,43,True,"#ffffff")
    clipped(d,"BET",115,27,160,43,True,"#238fe1")
    clipped(d,"OU",312,38,65,25,True,"#c7c7c7")
    clipped(d,"MEL",400,27,145,43,True,"#ffffff")
    clipped(d,"BET",530,27,130,43,True,"#ffd735")
    d.rounded_rectangle((706,25,1056,93),radius=9,fill="#ffda36")
    clipped(d,"CODE PROMO XPVIP",725,40,310,28,True,"#050505")
    d.rounded_rectangle((18,145,1062,1242),radius=15,fill="white",outline="#d2dce3",width=2)
    icon(canvas,64,190,65)
    clipped(d,now.strftime("%d.%m.%Y (%H:%M)"),152,187,305,28,True,SLATE)
    badge="● GAIN" if win else "● À VENIR"
    d.rounded_rectangle((485,190,625,235),radius=7,fill="#1ca052" if win else "#e94343")
    clipped(d,badge,502,197,115,23,True,"#ffffff")
    clipped(d,"Simple",152,243,280,43,True,NAVY)
    ref=str(match.get("id") or "")
    clipped(d,"ID "+ref,340,259,620,23,False,NAVY)
    d.line((28,350,1050,350),fill="#d9e2e8",width=2)
    rows=[("Cote BSD :",label),("Mise simulée :",f"{stake:,}".replace(","," ")+" F"),
          ("Gain potentiel simulé :",gross),("Statut :","GAGNÉ (pronostic)" if win else "PRONOSTIC, NON PARIÉ")]
    for idx,(key,val) in enumerate(rows):
        y=388+idx*61
        clipped(d,key,65,y,490,29,True,SLATE)
        right(d,val,1000,y,26 if idx!=2 else 24,True,GREEN if win and idx==3 else NAVY)
    d.rectangle((20,649,1060,679),fill="#edf3f6")
    icon(canvas,56,711,48)
    clipped(d,"Football · "+str(match.get("league") or "Compétition"),120,706,820,27,True,SLATE)
    clipped(d,kick.strftime("%d.%m.%Y (%H:%M UTC)"),120,752,740,24,True,SLATE)
    if win:
        score=f"{match.get('home_score')} : {match.get('away_score')}"
        clipped(d,str(match.get("home_team")),54,849,350,29,True,NAVY)
        clipped(d,score,441,842,205,44,True,NAVY)
        clipped(d,str(match.get("away_team")),670,849,348,29,True,NAVY)
    else:
        clipped(d,str(match.get("home_team")),54,849,360,30,True,NAVY)
        clipped(d,"VS",477,842,145,45,True,NAVY)
        clipped(d,str(match.get("away_team")),690,849,330,30,True,NAVY)
    d.line((62,964,1015,964),fill="#e0e5ea",width=2)
    clipped(d,str(pred.get("type") or pred.get("label") or "Pronostic"),58,1000,720,31,True,NAVY)
    right(d,label,1005,1000,29,True,NAVY)
    if win:
        clipped(d,"RÉSULTAT",57,1100,440,28,True,SLATE)
        right(d,"GAGNÉ ✓",1003,1100,33,True,GREEN)
    else:
        mins=max(0,int((kick-now).total_seconds()/60))
        clipped(d,"PRONOSTIC AVANT-MATCH",57,1100,560,26,True,SLATE)
        right(d,f"Début dans {mins//60:02d}:{mins%60:02d}",1005,1100,24,True,NAVY)
    clipped(d,"Simulation illustrative · aucun pari placé · 18+",62,1190,940,19,False,SLATE)
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(path,"PNG",optimize=True)
    return path
