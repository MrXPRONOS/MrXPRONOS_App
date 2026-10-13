#!/usr/bin/env python3
"""Prépare uniquement les nouvelles images JPEG Instagram (sans API payante).

Instagram n'accepte pas nos couvertures WebP comme image_url. Le fichier JPEG
est hébergé publiquement par GitHub Pages, sans serveur ni Storage payant.
"""
from __future__ import annotations
import argparse,json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from PIL import Image
try:
    from scripts.editorial_telegram import parsed_dt
except ImportError:
    from editorial_telegram import parsed_dt

ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/"assets/data/editorial_share_queue.json"

def recent(item,now):
    if not isinstance(item,dict) or item.get("retired") or item.get("kind") not in ("article","conseil"):
        return False
    d=parsed_dt(item.get("source_date"))
    return bool(d and now-timedelta(hours=72)<=d<=now+timedelta(hours=2)
                and item.get("platform_status",{}).get("instagram") not in ("sent","sending")
                and str(item.get("image") or "").endswith("-social.webp"))

def prepare(root=ROOT,queue_path=QUEUE,now=None,limit=8):
    now=now or datetime.now(timezone.utc)
    if not queue_path.is_file(): return {"created":0,"eligible":0}
    data=json.loads(queue_path.read_text(encoding="utf-8"))
    items=sorted((x for x in data if recent(x,now)),key=lambda x:parsed_dt(x["source_date"]),reverse=True)[:limit]
    created=0
    for item in items:
        source=(root/str(item["image"])).resolve()
        if not source.is_relative_to((root/"assets/images/editorial").resolve()) or not source.is_file():
            continue
        dest=source.with_suffix(".jpg")
        with Image.open(source) as im:
            if im.size!=(1080,1080):continue
            if not dest.exists():
                im.convert("RGB").save(dest,"JPEG",quality=88,optimize=True,progressive=True)
                created+=1
        if dest.stat().st_size > 8_000_000:
            dest.unlink(missing_ok=True);continue
        item["instagram_image"]=dest.relative_to(root).as_posix()
    queue_path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    result={"created":created,"eligible":len(items),"prepared":sum(bool(x.get("instagram_image")) for x in items)}
    print("EDITORIAL_INSTAGRAM_JPEGS",json.dumps(result))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--limit",type=int,default=8)
    args=p.parse_args();prepare(limit=max(0,args.limit))
