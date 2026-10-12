#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Studio editorial local Mr XPRONOS : 0 API, 0 credit, 3 formats WebP.
Ne modifie ni les templates premium Telegram ni les anciens visuels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "images" / "editorial"
FORMATS = {"og": (1200, 630), "social": (1080, 1080), "story": (1080, 1920)}
FONT_BOLD = [
    "/usr/share/fonts/truetype/lato/Lato-Heavy.ttf",
    "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONT_REG = [
    "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
LOGO_CANDIDATES = [
    ROOT / "assets/images/mrxpronos-horizontal.webp",
    ROOT / "assets/images/mrxpronos-mark.png",
]
GOLD = (241, 197, 90)
WHITE = (247, 249, 252)
MUTED = (187, 202, 214)
NAVY = (6, 19, 34)
TYPE_CONFIG = {
    "article": ("ANALYSE & BLOG", (32, 121, 169)),
    "conseil": ("CONSEIL DU JOUR", (49, 145, 119)),
    "news": ("FLASH FOOT", (179, 67, 79)),
    "match": ("AVANT-MATCH", (58, 115, 183)),
}


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9-]", "", re.sub(r"[\s_]+", "-", value.lower()))[:100].strip("-") or "contenu"


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    for name in (FONT_BOLD if bold else FONT_REG):
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def color_mix(a, b, t):
    return tuple(round(a[i] * (1 - t) + b[i] * t) for i in range(3))


def wrap_text(draw: ImageDraw.ImageDraw, text: str, ft, width: int, max_lines: int) -> list[str]:
    words = re.sub(r"\s+", " ", re.sub(r"^#+\s*", "", text)).strip().split()
    if not words:
        return ["Mr XPRONOS"]
    lines, line = [], ""
    for word in words:
        proposal = f"{line} {word}".strip()
        if draw.textbbox((0, 0), proposal, font=ft)[2] <= width or not line:
            line = proposal
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and draw.textbbox((0, 0), last + "…", font=ft)[2] > width:
            last = last[:-1].rstrip()
        lines[-1] = last.rstrip(" ,.;") + "…"
    return lines


