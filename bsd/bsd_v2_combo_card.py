"""Telegram dark-theme two-leg football forecast ticket, not bookmaker receipt."""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image,ImageDraw
from bsd_h2h import _utc
from bsd_v2_labels import market_label
from bsd_v2_card import font,write,paste_asset,team_logo,BALL,BRAND_ONE,BRAND_TWO

INK="#eeeeee";MUTED="#9da2a8";BLUE="#56a7ed";BACK="#191919"

def render_combo(combo,path,*,now=None,session=None):
    now=now or datetime.now(timezone.utc)
    legs=combo["legs"]
    if len(legs)!=2:raise ValueError("Exactement deux matchs requis")
    image=Image.new("RGB",(1080,1560),BACK);d=ImageDraw.Draw(image)
    d.rectangle((0,0,1080,125),fill="#070707")
    paste_asset(image,BRAND_ONE,27,31,212,64,required=True)
    write(d,"ou",275,50,size=28,color="#dddddd")
    paste_asset(image,BRAND_TWO,341,32,232,64,required=True)
    d.rounded_rectangle((634,27,1050,103),radius=9,fill="#ffdc34")
    write(d,"Code Promo: XPVIP",841,48,size=28,bold=True,color="#121212",align="center")
    paste_asset(image,BALL,46,180,98,98,required=True)
    write(d,now.strftime("%d.%m.%Y (%H:%M)"),177,183,size=30,color=MUTED)
    write(d,"Combiné",177,231,size=47,bold=True,color=INK)
    write(d,"N° "+combo["id"],177,293,size=24,color=INK)
    d.line((22,352,1058,352),fill="#444444",width=2)
    write(d,"Événements : 2",39,382,size=31,color=INK)
    write(d,"0 sur 2 terminés",1043,382,size=27,color=MUTED,align="right")
    rows=[("Cotes:",f'{combo["combined_odds"]:.3f}'),
          ("Mise indicative:",f'{combo["stake"]:,}'.replace(","," ")+" F"),
          ("Gains potentiels:",f'{combo["potential_gain"]:,.2f}'.replace(","," ")+" F"),
          ("Statut:","Pronostic")]
    for i,(label,value) in enumerate(rows):
        y=434+59*i
        write(d,label,38,y,size=30,color=MUTED)
        write(d,value,1045,y,size=29,color=BLUE if i==3 else INK,align="right")
    for idx,leg in enumerate(legs):
        top=711+idx*368
        d.rounded_rectangle((17,top,1063,top+350),radius=22,fill="#282828")
        paste_asset(image,BALL,44,top+25,66,66,required=True)
        write(d,"Football. "+str(leg.get("league") or "Compétition"),
              129,top+19,size=28,color=MUTED,maximum=860)
        kick=_utc(leg["event_date"])
        write(d,kick.strftime("%d.%m.%Y (%H:%M UTC)"),129,top+58,size=24,color=MUTED)
        from bsd_v2_card import wrap_name
        for j,line in enumerate(wrap_name(d,leg.get("home_team"),262,size=29)):
            write(d,line,278,top+131+37*j,size=29,bold=True,color=INK,align="right",maximum=260)
        team_logo(image,d,leg,"home",294,top+120,size=86,session=session)
        write(d,"VS",540,top+141,size=42,bold=True,color=INK,align="center")
        team_logo(image,d,leg,"away",688,top+120,size=86,session=session)
        for j,line in enumerate(wrap_name(d,leg.get("away_team"),247,size=29)):
            write(d,line,787,top+131+37*j,size=29,bold=True,color=INK,maximum=246)
        d.line((25,top+240,1055,top+240),fill="#414141",width=2)
        pick=leg.get("prediction") or {}
        market=market_label(pick.get("selection_key"),pick.get("type") or "Pronostic")
        write(d,market,40,top+256,size=27,color=INK,maximum=765)
        write(d,f'{leg["prediction"]["odds"]:.2f}',1036,top+256,size=30,color=INK,align="right")
        write(d,"Statut:",40,top+304,size=25,color=MUTED)
        write(d,"Pronostic",1035,top+304,size=25,color=BLUE,align="right")
    write(d,"Parier responsablement.",540,1519,size=24,color=MUTED,align="center")
    output=Path(path);output.parent.mkdir(parents=True,exist_ok=True)
    image.save(output,"PNG",optimize=True)
    return output
