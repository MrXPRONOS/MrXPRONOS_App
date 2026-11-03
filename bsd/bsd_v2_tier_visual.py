"""Premium, user-facing Mr XPRONOS Telegram visuals, no fake betting ticket.

No stake, payout, provider ID, API information, accepted-bet badge, or
internal confidence variables. Three real audience-facing categories.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from math import isfinite
from PIL import Image,ImageDraw,ImageFont
from bsd_v2_public_tiers import HEADLINES, ULTRA, SAFE, COTES15, tier_for_record

WIDTH,HEIGHT=1080,1120
NAVY="#08192B"; BLUE="#123B5E"; SKY="#75D1F0"
AMBER="#FFAF55"; WHITE="#F9FCFF"; MUTED="#B8D3E5"
FONT_BOLD=("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
           "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf")
FONT_REG=("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
          "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf")

def _font(size,bold=False):
    for path in FONT_BOLD if bold else FONT_REG:
        if Path(path).is_file():return ImageFont.truetype(path,size)
    return ImageFont.load_default()

def _width(draw,value,font):
    return draw.textbbox((0,0),str(value),font=font)[2]

def _line(draw,value,x,y,*,size=38,bold=False,color=WHITE,width=930,align="left"):
    text=" ".join(str(value or "—").split())
    font=_font(size,bold)
    while _width(draw,text,font)>width and len(text)>3:
        text=text[:-2].rstrip("…")+"…"
    x=int(x - (_width(draw,text,font)/2 if align=="center" else 0))
    draw.text((x,y),text,font=font,fill=color)
    return text

def _date(value):
    try:
        dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return dt.astimezone(timezone.utc).strftime("%d/%m/%Y · %Hh%M UTC")
    except (TypeError,ValueError,OverflowError):
        return "Horaire à confirmer"

def _price(value):
    if type(value) not in (int,float) or not isfinite(float(value)) or not 1.01<=value<=100:
        raise ValueError("Invalid display price")
    # At threshold boundaries do not display 1,50 for a strictly >1,50 price.
    digits=3 if 1.5<float(value)<1.505 or 1.30<float(value)<1.305 else 2
    return f"{value:.{digits}f}".replace(".",",")

def _base(tier,height=HEIGHT):
    canvas=Image.new("RGB",(WIDTH,height),NAVY)
    d=ImageDraw.Draw(canvas)
    for y in range(height):
        t=y/height
        d.line([(0,y),(WIDTH,y)],
               fill=(round(7+12*t),round(28+22*t),round(46+30*t)))
    d.ellipse((880,-210,1300,210),fill="#124062")
    d.rounded_rectangle((50,52,1030,height-54),radius=35,
                        fill="#0C253C",outline="#336080",width=3)
    d.rounded_rectangle((82,88,998,147),radius=16,fill="#123F5F")
    _line(d,"MR XPRONOS",112,96,size=33,bold=True,color=WHITE)
    _line(d,"FOOTBALL · AVANT-MATCH",965,106,size=21,color=SKY,
          width=420,align="right" if False else "left")
    d.line((100,291,980,291),fill="#326180",width=2)
    d.line((100,height-165,980,height-165),fill="#326180",width=2)
    return canvas,d

def _card(tier,*,home,away,league,event_date,selection,odds,probability,
          model_only=False,outcome=None):
    if tier not in HEADLINES:raise ValueError("Unknown visual tier")
    if model_only and tier==ULTRA:raise ValueError("Analysis cannot claim Ultra Safe")
    if not model_only and tier!=ULTRA:raise ValueError("Ultra Safe requires published selection")
    canvas,d=_base(tier)
    accent=AMBER if tier==COTES15 else SKY
    _line(d,HEADLINES[tier],540,187,size=57,bold=True,color=accent,
          width=860,align="center")
    _line(d,"MATCH DU JOUR",116,330,size=23,bold=True,color=SKY)
    _line(d,league or "Football",116,380,size=27,color=MUTED,width=820)
    _line(d,home,540,440,size=45,bold=True,align="center",width=810)
    _line(d,"VS",540,507,size=31,bold=True,color=accent,align="center")
    _line(d,away,540,567,size=45,bold=True,align="center",width=810)
    d.rounded_rectangle((100,653,980,847),radius=24,fill="#143B56",outline="#397090",width=2)
    _line(d,selection,540,676,size=31,bold=True,align="center",width=810)
    d.line((144,738,938,738),fill="#2A6485",width=2)
    _line(d,"COTE INDICATIVE" if model_only else "COTE ESTIMÉE" if outcome=="model"
          else "COTE",144,759,size=24,color=MUTED)
    _line(d,_price(odds),915,746,size=54,bold=True,color=accent,align="center")
    if probability is not None:
        _line(d,"PROBABILITÉ ESTIMÉE",145,861,size=24,color=MUTED)
        _line(d,f"{probability:.1f} %".replace(".",","),810,851,
              size=39,bold=True,color=WHITE,align="center")
    _line(d,_date(event_date),540,944,size=27,color=SKY,align="center")
    _line(d,"Cote théorique, non proposée par un bookmaker" if model_only
          else "Estimation du modèle, pas une cote bookmaker" if outcome=="model"
          else "Pronostic avant-match, résultat non garanti",
          540,999,size=20,color=MUTED,align="center")
    _line(d,"18+ · Jouez avec modération",540,1053,size=19,color="#8EABB9",align="center")
    return canvas

def render_ultra(match,path):
    pick=(match.get("prediction") or {})
    if tier_for_record(match)!=ULTRA:raise ValueError("Not an eligible Ultra Safe prediction")
    prob=pick.get("confidence")
    if type(prob) not in (float,int) or not 79<=float(prob)<=100:
        raise ValueError("Insufficient Ultra Safe confidence")
    image=_card(ULTRA,
        home=match.get("home_team"),away=match.get("away_team"),
        league=match.get("league"),event_date=match.get("event_date"),
        selection=pick.get("label") or pick.get("type") or pick.get("selection_key"),
        odds=pick.get("odds"),probability=prob,
        outcome="model" if pick.get("estimated_odds") else "verified")
    dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True)
    image.save(dest,"PNG",optimize=True)
    return dest

def render_analysis(row,path):
    tier=tier_for_record(row)
    if tier not in (SAFE,COTES15) or not row.get("analysis_telegram_opt_in") is True:
        raise ValueError("Invalid dedicated Telegram analysis")
    if not (row.get("analysis_only") is True and row.get("do_not_send_to_telegram") is True
            and row.get("not_an_executable_bookmaker_quote") is True
            and row.get("odds_source")=="mrxpronos_model" and
            row.get("recommendation_eligible") is False):
        raise ValueError("Analysis cannot impersonate a recommended or bookmaker ticket")
    probability=row.get("model_probability")
    if type(probability) not in (int,float) or not 0<float(probability)<1:
        raise ValueError("Missing calibrated probability")
    price=float(row["odds"])
    if abs(price-round(1/(probability*1.06),3))>.002:
        raise ValueError("Indicative quote is not backed by model probability")
    image=_card(tier,
        home=row.get("home_team"),away=row.get("away_team"),
        league=row.get("league"),event_date=row.get("event_date"),
        selection=row.get("market_label"),odds=price,
        probability=100*probability,model_only=True)
    dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True)
    image.save(dest,"PNG",optimize=True)
    return dest
