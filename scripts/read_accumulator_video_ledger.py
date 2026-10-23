#!/usr/bin/env python3
"""Exporte les matchs déjà PUBLIÉS en vidéo, depuis le registre Neon.

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
    from neon_telegram_ledger import records
    rows=records(KIND,day,limit=1000,columns=["ref_id","ref_date"])
    rows=[row for row in rows if str(row["ref_date"])==day]
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
