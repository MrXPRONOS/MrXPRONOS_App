#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build validation Shorts from the CURRENT Telegram coupon-validation system.

The validated-win coupon itself is not redesigned:
  bsd_v2_verify_telegram.verdict() -> official result semantics
  bsd_v2_card.render(..., win=True) -> exact validated coupon
  bsd_v2_telegram_banner.attach_banner() -> exact Telegram bookmaker banner

The active Telegram validator is intentionally silent for losses. Therefore
the one-loss video contains only the validated winning coupons; the surrounding
video layer states the aggregate result (for example 4/5 validated, 1 lost).
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"bsd"))

from bsd.bsd_v2_card import render as render_card
from bsd.bsd_v2_telegram import partner_pack
from bsd.bsd_v2_telegram_banner import attach_banner
from bsd.bsd_v2_verify_telegram import verdict

UTC=timezone.utc
W,H=1080,1920
TARGET_WIDTH=940
COUPON_Y=105


def _font(size,bold=False):
    candidates=(
      ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
       "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"]
      if bold else
      ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
       "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
    )
    for item in candidates:
        if Path(item).is_file():
            return ImageFont.truetype(item,size)
    return ImageFont.load_default()


def _odds(match):
    try:
        value=float((match.get("prediction") or {}).get("odds"))
        return value if math.isfinite(value) else 0.0
    except (TypeError,ValueError):
        return 0.0


def _key(match):
    pick=match.get("prediction") or {}
    return (
        str(match.get("id") or ""),
        str(match.get("date") or ""),
        str(pick.get("selection_key") or ""),
    )


def _finished_candidates(snapshot,now):
    output=[]
    for match in snapshot.get("matches") or []:
        if not isinstance(match,dict) or match.get("source")!="bsd":
            continue
        if str(match.get("status") or "").lower()!="finished":
            continue
        if match.get("is_finished") is not True:
            continue
        if type(match.get("home_score")) is not int or type(match.get("away_score")) is not int:
            continue
        pick=match.get("prediction") or {}
        if not isinstance(pick,dict) or not pick.get("selection_key"):
            continue
        event={
            "status":"finished",
            "event_date":match.get("event_date"),
            "home_score":match.get("home_score"),
            "away_score":match.get("away_score"),
        }
        try:
            result=verdict(match,event,now)
        except Exception:
            result=None
        if result is None:
            continue
        won,home,away=result
        output.append((
            bool(won),
            {**match,"home_score":home,"away_score":away,
             "status":"finished","is_finished":True},
        ))
    return output


def _snapshots(feed_path:Path,max_commits=90):
    seen=set()
    try:
        current=json.loads(feed_path.read_text(encoding="utf-8"))
        yield current
    except Exception:
        pass

    try:
        proc=subprocess.run(
            ["git","log",f"--max-count={max_commits}","--format=%H","--","data.json"],
            cwd=ROOT,capture_output=True,text=True,check=True,timeout=30,
        )
    except Exception:
        return
    for sha in proc.stdout.splitlines():
        sha=sha.strip()
        if len(sha)!=40 or sha in seen:
            continue
        seen.add(sha)
        try:
            raw=subprocess.run(
                ["git","show",f"{sha}:data.json"],
                cwd=ROOT,capture_output=True,text=True,check=True,timeout=20,
            ).stdout
            yield json.loads(raw)
        except Exception:
            continue


def collect_real_results(feed_path:Path,now,need_wins=5,need_losses=1):
    wins={}
    losses={}
    for snapshot in _snapshots(feed_path):
        for won,match in _finished_candidates(snapshot,now):
            target=wins if won else losses
            target.setdefault(_key(match),match)
        if len(wins)>=need_wins and len(losses)>=need_losses:
            break
    win_rows=sorted(wins.values(),key=lambda m:(-_odds(m),str(m.get("event_date") or "")))
    loss_rows=sorted(losses.values(),key=lambda m:(-_odds(m),str(m.get("event_date") or "")))
    return win_rows,loss_rows


def render_exact_validated_cards(matches,out_dir:Path,now):
    out_dir.mkdir(parents=True,exist_ok=True)
    pack=partner_pack(now)
    paths=[]
    session=requests.Session()
    for idx,match in enumerate(matches,1):
        path=out_dir/f"validated_{idx:02d}.png"
        # Exact active Telegram validation card.
        render_card(match,path,win=True,now=now,session=session)
        attach_banner(path,pack=pack)
        paths.append(path)
        print("EXACT_TELEGRAM_VALIDATION_COUPON",idx,path)
    return paths,pack


def _smooth(v):
    v=max(0.0,min(1.0,v))
    return v*v*(3.0-2.0*v)


def _x(t,duration,width,enter=.34,leave=.34):
    center=int((W-width)/2)
    if t<enter:
        p=_smooth(t/enter)
        return int(W+(center-W)*p)
    if t>duration-leave:
        p=_smooth((t-(duration-leave))/leave)
        return int(center+(-width-center)*p)
    return center


