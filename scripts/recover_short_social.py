#!/usr/bin/env python3
"""One-shot recovery of Instagram/Threads after the primary Short was published.

The original Telegram/Facebook/YouTube/Bluesky posts are never retried. The
same original MP4 artifact is used, and each missing platform has a permanent
Cloudflare D1 reservation keyed to SHA256 and target date.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime
from d1_publication_ledger import D1Ledger
from post_shorts_video import (resolve_public_url,post_instagram_reel,post_threads,
                               require_env)

PLATFORMS = ("instagram","threads")

def preflight(video: Path, manifest_file: Path, previous_file: Path):
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    old = json.loads(previous_file.read_text(encoding="utf-8"))
    target = str(manifest.get("target") or "")
    datetime.strptime(target,"%Y-%m-%d")
    count = int(manifest.get("count") or 0)
    if not 1 <= count <= 15:
        raise RuntimeError("Original daily video manifest has no valid selections")
    if not video.is_file() or video.suffix.lower()!=".mp4" or not 100000 <= video.stat().st_size <= 49000000:
        raise RuntimeError("Original MP4 artifact missing or invalid")
    status={str(x.get("platform")):x.get("ok") for x in old if isinstance(x,dict)}
    expected={"facebook","youtube","instagram","threads","bluesky"}
    if not expected.issubset(status):
        raise RuntimeError("Original social publication report is incomplete")
    if status["instagram"] is not False or status["threads"] is not False:
        raise RuntimeError("Recovery refused: original Instagram/Threads outcome is not a confirmed failure")
    if not all(status[x] is True for x in ("facebook","youtube","bluesky")):
        raise RuntimeError("Recovery refused: main video campaign is not confirmed")
    return target,count,hashlib.sha256(video.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--video",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--previous-report",type=Path,required=True)
    p.add_argument("--dry-run",action="store_true")
    args=p.parse_args()
    day,count,digest=preflight(args.video,args.manifest,args.previous_report)
    if args.dry_run:
        print("SOCIAL_RECOVERY_DRY_RUN",json.dumps({"date":day,"count":count,"sha256":digest,"platforms":PLATFORMS}))
        return 0

    for group in (["IG_USER_ID","META_ACCESS_TOKEN"],["THREADS_USER_ID","THREADS_ACCESS_TOKEN"]):
        ok,msg=require_env(group)
        if not ok:raise RuntimeError(msg)
    # Validate public URL BEFORE claiming a platform's one-shot dedup key.
    url=resolve_public_url(args.video,None)
    if not isinstance(url,str) or not url.startswith("https://"):
        raise RuntimeError("Public Neon media URL unavailable")
    ledger=D1Ledger()
    caption=(f"Pronostics du jour ⚽\n{count} sélections Mr XPRONOS.\n"
             "18+ • Joue responsablement.\n\n"
             "#football #pronostic #pronosdujour #mrxpronos")
    out=[]
    for platform,send in (("instagram",post_instagram_reel),("threads",post_threads)):
        key=("shorts_social_recovery_"+platform,"sha256:"+digest,day)
        if not ledger.claim(*key):
            out.append({"platform":platform,"status":"already_claimed"})
            continue
        try:
            result=send(url,caption)
            if not result.ok:
                raise RuntimeError(platform+" provider did not confirm a publication ID")
            ledger.mark(*key)
            out.append({"platform":platform,"status":"sent","verified_id":bool(result.data and result.data.get("id"))})
            print("SHORTS_SOCIAL_RECOVERY_SENT",platform)
        except Exception as exc:
            # Retain claim after uncertain provider failure. It must be
            # manually reconciled before trying this platform again.
            out.append({"platform":platform,"status":"error","error_type":type(exc).__name__})
            print("SHORTS_SOCIAL_RECOVERY_FAILED",platform,type(exc).__name__)
    target=Path("social_recovery_results.json")
    target.write_text(json.dumps({"date":day,"count":count,"platforms":out},indent=2),encoding="utf-8")
    if any(x["status"]=="error" for x in out):
        raise RuntimeError("At least one missing platform still failed; check the ledger before retrying")
    print("SHORTS_SOCIAL_RECOVERY_COMPLETE",json.dumps(out))
    return 0

if __name__=="__main__":raise SystemExit(main())
