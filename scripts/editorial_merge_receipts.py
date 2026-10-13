#!/usr/bin/env python3
"""Merge les accusés de réception sociaux sans perdre les mises à jour récentes.

Une confirmation "sent" est monotone : aucune autre régénération de file ne
doit repasser cette plateforme en "not_requested".
"""
from __future__ import annotations
import argparse,json
from pathlib import Path

def merge(current,received):
    present={str(x.get("id")):x for x in current if isinstance(x,dict) and x.get("id")}
    merged=0
    for incoming in received:
        if not isinstance(incoming,dict):continue
        item=present.get(str(incoming.get("id")))
        if item is None:continue
        for platform,state in (incoming.get("platform_status") or {}).items():
            if state!="sent":continue
            info=(incoming.get("delivered") or {}).get(platform)
            if not isinstance(info,dict) or not info:continue
            old=(item.get("platform_status") or {}).get(platform)
            if old=="sent":continue
            item.setdefault("platform_status",{})[platform]="sent"
            item.setdefault("delivered",{})[platform]=info
            merged+=1
    return merged

def run(current_path,receipts_path):
    current=json.loads(Path(current_path).read_text(encoding="utf-8"))
    receipts=json.loads(Path(receipts_path).read_text(encoding="utf-8"))
    updated=merge(current,receipts)
    if updated:
        Path(current_path).write_text(json.dumps(current,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("EDITORIAL_DELIVERY_RECEIPTS_MERGED",updated)
    return updated

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--queue",default="assets/data/editorial_share_queue.json")
    p.add_argument("--receipt",required=True)
    a=p.parse_args();run(a.queue,a.receipt)
