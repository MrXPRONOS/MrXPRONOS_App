#!/usr/bin/env python3
"""Diffusion Facebook Page de liens éditoriaux via Graph API (sans coût logiciel).

Utilise les Open Graph du site: ne réhéberge pas les médias sur Meta.
Aucun envoi sans --publish + META_PAGE_ID + META_PAGE_ACCESS_TOKEN.
"""
from __future__ import annotations
import argparse,json,os,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.editorial_telegram import parsed_dt,tagged_url,BASE

ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/"assets/data/editorial_share_queue.json"

def eligible(item,now):
    if item.get("retired") or item.get("kind") not in ("article","conseil"):return False
    if item.get("platform_status",{}).get("facebook") in ("sent","sending"):return False
    if not str(item.get("url","")).startswith(BASE):return False
    when=parsed_dt(item.get("source_date"))
    return bool(when and now-timedelta(hours=48)<=when<=now+timedelta(hours=2))

def publish(queue_path=QUEUE, enabled=False,now=None,request_post=requests.post):
    now=now or datetime.now(timezone.utc)
    if not queue_path.is_file():return {"sent":0,"skipped":True}
    data=json.loads(queue_path.read_text(encoding="utf-8"))
    selected=next((i for i in data if isinstance(i,dict) and eligible(i,now)),None)
    if not enabled:
        print("EDITORIAL_FACEBOOK_DRY_RUN",selected.get("id") if selected else "none")
        return {"sent":0,"dry_run":True}
    page_id=os.getenv("META_PAGE_ID","").strip()
    token=os.getenv("META_PAGE_ACCESS_TOKEN","").strip()
    if not page_id or not token:
        print("EDITORIAL_FACEBOOK_NOT_CONFIGURED")
        return {"sent":0,"skipped":True}
    if selected is None:return {"sent":0,"eligible":0}
    url="https://graph.facebook.com/v26.0/"+page_id+"/feed"
    message=str(selected.get("title") or "Mr XPRONOS")[:500]+"\n\nAnalyse et conseils football sur Mr XPRONOS.\n⚽ 18+ • Jeu responsable"
    try:
        response=request_post(url, data={"message":message,"link":tagged_url(selected).replace("utm_source=telegram","utm_source=facebook"),
                                          "access_token":token},timeout=(10,45))
        response.raise_for_status()
        payload=response.json()
        ident=payload.get("id") if isinstance(payload,dict) else None
        if not ident:raise ValueError("Meta n'a pas confirmé la publication")
        selected.setdefault("platform_status",{})["facebook"]="sent"
        selected.setdefault("delivered",{})["facebook"]={"post_id":ident,"at":now.isoformat()}
        queue_path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("EDITORIAL_FACEBOOK_SENT",selected.get("id"),"post_id",ident)
        return {"sent":1}
    except (requests.RequestException, ValueError, OSError) as exc:
        print("EDITORIAL_FACEBOOK_FAILED",type(exc).__name__)
        return {"sent":0,"failed":1}

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--publish",action="store_true")
    args=parser.parse_args()
    result=publish(enabled=args.publish)
    raise SystemExit(1 if result.get("failed") else 0)
