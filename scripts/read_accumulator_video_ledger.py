#!/usr/bin/env python3
"""Exporte les matchs déjà PUBLIÉS en vidéo, depuis le registre Supabase.

Aucun combiné ne peut être créé si ce registre est inaccessible ou vide.
La clé est celle utilisée par send_short_production_telegram.py après envoi confirmé.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import requests

KIND="shorts_video_coupon"

def main():
    day=os.getenv("ACCUMULATOR_TEST_DATE") or datetime.now(timezone.utc).date().isoformat()
    base=(os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key=(os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or "").strip()
    if not (base and key):
        raise RuntimeError("Supabase indisponible : impossible de vérifier quels matchs ont été publiés en vidéo")
    response=requests.get(base+"/rest/v1/telegram_sent",params={
        "select":"ref_id,ref_date","kind":"eq."+KIND,
        "ref_date":"eq."+day,"limit":"1000",
    },headers={"apikey":key,"Authorization":"Bearer "+key},timeout=30)
    response.raise_for_status()
    rows=response.json()
    if not isinstance(rows,list):raise RuntimeError("Registre Supabase vidéo invalide")
    excluded=set()
    for row in rows:
        ref=str(row.get("ref_id") or "").strip()
        if ":bsd:" in ref:
            excluded.add("bsd:"+ref.rsplit(":bsd:",1)[-1])
        elif ref.startswith("bsd:"):
            excluded.add(ref)
    output=Path(os.getenv("ACCUMULATOR_VIDEO_MANIFEST","telegram_out/video_used_matches.json"))
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({"date":day,"kind":KIND,"published_video_ids":sorted(excluded),
                                  "published_video_count":len(excluded)},ensure_ascii=False,indent=2))
    print("ACCUMULATOR_VIDEO_LEDGER_VERIFIED",json.dumps({"date":day,"used":len(excluded)}))
    if not excluded:print("ACCUMULATOR_SKIP_NO_PUBLISHED_VIDEO",day)

if __name__=="__main__":main()