def overlay_png(index,total,summary,out):
    canvas=Image.new("RGBA",(W,H),(0,0,0,0))
    draw=ImageDraw.Draw(canvas)

    # Results summary and CTA are both above common social bottom overlays.
    draw.rounded_rectangle((92,1360,988,1435),radius=28,fill=(13,44,67,232),
                           outline=(255,255,255,28),width=2)
    sf=_font(30,True)
    sw=draw.textbbox((0,0),summary,font=sf)[2]
    draw.text(((W-sw)/2,1380),summary,font=sf,fill=(255,255,255,255))

    draw.rounded_rectangle((92,1460,988,1588),radius=34,fill=(5,18,31,232),
                           outline=(255,255,255,34),width=2)
    title="REJOINS-NOUS SUR TELEGRAM"
    sub="Plus de pronostics sur @mr_xpronos"
    tf=_font(32,True); subf=_font(24,False)
    tw=draw.textbbox((0,0),title,font=tf)[2]
    suw=draw.textbbox((0,0),sub,font=subf)[2]
    draw.text(((W-tw)/2,1488),title,font=tf,fill=(255,255,255,255))
    draw.text(((W-suw)/2,1538),sub,font=subf,fill=(188,210,225,255))

    y=1660
    gap=24; radius=8
    total_width=total*radius*2+(total-1)*gap
    x=(W-total_width)/2
    for i in range(total):
        fill=(255,255,255,255) if i==index else (255,255,255,85)
        draw.ellipse((x,y,x+radius*2,y+radius*2),fill=fill)
        x+=radius*2+gap
    canvas.save(out)


def build_video(cards,output,work_dir,summary):
    if not hasattr(Image,"ANTIALIAS"):
        Image.ANTIALIAS=Image.Resampling.LANCZOS

    from moviepy.editor import ColorClip,CompositeVideoClip,ImageClip,concatenate_videoclips

    if not cards:
        raise RuntimeError("Aucun coupon gagnant validé à monter")
    total=len(cards)
    per_card=3.0 if total<=2 else 2.6
    scenes=[]
    for idx,path in enumerate(cards):
        with Image.open(path) as opened:
            sw,sh=opened.size
        scale=TARGET_WIDTH/sw
        cw=int(round(sw*scale)); ch=int(round(sh*scale))
        if COUPON_Y+ch>=1335:
            raise RuntimeError("Carte de validation trop haute pour la zone sûre")
        overlay=work_dir/f"overlay_{idx+1:02d}.png"
        overlay_png(idx,total,summary,overlay)
        bg=ColorClip((W,H),color=(7,15,24)).set_duration(per_card)
        card=(ImageClip(str(path)).resize(width=cw).set_duration(per_card)
              .set_position(lambda t,d=per_card,w=cw:(_x(t,d,w),COUPON_Y)))
        ov=ImageClip(str(overlay),transparent=True).set_duration(per_card)
        scenes.append(CompositeVideoClip([bg,card,ov],size=(W,H)).set_duration(per_card))
    final=concatenate_videoclips(scenes,method="compose")
    output.parent.mkdir(parents=True,exist_ok=True)
    final.write_videofile(
        str(output),fps=30,codec="libx264",audio=False,preset="medium",
        bitrate="5000k",threads=4,
        ffmpeg_params=["-pix_fmt","yuv420p","-movflags","+faststart"],
        verbose=False,logger="bar",
    )
    try: final.close()
    except Exception: pass


def make_scenario(name,wins,losses,work_root,now):
    if name=="all-win":
        selected_wins=wins[:5]
        if not selected_wins:
            raise RuntimeError("Aucune victoire réelle disponible pour le test")
        total=len(selected_wins)
        lost=0
        summary=f"{total}/{total} VALIDÉS · AUCUN PERDU"
        scenario_matches=selected_wins
    elif name=="one-loss":
        if not losses:
            raise RuntimeError("Aucune défaite réelle disponible pour le test")
        selected_wins=wins[:4]
        if not selected_wins:
            raise RuntimeError("Aucune victoire réelle disponible pour le scénario 1 perdu")
        total=len(selected_wins)+1
        lost=1
        summary=f"{len(selected_wins)}/{total} VALIDÉS · 1 PERDU"
        scenario_matches=selected_wins
    else:
        raise ValueError(name)

    scenario_dir=work_root/name
    cards,pack=render_exact_validated_cards(scenario_matches,scenario_dir/"cards",now)
    output=work_root/f"validation_{name}.mp4"
    build_video(cards,output,scenario_dir,summary)
    return {
        "scenario":name,
        "output":str(output),
        "summary":summary,
        "total_original_selections":total,
        "validated_cards":len(cards),
        "losses":lost,
        "bookmaker_pack":pack,
        "wins":[{
            "id":m.get("id"),"date":m.get("date"),
            "home_team":m.get("home_team"),"away_team":m.get("away_team"),
            "score":f"{m.get('home_score')}-{m.get('away_score')}",
            "selection_key":(m.get("prediction") or {}).get("selection_key"),
            "odds":(m.get("prediction") or {}).get("odds"),
        } for m in scenario_matches],
        "loss_example": ({
            "id":losses[0].get("id"),"date":losses[0].get("date"),
            "home_team":losses[0].get("home_team"),"away_team":losses[0].get("away_team"),
            "score":f"{losses[0].get('home_score')}-{losses[0].get('away_score')}",
            "selection_key":(losses[0].get("prediction") or {}).get("selection_key"),
            "odds":(losses[0].get("prediction") or {}).get("odds"),
        } if name=="one-loss" else None),
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--feed",default="data.json")
    p.add_argument("--work-dir",default="telegram_out/validation_shorts")
    args=p.parse_args()

    now=datetime.now(UTC)
    work=Path(args.work_dir)
    work.mkdir(parents=True,exist_ok=True)
    wins,losses=collect_real_results(Path(args.feed),now)
    print("REAL_VALIDATION_POOL",json.dumps({"wins":len(wins),"losses":len(losses)}))

    reports=[
        make_scenario("all-win",wins,losses,work,now),
        make_scenario("one-loss",wins,losses,work,now),
    ]
    (work/"manifest.json").write_text(
        json.dumps({"generated_at":now.isoformat(),"scenarios":reports},
                   ensure_ascii=False,indent=2),
        encoding="utf-8",
    )
    print("VALIDATION_SHORTS_READY",json.dumps(reports,ensure_ascii=False))


if __name__=="__main__":
    main()
