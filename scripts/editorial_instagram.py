#!/usr/bin/env python3
"""Instagram Feed : publication opt-in de cartes originales via Graph API officiel.

N'utilise aucune API générative, pas de services payants, jamais d'envoi implicite.
N'écrit un reçu 'sent' qu'après confirmation /media_publish de Meta.
"""
from __future__ import annotations
import argparse,json,os
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import quote,urlsplit
import requests
try:
    from scripts.editorial_telegram import parsed_dt,tagged_url,BASE
except ImportError:
    from editorial_telegram import parsed_dt,tagged_url,BASE

ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/"assets/data/editorial_share_queue.json"
GRAPH=os.getenv("IG_GRAPH_VERSION","v26.0")
API="https://graph.facebook.com/"

def eligible(item,now):
    if not isinstance(item,dict) or item.get("retired") or item.get("kind") not in ("article","conseil"):
        return False
    if (item.get("platform_status") or {}).get("instagram") in ("sent","sending"):return False
    d=parsed_dt(item.get("source_date"))
    if not d or not now-timedelta(hours=48)<=d<=now+timedelta(hours=2):return False
    image=str(item.get("instagram_image") or "")
    return bool(image.startswith("assets/images/editorial/") and image.endswith(".jpg")
                and str(item.get("url") or "").startswith(BASE))

def photo_url(item):
    path=str(item["instagram_image"])
    if ".." in path or "?" in path or "#" in path: raise ValueError("Chemin media non autorisé")
    return BASE+path

def publish(queue_path=QUEUE,enabled=False,now=None,request_post=requests.post,request_get=requests.get):
    now=now or datetime.now(timezone.utc)
    if not queue_path.exists():return {"sent":0,"skipped":"no_queue"}
    data=json.loads(queue_path.read_text(encoding="utf-8"))
    selected=next((x for x in data if eligible(x,now)),None)
    if not enabled:
        print("EDITORIAL_INSTAGRAM_DRY_RUN",selected.get("id") if selected else "none")
        return {"sent":0,"dry_run":True}
    user_id=os.getenv("IG_USER_ID","").strip()
    token=(os.getenv("META_ACCESS_TOKEN","") or os.getenv("META_PAGE_ACCESS_TOKEN","")).strip()
    if not user_id or not token:
        print("EDITORIAL_INSTAGRAM_NOT_CONFIGURED")
        return {"sent":0,"skipped":"missing_credentials"}
    if not selected:return {"sent":0,"eligible":0}
    if not user_id.isdigit():raise ValueError("IG_USER_ID doit être numérique")
    image_url=photo_url(selected)
    # Vérifie que l'URL publique renvoie bien un JPEG AVANT de créer le conteneur.
    # Cela couvre le délai de déploiement GitHub Pages.
    try:
        probe=request_get(image_url,timeout=(8,18),stream=True)
        probe.raise_for_status()
        content_type=str(probe.headers.get("Content-Type") or "").lower()
        if not ("image/jpeg" in content_type or "image/jpg" in content_type):
            print("EDITORIAL_INSTAGRAM_JPEG_NOT_LIVE",content_type)
            return {"sent":0,"skipped":"jpeg_not_published"}
    except requests.RequestException as exc:
        print("EDITORIAL_INSTAGRAM_MEDIA_UNAVAILABLE",type(exc).__name__)
        return {"sent":0,"skipped":"public_media_unavailable"}
    finally:
        try:
            probe.close()
        except (NameError,AttributeError):
            pass
    caption=(
        str(selected.get("title") or "Mr XPRONOS")[:280]
        +"\n\n⚽ Notre analyse complète sur Mr XPRONOS :\n"
        +tagged_url(selected,"instagram")
        +"\n\n18+ • Joue responsablement.\n"
        +"#football #analysefootball #mrxpronos"
    )
    api=f"{API}{GRAPH}/{quote(user_id,safe='')}"
    try:
        container=request_post(api+"/media",
            data={"image_url":image_url,"caption":caption,"access_token":token},
            timeout=(10,45))
        container.raise_for_status()
        payload=container.json()
        creation_id=payload.get("id") if isinstance(payload,dict) else None
        if not creation_id:raise ValueError("Meta n'a pas fourni creation_id")
        posted=request_post(api+"/media_publish",
            data={"creation_id":creation_id,"access_token":token},
            timeout=(10,45))
        posted.raise_for_status()
        data_post=posted.json()
        post_id=data_post.get("id") if isinstance(data_post,dict) else None
        if not post_id:raise ValueError("Meta n'a pas confirmé media_publish")
        selected.setdefault("platform_status",{})["instagram"]="sent"
        selected.setdefault("delivered",{})["instagram"]={"media_id":post_id,"at":now.isoformat()}
        queue_path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("EDITORIAL_INSTAGRAM_SENT",selected["id"],"media_id",post_id)
        return {"sent":1}
    except (requests.RequestException,ValueError,OSError) as exc:
        # Statut éventuellement ambigu, NE PAS déclencher de retry automatique.
        print("EDITORIAL_INSTAGRAM_FAILED_OR_AMBIGUOUS",type(exc).__name__)
        return {"sent":0,"failed":1}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--publish",action="store_true")
    args=p.parse_args();result=publish(enabled=args.publish)
    raise SystemExit(1 if result.get("failed") else 0)
