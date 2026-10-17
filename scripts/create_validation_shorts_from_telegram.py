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
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"bsd"))

from bsd.bsd_v2_card import render as render_card
from bsd.bsd_v2_telegram import partner_pack
from bsd.bsd_v2_telegram_banner import attach_banner
from bsd.bsd_v2_verify_telegram import verdict
from shorts_video_fx import LOOP_TAIL_SECONDS, card_zoom, scene_duration, synthesize_soundtrack

UTC=timezone.utc
W,H=1080,1920
TARGET_WIDTH=940
COUPON_Y=105
VIDEO_BACKGROUND=ROOT/"assets"/"images"/"mrxpronos-video-background.jpg"
HEADER_LOGO=ROOT/"assets"/"images"/"mrxpronos-logo-maquette.png"


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


def fit_card_size(source_w,source_h,max_w=940,max_h=1210):
    """Fit proportionally inside the safe coupon area."""
    if source_w<=0 or source_h<=0:
        raise RuntimeError("Dimensions coupon invalides")
    scale=min(max_w/source_w,max_h/source_h,1.0)
    return int(round(source_w*scale)),int(round(source_h*scale))


def make_card_shadow(card_width,card_height,out):
    """External depth only; validated Telegram card pixels remain untouched."""
    pad=54
    layer=Image.new("RGBA",(card_width+pad*2,card_height+pad*2),(0,0,0,0))
    shadow=Image.new("RGBA",layer.size,(0,0,0,0))
    sd=ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (pad,pad+12,pad+card_width,pad+12+card_height),
        radius=26,fill=(0,0,0,165)
    )
    shadow=shadow.filter(ImageFilter.GaussianBlur(22))
    layer=Image.alpha_composite(layer,shadow)

    glow=Image.new("RGBA",layer.size,(0,0,0,0))
    gd=ImageDraw.Draw(glow)
    gd.rounded_rectangle(
        (pad-3,pad-3,pad+card_width+3,pad+card_height+3),
        radius=26,outline=(39,133,255,105),width=8
    )
    glow=glow.filter(ImageFilter.GaussianBlur(14))
    layer=Image.alpha_composite(layer,glow)
    layer.save(out)
    return pad


def overlay_png(index,total,summary,out,total_original=None,losses=0):
    canvas=Image.new("RGBA",(W,H),(0,0,0,0))
    draw=ImageDraw.Draw(canvas)
    total_original=int(total_original or total)

    # Result header, protected from the right-side social UI column.
    if HEADER_LOGO.is_file():
        try:
            logo=Image.open(HEADER_LOGO).convert("RGBA")
            logo.thumbnail((160,54),Image.Resampling.LANCZOS)
            canvas.alpha_composite(logo,(48,26))
        except Exception:
            pass
    header="RÉSULTATS"
    hf=_font(26,True)
    hb=draw.textbbox((0,0),header,font=hf)
    safe_right=900
    draw.text((safe_right-(hb[2]-hb[0]),38),header,font=hf,fill=(244,249,255,245))

    # Counter + progress bar.
    counter=f"{index+1:02d} / {total_original:02d}"
    cf=_font(28,True)
    draw.text((92,1303),counter,font=cf,fill=(248,251,255,255))
    progress_ratio=(index+1)/max(total_original,1)
    bar_x1,bar_y1,bar_x2,bar_y2=285,1319,900,1329
    draw.rounded_rectangle((bar_x1,bar_y1,bar_x2,bar_y2),radius=5,fill=(255,255,255,48))
    fill_x=bar_x1+int((bar_x2-bar_x1)*progress_ratio)
    draw.rounded_rectangle((bar_x1,bar_y1,fill_x,bar_y2),radius=5,fill=(68,205,157,245))

    # Progressive validation score: it evolves card after card.
    current=index+1
    is_last=index==total-1
    if is_last:
        score_text=summary
    else:
        suffix="VALIDÉ" if current==1 else "VALIDÉS"
        score_text=f"{current}/{total_original} {suffix}"

    draw.rounded_rectangle((92,1350,900,1428),radius=26,fill=(7,44,42,205),
                           outline=(84,220,171,80),width=2)
    sf=_font(29,True)
    sw=draw.textbbox((0,0),score_text,font=sf)[2]
    draw.text((92+(808-sw)/2,1372),score_text,font=sf,fill=(241,255,250,255))

    # Minimal Telegram CTA, no large heavy block.
    draw.line((92,1465,900,1465),fill=(255,255,255,38),width=2)
    icon_x,icon_y,icon_r=92,1496,25
    draw.ellipse((icon_x,icon_y,icon_x+icon_r*2,icon_y+icon_r*2),fill=(48,163,255,230))
    draw.polygon(
        [(icon_x+13,icon_y+24),(icon_x+39,icon_y+13),(icon_x+29,icon_y+38)],
        fill=(255,255,255,255)
    )
    draw.text((158,1487),"PLUS DE PRONOSTICS",font=_font(22,False),
              fill=(193,210,226,245))
    draw.text((158,1518),"@mr_xpronos",font=_font(31,True),
              fill=(247,251,255,255))

    canvas.save(out)


def _card_position(t,duration,width,height,y):
    zoom=card_zoom(t,duration)
    x=_x(t,duration,width)-int((width*zoom-width)/2)
    yy=y-int((height*zoom-height)/2)
    return x,yy


