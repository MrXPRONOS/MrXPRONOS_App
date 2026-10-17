"""Mr XPRONOS : composition 1080x1350 inspirée de la maquette approuvée.
Images préchargées dans crypto/assets/premium_market. Aucun prix ni historique inventé.
"""
from __future__ import annotations
from pathlib import Path
from datetime import timezone
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import math

W,H=1080,1350
ASSETS=Path(__file__).resolve().parent/"assets"/"premium_market"
SYMBOLS=("BTC","ETH","SOL","BNB","XRP")
NAMES={"BTC":"Bitcoin","ETH":"Ethereum","SOL":"Solana","BNB":"BNB","XRP":"XRP"}
FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans"
def font(n,b=True):
    names=[FONT+("-Bold" if b else "")+".ttf",
           "C:/Windows/Fonts/arialbd.ttf" if b else "C:/Windows/Fonts/arial.ttf"]
    for name in names:
        try:return ImageFont.truetype(name,n)
        except OSError:pass
    return ImageFont.load_default()
def text(d,x,y,value,size,color="#f8faff",anchor=None,bold=True,max_width=None):
    value=str(value)
    while max_width and size>12 and d.textbbox((0,0),value,font=font(size,bold))[2]>max_width:size-=1
    d.text((x+2,y+3),value,font=font(size,bold),fill=(0,0,0,165),anchor=anchor)
    d.text((x,y),value,font=font(size,bold),fill=color,anchor=anchor)
def price(v):
    v=float(v)
    return f"{v:,.0f}".replace(","," ") if v>=10000 else (f"{v:,.2f}".replace(","," ") if v>=1 else f"{v:.6f}".rstrip("0").rstrip("."))
def sparkline(d,series,x,y,w,h,positive):
    """Courbe affichée UNIQUEMENT si l'API fournit de vrais points historiques."""
    if not series or len(series)<3:return
    values=[float(v) for v in series if v is not None and math.isfinite(float(v))]
    if len(values)<3:return
    low,high=min(values),max(values)
    spread=high-low or 1
    pts=[(round(x+i*w/(len(values)-1)),round(y+h-4-(v-low)/spread*(h-8))) for i,v in enumerate(values)]
    d.line(pts,fill="#48edb4" if positive else "#ff647b",width=3,joint="curve")
def render_premium_prices_card(rows,source,now,out_path):
    by={str(r["symbol"]).upper():r for r in rows}
    if any(s not in by for s in SYMBOLS):raise ValueError("BTC ETH SOL BNB XRP requis")
    for s in SYMBOLS:
        if float(by[s]["price"])<=0 or not math.isfinite(float(by[s]["price"])):raise ValueError("Prix invalide "+s)
    base=Image.open(ASSETS/"background.png").convert("RGB").resize((W,H),Image.Resampling.LANCZOS).convert("RGBA")
    veil=Image.new("RGBA",(W,H));vd=ImageDraw.Draw(veil)
    vd.rectangle((0,0,W,H),fill=(0,8,25,100))
    vd.rounded_rectangle((145,95,910,385),radius=30,fill=(0,12,35,175))
    base.alpha_composite(veil)
    d=ImageDraw.Draw(base)
    text(d,540,23,"♛  Mr XPRONOS",40,"#ffcf68","mt")
    text(d,540,83,"ANALYSES  •  SIGNAUX  •  OPPORTUNITÉS",18,"#d1dfed","mt",False)
    text(d,540,129,"COURS DU",77,"#ffffff","mt")
    text(d,540,226,"MARCHÉ CRYPTO",64,"#ffc153","mt")
    d.rounded_rectangle((170,320,910,370),radius=25,fill=(1,15,39,230),outline="#2684f5",width=2)
    text(d,540,335,"PRINCIPALES CRYPTOMONNAIES EN TEMPS RÉEL",20,"#eaf4ff","mt",False)
    d.rounded_rectangle((899,26,1057,172),radius=20,fill=(1,21,56,235),outline="#2886f3",width=2)
    text(d,978,47,now.strftime("%d %b").upper(),25,"#ffffff","mt",max_width=142)
    text(d,978,92,now.strftime("%Y"),26,"#e2eaf5","mt")
    text(d,978,132,now.strftime("%H:%M UTC"),16,"#bdcfe5","mt")
    for i,s in enumerate(SYMBOLS):
        r=by[s];y=396+i*145;change=float(r["change"]);positive=change>=0
        d.rounded_rectangle((46,y,1038,y+130),radius=24,fill=(2,19,45,245),outline=(67,147,228,200),width=2)
        d.rounded_rectangle((57,y+28,111,y+99),radius=12,fill=(18,42,78,255),outline=(51,97,160,255))
        text(d,84,y+42,str(i+1),30,"#dce8f9","mt")
        coin=Image.open(ASSETS/(s.lower()+".png")).convert("RGBA")
        coin.thumbnail((110,110),Image.Resampling.LANCZOS)
        base.alpha_composite(coin,(125+(110-coin.width)//2,y+11+(110-coin.height)//2))
        d=ImageDraw.Draw(base)
        text(d,250,y+30,NAMES[s],31,max_width=173)
        text(d,250,y+76,s,25,"#a8b9d2",bold=False)
        sparkline(d,r.get("sparkline"),420,y+23,165,85,positive)
        text(d,622,y+50,"$ "+price(r["price"]),32,max_width=220)
        color="#4cf6b7" if positive else "#ff788a"
        d.rounded_rectangle((848,y+17,1020,y+111),radius=17,fill=(3,71,53,240) if positive else (84,20,39,240),outline="#20b86d" if positive else "#eb6078",width=2)
        text(d,934,y+35,("▲ " if positive else "▼ ")+f"{change:+.2f}%",24,color,"mt",max_width=162)
        text(d,934,y+80,"24h",19,"#d0e5dd","mt",False)
    d.rounded_rectangle((34,1130,1045,1250),radius=24,fill=(1,15,40,250),outline="#2076c7",width=2)
    for x in (357,702):d.line((x,1151,x,1228),fill="#3c7cb6",width=2)
    market_cap=next((r.get("market_cap_total") for r in rows if r.get("market_cap_total") is not None),None)
    volume=sum(float(r.get("volume",0) or 0) for r in rows)
    fear=next((r.get("fear_greed") for r in rows if r.get("fear_greed") is not None),None)
    text(d,70,1154,"CAPITALISATION TOTALE",18,"#b7d1ed")
    text(d,70,1194,"N/D" if market_cap is None else f"$ {float(market_cap)/1e12:.2f}T",25)
    text(d,384,1154,"VOLUME 24H (5 ACTIFS)",17,"#b7d1ed")
    text(d,384,1194,f"$ {volume/1e9:.2f}B" if volume>0 else "N/D",25)
    text(d,727,1154,"FEAR & GREED INDEX",18,"#b7d1ed")
    text(d,727,1194,str(fear) if fear is not None else "N/D",26,"#5cf0aa")
    text(d,540,1281,"♛  Mr XPRONOS  •  DES DONNÉES. DES ANALYSES. DES OPPORTUNITÉS.",18,"#ffda87","mt")
    demo="simulation" in str(source).lower() or "demo" in str(source).lower()
    if demo:
        d.rounded_rectangle((760,1261,1063,1316),radius=9,fill=(111,29,38,245))
        text(d,912,1273,"TEST • DONNÉES FICTIVES",16,"#ffffff","mt")
    path=Path(out_path);path.parent.mkdir(parents=True,exist_ok=True)
    base.convert("RGB").save(path,"PNG",optimize=True)
    return path