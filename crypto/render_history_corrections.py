"""Premium correction cards for old published Telegram images, grounded in screenshot values."""
from __future__ import annotations
import json
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from crypto.financial_sanity import validate_global_usd

ROOT = Path("crypto/generated/test")
MANIFEST = Path("crypto/history_corrections_2026_10_18.json")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
WHITE = (245,249,255)
GOLD = (245,196,130)
MUTED = (182,207,230)


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def wrap(text, max_width, draw, f):
    lines = []
    current = ""
    for word in str(text).split():
        test = (current+" "+word).strip()
        if draw.textbbox((0,0),test,font=f)[2] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def render(data, qa=False):
    if data["kind"] == "global_units":
        cap, vol = validate_global_usd(data["market_cap_usd"],data["volume_24h_usd"])
    elif data["kind"] != "editorial_classification":
        raise ValueError("Unknown historic correction")
    image = Image.new("RGB", (1080, 1350))
    px = image.load()
    for y in range(1350):
        for x in range(1080):
            intensity = max(0, 1 - ((x-1050)**2+(y+70)**2)**.5/1150)
            px[x,y] = (int(5+35*intensity), int(17+52*intensity), int(39+88*intensity))
    d = ImageDraw.Draw(image)
    d.text((60,55),"RECTIFICATIF  /  N°"+str(data["number"]).zfill(2),font=font(21,True),fill=GOLD)
    d.text((765,55),"MR XPRONOS",font=font(31,True),fill=GOLD)
    d.line((60,111,1020,111),fill=(88,121,158),width=2)
    d.text((60,151),"UNE DONNÉE",font=font(82,True),fill=WHITE)
    d.text((60,250),"À RECTIFIER.",font=font(80,True),fill=GOLD)
    d.text((62,350),data["headline"],font=font(27,True),fill=WHITE)
    d.text((62,395),"Publication initiale : "+data["date_utc"],font=font(22),fill=MUTED)
    d.rounded_rectangle((55,468,1024,1172),radius=35,fill=(14,38,67),outline=(103,142,175),width=2)
    if data["kind"] == "global_units":
        def box(top,label,value):
            d.rounded_rectangle((90,top,989,top+198),radius=23,fill=(9,24,46),outline=(79,113,152),width=2)
            d.text((121,top+19),label,font=font(21,True),fill=MUTED)
            d.text((120,top+72),value,font=font(55,True),fill=GOLD)
            d.text((122,top+149),"Montant en dollars US, non multiplié.",font=font(18),fill=MUTED)
        box(515,"CAPITALISATION GLOBALE",format(cap/1e9,",.2f").replace(","," ").replace(".",",")+" Md USD")
        box(734,"VOLUME GLOBAL SUR 24 H",format(vol/1e9,",.2f").replace(","," ").replace(".",",")+" Md USD")
        message="L'ancien visuel appliquait un facteur × 1 milliard en trop aux statistiques mondiales."
        y=978
    else:
        message=("La dépêche affichée concernait le cadre réglementaire de la SEC "
                 "sur les actions tokenisées et l'opposition d'émetteurs. "
                 "Elle ne démontrait pas une modification des frais de trading d'OKX. "
                 "Son classement dans la rubrique Exchanges était erroné.")
        y=535
    d.text((92,y),"CE QUI CHANGE",font=font(23,True),fill=GOLD)
    for i,line in enumerate(wrap(message,845,d,font(26))):
        d.text((92,y+54+42*i),line,font=font(26),fill=WHITE)
    d.text((91,1111),"Source initiale : "+data["source"]+" · Relevé historique, pas un cours actuel.",font=font(18),fill=MUTED)
    d.line((60,1234,1020,1234),fill=(76,111,151),width=2)
    d.text((62,1260),"MR XPRONOS • EXACTITUDE ET TRANSPARENCE",font=font(19,True),fill=GOLD)
    if qa:
        d.rectangle((0,1300,1080,1350),fill=(162,41,65))
        d.text((195,1310),"SIMULATION QA · NE PAS PUBLIER",font=font(22,True),fill=WHITE)
    output = ROOT/("rectification_"+str(data["number"]).zfill(2)+".png")
    image.save(output,format="PNG",optimize=True)
    print("HISTORY_CORRECTION_RENDERED",data["number"],output,output.stat().st_size)
    return output


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--qa",action="store_true")
    opts=parser.parse_args()
    ROOT.mkdir(parents=True,exist_ok=True)
    content=json.loads(MANIFEST.read_text(encoding="utf-8"))
    if sorted(v["number"] for v in content["corrections"]) != [1,3,9]:
        raise ValueError("Historic correction targets tampered")
    for record in content["corrections"]:
        render(record,qa=opts.qa)


if __name__ == "__main__":
    main()