def _shadow_position(t,duration,card_width,card_height,pad,y):
    zoom=card_zoom(t,duration)
    sw=card_width+2*pad
    sh=card_height+2*pad
    x=_x(t,duration,card_width)-pad-int((sw*zoom-sw)/2)
    yy=y-pad-int((sh*zoom-sh)/2)
    return x,yy


def _animated_result_background(ImageClip,ColorClip,CompositeVideoClip,duration):
    """Premium background with slow parallax and a subtle result-green wash."""
    bg_w=1120
    bg_h=int(round(H*bg_w/W))
    moving=(ImageClip(str(VIDEO_BACKGROUND)).resize(newsize=(bg_w,bg_h)).set_duration(duration)
            .set_position(lambda t:(
                int((W-bg_w)/2+8*math.sin((t+0.7)*0.55)),
                int((H-bg_h)/2+6*math.cos((t+0.7)*0.42)),
            )))
    tint=(ColorClip((W,H),color=(5,54,43)).set_opacity(0.10).set_duration(duration))
    return CompositeVideoClip([moving,tint],size=(W,H)).set_duration(duration)


def build_video(cards,output,work_dir,summary,total_original=None,losses=0):
    if not hasattr(Image,"ANTIALIAS"):
        Image.ANTIALIAS=Image.Resampling.LANCZOS

    from moviepy.editor import AudioFileClip,ColorClip,CompositeVideoClip,ImageClip,concatenate_videoclips

    if not cards:
        raise RuntimeError("Aucun coupon gagnant validé à monter")
    if not VIDEO_BACKGROUND.is_file():
        raise RuntimeError(f"Fond vidéo introuvable: {VIDEO_BACKGROUND}")

    total=len(cards)
    total_original=int(total_original or total)
    durations=[scene_duration(total,idx) for idx in range(total)]
    scenes=[]
    last_overlay=None

    for idx,path in enumerate(cards):
        duration=durations[idx]
        with Image.open(path) as opened:
            sw,sh=opened.size
        cw,ch=fit_card_size(sw,sh,max_w=TARGET_WIDTH,max_h=1185)
        if COUPON_Y+ch>=1335:
            raise RuntimeError("Carte de validation trop haute pour la zone sûre")

        overlay=work_dir/f"overlay_{idx+1:02d}.png"
        overlay_png(idx,total,summary,overlay,total_original=total_original,losses=losses)
        last_overlay=overlay
        shadow_path=work_dir/f"shadow_{idx+1:02d}.png"
        shadow_pad=make_card_shadow(cw,ch,shadow_path)

        bg=_animated_result_background(ImageClip,ColorClip,CompositeVideoClip,duration)
        shadow=(ImageClip(str(shadow_path),transparent=True)
                .resize(lambda t,d=duration:card_zoom(t,d))
                .set_duration(duration)
                .set_position(lambda t,d=duration,w=cw,h=ch,p=shadow_pad:
                              _shadow_position(t,d,w,h,p,COUPON_Y)))
        card=(ImageClip(str(path)).resize(width=cw)
              .resize(lambda t,d=duration:card_zoom(t,d))
              .set_duration(duration)
              .set_position(lambda t,d=duration,w=cw,h=ch:
                            _card_position(t,d,w,h,COUPON_Y)))

        next_preview=None
        if idx+1<total:
            next_path=cards[idx+1]
            with Image.open(next_path) as next_opened:
                nw,_=fit_card_size(next_opened.width,next_opened.height,
                                   max_w=TARGET_WIDTH,max_h=1185)
            preview_w=int(round(nw*0.94))
            next_preview=(ImageClip(str(next_path)).resize(width=preview_w).set_opacity(0.50)
                          .set_duration(duration).set_position((W-62,COUPON_Y+44)))

        ov=ImageClip(str(overlay),transparent=True).set_duration(duration)
        layers=[bg,shadow,card]
        if next_preview is not None:
            layers.append(next_preview)
        layers.append(ov)
        scenes.append(CompositeVideoClip(layers,size=(W,H)).set_duration(duration))

    # Short background tail: final score remains visible, then replay starts smoothly.
    tail_bg=_animated_result_background(ImageClip,ColorClip,CompositeVideoClip,LOOP_TAIL_SECONDS)
    tail_ov=ImageClip(str(last_overlay),transparent=True).set_duration(LOOP_TAIL_SECONDS)
    scenes.append(CompositeVideoClip([tail_bg,tail_ov],size=(W,H)).set_duration(LOOP_TAIL_SECONDS))

    final=concatenate_videoclips(scenes,method="compose")

    soundtrack=work_dir/"soundtrack.wav"
    synthesize_soundtrack(durations,soundtrack,results=True)
    audio=AudioFileClip(str(soundtrack)).set_duration(final.duration)
    final=final.set_audio(audio)

    output.parent.mkdir(parents=True,exist_ok=True)
    final.write_videofile(
        str(output),fps=30,codec="libx264",audio_codec="aac",preset="medium",
        bitrate="5000k",threads=4,
        ffmpeg_params=["-pix_fmt","yuv420p","-movflags","+faststart"],
        verbose=False,logger="bar",
    )
    try:
        audio.close()
        final.close()
    except Exception:
        pass


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
    build_video(cards,output,scenario_dir,summary,total_original=total,losses=lost)
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
