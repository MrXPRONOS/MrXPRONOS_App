#!/usr/bin/env python3
"""File d'attente de partage idempotente, en JSON local, sans token requis.
Ne publie PAS automatiquement: un intégrateur externe pourra consommer la file.
"""
from __future__ import annotations
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/"assets"/"data"/"editorial_share_queue.json"
PLATFORMS=("facebook","instagram","threads","telegram","tiktok","youtube")
def build(root=ROOT, queue_path=QUEUE,limit=20):
    previous={}
    if queue_path.exists():
        try:
            previous={x["id"]:x for x in json.loads(queue_path.read_text(encoding="utf-8")) if isinstance(x,dict) and x.get("id")}
        except (ValueError,OSError): previous={}
    now=datetime.now(timezone.utc).isoformat()
    for name,kind in (("articles.json","article"),("conseils.json","conseil"),("footnews.json","news")):
        f=root/name
        if not f.is_file():continue
        records=json.loads(f.read_text(encoding="utf-8"))
        for obj in records[:limit]:
            if not isinstance(obj,dict) or obj.get("active") is False:continue
            title=str(obj.get("title") or "").strip()
            if not title:continue
            slug=str(obj.get("slug") or obj.get("link") or title)
            unique=hashlib.sha256((kind+"|"+slug).encode()).hexdigest()[:24]
            if unique in previous:continue
            if kind=="news":
                url=str(obj.get("link") or "")
            else:
                url="https://mrxpronos.github.io/MrXPRONOS_App/"+("articles" if kind=="article" else "conseils")+"/"+slug+"/"
            previous[unique]={"id":unique,"kind":kind,"title":title,"url":url,
              "source_date":str(obj.get("date") or obj.get("published") or obj.get("published_at") or ""),
              "visual_variant":str(obj.get("visual_variant") or "legacy"),
              "image":obj.get("social_image") or obj.get("image_url") or "",
              "story_image":obj.get("story_image") or "",
              "status":"pending_review","created_at":now,
              "platform_status":{p:"not_requested" for p in PLATFORMS}}
    # Préserver les anciens états de diffusion et enrichir les entrées existantes.
    lookup = {}
    for name,kind in (("articles.json","article"),("conseils.json","conseil"),("footnews.json","news")):
        f=root/name
        if not f.is_file():continue
        for obj in json.loads(f.read_text(encoding="utf-8"))[:limit]:
            if not isinstance(obj,dict):continue
            slug=str(obj.get("slug") or obj.get("link") or obj.get("title") or "")
            ident=hashlib.sha256((kind+"|"+slug).encode()).hexdigest()[:24]
            lookup[ident] = obj
    for ident,item in previous.items():
        obj=lookup.get(ident)
        if obj:
            item["source_date"]=str(obj.get("date") or obj.get("published") or obj.get("published_at") or item.get("source_date") or "")
            item["visual_variant"]=str(obj.get("visual_variant") or item.get("visual_variant") or "legacy")
            item["image"]=obj.get("social_image") or obj.get("image_url") or item.get("image") or ""
            item["story_image"]=obj.get("story_image") or item.get("story_image") or ""
    result=sorted(previous.values(),key=lambda x:x.get("created_at",""),reverse=True)
    queue_path.parent.mkdir(parents=True,exist_ok=True)
    queue_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("EDITORIAL_QUEUE",json.dumps({"items":len(result),"new_or_existing":len(previous)}))
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--limit",type=int,default=20)
    args=p.parse_args();build(limit=max(0,args.limit))
