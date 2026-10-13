#!/usr/bin/env python3
"""Publication Threads gratuite des liens du site via l'API officielle Meta.

Deux étapes /threads -> /threads_publish ; pas de post sans --publish + secrets.
Le lien Open Graph porte des UTM, aucun média protégé n'est téléchargé.
"""
from __future__ import annotations
import argparse,json,os
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import quote
import requests

try:
    from scripts.editorial_telegram import parsed_dt,tagged_url,BASE
except ImportError:
    from editorial_telegram import parsed_dt,tagged_url,BASE

ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/"assets/data/editorial_share_queue.json"
API="https://graph.threads.net/v1.0"

def eligible(item,now):
    if not isinstance(item,dict) or item.get("retired"):
        return False
    if item.get("kind") not in ("article","conseil"):return False
    if (item.get("platform_status") or {}).get("threads") in ("sent","sending"):return False
    if not str(item.get("url") or "").startswith(BASE):return False
    when=parsed_dt(item.get("source_date"))
    return bool(when and now-timedelta(hours=48)<=when<=now+timedelta(hours=2))

def publish(queue_path=QUEUE,enabled=False,now=None,request_post=requests.post):
    now=now or datetime.now(timezone.utc)
    if not queue_path.is_file():return {"sent":0,"skipped":True}
    data=json.loads(queue_path.read_text(encoding="utf-8"))
    selected=next((x for x in data if eligible(x,now)),None)
    if not enabled:
        print("EDITORIAL_THREADS_DRY_RUN",selected.get("id") if selected else "none")
        return {"sent":0,"dry_run":True}
    token=os.getenv("THREADS_ACCESS_TOKEN","").strip()
    user_id=os.getenv("THREADS_USER_ID","").strip()
    if not token or not user_id:
        print("EDITORIAL_THREADS_NOT_CONFIGURED");return {"sent":0,"skipped":True}
    if selected is None:return {"sent":0,"eligible":0}
    url=tagged_url(selected,"threads")
    title=str(selected.get("title") or "Mr XPRONOS")[:260]
    message=f"{title}\n\n⚽ À lire sur Mr XPRONOS.\n18+ • Jeu responsable"
    try:
        headers={"Authorization":"Bearer "+token}
        container=request_post(f"{API}/{quote(user_id,safe='')}/threads",
            data={"media_type":"TEXT","text":message,"link_attachment":url},
            headers=headers,timeout=(10,40))
        container.raise_for_status()
        entry=container.json()
        creation_id=entry.get("id") if isinstance(entry,dict) else None
        if not creation_id:raise ValueError("Threads container id missing")
        result=request_post(f"{API}/{quote(user_id,safe='')}/threads_publish",
            data={"creation_id":creation_id},headers=headers,timeout=(10,45))
        result.raise_for_status()
        payload=result.json()
        post_id=payload.get("id") if isinstance(payload,dict) else None
        if not post_id:raise ValueError("Threads publish id missing")
        selected.setdefault("platform_status",{})["threads"]="sent"
        selected.setdefault("delivered",{})["threads"]={"post_id":str(post_id),"at":now.isoformat()}
        queue_path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("EDITORIAL_THREADS_SENT",selected.get("id"),"post_id",post_id)
        return {"sent":1}
    except (requests.RequestException,ValueError,OSError) as exc:
        # Ne réessaie pas automatiquement l'envoi: le serveur Meta a pu réussir.
        print("EDITORIAL_THREADS_FAILED_OR_AMBIGUOUS",type(exc).__name__)
        return {"sent":0,"failed":1}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--publish",action="store_true",help="Publier réellement uniquement avec autorisation")
    args=p.parse_args()
    result=publish(enabled=args.publish)
    raise SystemExit(1 if result.get("failed") else 0)