def background(size: tuple[int, int], accent: tuple[int, int, int], variant: int) -> Image.Image:
    w, h = size
    base = Image.new("RGB", size, NAVY)
    d = ImageDraw.Draw(base)
    for y in range(h):
        t = y / max(h - 1, 1)
        tone = color_mix((10, 33, 53), (2, 11, 21), t)
        d.line((0, y, w, y), fill=tone)
    # Motifs football abstraits : pas d'image factice, pas d'image sous licence.
    step = round(w / 9)
    for x in range(-step, w + step, step):
        d.line((x, 0, x + round(h * .40), h), fill=(22, 49, 65), width=max(1, w // 350))
    cx, cy = (round(.77 * w), round(.46 * h))
    r = round(min(w, h) * (.46 if h < w else .30))
    for offset in range(4):
        rr = r + offset * round(w / 13)
        d.ellipse((cx-rr, cy-rr, cx+rr, cy+rr), outline=color_mix(NAVY, accent, .26 - offset * .045), width=max(3, w//250))
    if variant == 1:
        d.arc((round(w*.43),round(h*.12),round(w*1.09),round(h*.92)), 210, 350, fill=GOLD, width=max(4,w//180))
    elif variant == 2:
        for y in range(0, h, max(16,h//25)):
            d.line((round(w*.67), y, w, y), fill=(22, 49, 61), width=2)
    # Understated editorial diagonal separator
    d.polygon([(0, h), (round(w*.37), h), (round(w*.95), 0), (round(w*.84), 0)], fill=color_mix(NAVY,accent,.16))
    return base


def logo(canvas: Image.Image, x: int, y: int, max_w: int, max_h: int) -> bool:
    for path in LOGO_CANDIDATES:
        if not path.is_file():
            continue
        try:
            with Image.open(path) as raw:
                im = ImageOps.exif_transpose(raw).convert("RGBA")
                im.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
                canvas.paste(im, (x, y), im)
                return True
        except (OSError, ValueError):
            continue
    return False


def draw_cover(
    title: str, subtype: str, size: tuple[int, int], variant: int,
    subtitle: str = "", match_teams: tuple[str, str] | None = None,
) -> Image.Image:
    w, h = size
    kind = subtype if subtype in TYPE_CONFIG else "article"
    tag, accent = TYPE_CONFIG[kind]
    im = background(size, accent, variant)
    d = ImageDraw.Draw(im)
    pad = round(w * .065)
    large = h > w * 1.30
    square = .90 <= h/w <= 1.10
    area_top = round(h * (.28 if large else .23 if square else .25))
    max_lines = 6 if large else 4 if square else 3
    title_size = round(w * (.069 if large else .065 if square else .061))
    if len(title) > 65:
        title_size = round(title_size * .82)
    elif len(title) < 35:
        title_size = round(title_size * 1.10)
    title_size = max(35, title_size)
    main_font = font(title_size, bold=True)
    lines = wrap_text(d, title, main_font, round(w*.86), max_lines)
    line_height = round(title_size * 1.28)
    # Make long titles fit without clipping footer
    max_body = h * (.47 if large else .51 if square else .41)
    while len(lines) * line_height > max_body and title_size > 30:
        title_size -= 3
        main_font = font(title_size, bold=True)
        line_height = round(title_size * 1.26)
        lines = wrap_text(d, title, main_font, round(w*.86), max_lines)
    # Top gold label and logo
    d.rounded_rectangle((pad, round(h*.072), pad+round(w*.29), round(h*.072)+round(w*.044)), radius=9, fill=accent)
    d.text((pad+round(w*.018), round(h*.072)+round(w*.011)), tag, font=font(round(w*.019),True), fill=WHITE)
    placed = logo(im, w-pad-round(w*.19), round(h*.061), round(w*.18), round(w*.085))
    if not placed:
        d.text((w-pad-round(w*.18), round(h*.083)), "MR XPRONOS", font=font(round(w*.023),True), fill=GOLD)
    d.rectangle((pad, area_top-round(w*.018), pad+round(w*.10), area_top-round(w*.013)), fill=GOLD)
    for idx, line in enumerate(lines):
        py = area_top + idx * line_height
        d.text((pad+2, py+4), line, font=main_font, fill=(2,8,13), stroke_width=1)
        d.text((pad,py), line, font=main_font, fill=WHITE)
    after = area_top + len(lines)*line_height
    if match_teams:
        text = "  VS  ".join(t for t in match_teams if t)
        if text:
            ft = font(round(w*.028),True)
            x = pad
            d.rounded_rectangle((x, after+round(h*.03), min(w-pad,x+round(w*.82)), after+round(h*.03)+round(w*.07)),radius=10,fill=(15,42,59))
            d.text((x+round(w*.018), after+round(h*.03)+round(w*.016)),text[:65],font=ft,fill=GOLD)
    elif subtitle:
        ft = font(round(w*.024))
        for idx, line in enumerate(wrap_text(d, subtitle,ft,round(w*.83), 2)):
            d.text((pad,after+round(h*.025)+idx*round(w*.034)),line,font=ft,fill=MUTED)
    # Footer separated by quiet rule
    fy = h-round(h*(.105 if not large else .078))
    d.line((pad,fy,w-pad,fy),fill=(69,87,99),width=max(2,w//500))
    d.text((pad,fy+round(h*.020)),"MR XPRONOS  •  FOOTBALL & ANALYSES",font=font(round(w*.019),True),fill=GOLD)
    disclaimer = "18+  •  Jeu responsable"
    b=d.textbbox((0,0),disclaimer,font=font(round(w*.016)))
    d.text((w-pad-(b[2]-b[0]),fy+round(h*.022)),disclaimer,font=font(round(w*.016)),fill=MUTED)
    return im


def save_cover(title: str, subtype: str, slug: str, subtitle: str = "", match_teams=None, dry_run=False) -> dict:
    safe_slug = slugify(slug)[:65]
    variant = int(hashlib.sha1(slug.encode()).hexdigest()[:3], 16) % 3
    stamp = hashlib.sha1((title+subtype+slug).encode()).hexdigest()[:8]
    result = {"visual_variant": f"v{variant+1}", "visual_hash": stamp, "visual_format": "webp"}
    if not dry_run:
        OUT.mkdir(parents=True, exist_ok=True)
    for key, size in FORMATS.items():
        path = OUT / f"{subtype}-{safe_slug}-{stamp}-{key}.webp"
        if not dry_run and not path.exists():
            cover = draw_cover(title, subtype, size, variant, subtitle, match_teams)
            cover.save(path, "WEBP", quality=86, method=5)
        result[{"og":"image_url","social":"social_image","story":"story_image"}[key]] = path.relative_to(ROOT).as_posix()
    result["og_image"] = result["image_url"]
    return result


def generate(limit: int, dry_run: bool, news_limit: int | None = None) -> dict:
    counts = {"article":0,"conseil":0,"news":0,"errors":0}
    for file_name, kind in (("articles.json", "article"),("conseils.json","conseil"),("footnews.json","news")):
        path=ROOT/file_name
        if not path.is_file():
            continue
        try:
            records=json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(records,list):
                raise ValueError("Le JSON doit être une liste")
        except (OSError,ValueError) as err:
            print("INVALID_JSON",file_name,err)
            counts["errors"]+=1
            continue
        subset=records[:(news_limit if kind=="news" and news_limit is not None else limit)]
        changed=False
        for i, item in enumerate(subset):
            if not isinstance(item,dict) or item.get("active") is False: continue
            title=str(item.get("title") or "").strip()
            if not title: continue
            slug=str(item.get("slug") or item.get("link") or hashlib.sha1(title.encode()).hexdigest()[:12])
            subtype="match" if kind=="article" and item.get("type")=="match" else kind
            subtitle=str(item.get("category") or item.get("source") or item.get("league") or "")
            try:
                result=save_cover(title,subtype,slug,subtitle,dry_run=dry_run)
                if not dry_run:
                    item.update(result)
                counts[kind]+=1
                changed=True
            except (OSError,ValueError) as e:
                counts["errors"]+=1
                print("RENDER_ERROR",kind,slug,type(e).__name__,str(e)[:140])
        if changed and not dry_run:
            tmp=path.with_suffix(".tmp")
            tmp.write_text(json.dumps(records,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            tmp.replace(path)
    print("EDITORIAL_STUDIO",json.dumps(counts,ensure_ascii=False))
    return counts


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--limit",type=int,default=8)
    parser.add_argument("--news-limit",type=int,default=12)
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args()
    result=generate(max(args.limit,0),args.dry_run,max(args.news_limit,0))
    raise SystemExit(1 if result["errors"] else 0)

if __name__=="__main__":
    main()
