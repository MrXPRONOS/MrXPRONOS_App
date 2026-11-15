#!/usr/bin/env python3
"""One-shot, fail-closed guard for Bluesky-only recovery of a proven validation.

No video upload, provider writes, or D1 changes take place in this module.
The associated workflow publishes only after guard() returns 'ready'.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path

REF="morning:2026-11-14"
DAY="2026-11-14"
OTHER=("facebook","youtube","instagram","threads")
TARGET="validation-2026-11-14-morning.mp4"
SUMMARY="4/4 VALIDÉS · AUCUN PERDU"


def assert_manifest(folder: Path):
    candidates=list(folder.rglob(TARGET))
    if len(candidates)!=1:
        raise RuntimeError("Exactly one proven validation MP4 is required")
    video=candidates[0]
    if video.stat().st_size < 100_000 or video.stat().st_size > 50_000_000:
        raise RuntimeError("Validation MP4 size outside Bluesky limits")
    manifest=list(folder.rglob("manifest.json"))
    if len(manifest)!=1:
        raise RuntimeError("Proven batch manifest not found or ambiguous")
    data=json.loads(manifest[0].read_text(encoding="utf-8"))
    matches=[x for x in data.get("published",[]) if
             x.get("slot")=="morning" and x.get("target")==DAY and
             x.get("summary")==SUMMARY and x.get("wins")==4 and
             x.get("losses")==0 and x.get("total")==4 and
             Path(x.get("video","")).name==TARGET]
    if len(matches)!=1:
        raise RuntimeError("Artifact does not prove expected exact validation batch")
    return video


def guard(ledger, video, handle):
    if not isinstance(handle, str) or not handle.strip():
        raise RuntimeError("Bluesky handle absent")
    rows=ledger.query(
        "SELECT kind,delivery_status,validation_details,telegram_message_id "
        "FROM telegram_sent WHERE ref_date=? AND ref_id=?",
        (DAY,REF)).get("results") or []
    by_kind={r["kind"]:r for r in rows}
    telegram=by_kind.get("shorts_video_validation") or {}
    if telegram.get("delivery_status")!="sent" or telegram.get("telegram_message_id")!=7042:
        raise RuntimeError("Telegram exact validation 7042 has not been confirmed")
    for platform in OTHER:
        receipt=by_kind.get("shorts_validation_social_"+platform) or {}
        try:
            provider_id=json.loads(receipt.get("validation_details") or "{}").get("id")
        except (TypeError,ValueError):
            provider_id=None
        if receipt.get("delivery_status")!="sent" or not provider_id:
            raise RuntimeError("A previously published social platform lacks evidence")

    bsky=by_kind.get("shorts_validation_social_bluesky")
    if bsky:
        if bsky.get("delivery_status")=="sent":
            try:
                provider_id=json.loads(bsky.get("validation_details") or "{}").get("id")
            except (TypeError,ValueError):
                provider_id=None
            if isinstance(provider_id,str) and provider_id.startswith("at://"):
                return "already_sent"
        raise RuntimeError("Bluesky validation reserved or uncertain; stop to prevent duplicate")

    digest=hashlib.sha256(Path(video).read_bytes()).hexdigest()
    ref=handle.strip().lstrip("@").lower()+":sha256:"+digest
    # Check ALL dates; the inner hash-based reservation dates the current run,
    # so a previous attempt on another day must also block this exact MP4.
    prior=ledger.query(
        "SELECT ref_date,delivery_status FROM telegram_sent "
        "WHERE kind=? AND ref_id=? LIMIT 2",
        ("bsd_v2_bluesky_video",ref)).get("results") or []
    if prior:
        raise RuntimeError("Identical video has a prior Bluesky reservation; review first")
    return "ready"


def main():
    from d1_publication_ledger import D1Ledger
    folder=Path(os.environ.get("RECOVERY_ARTIFACT_DIR","recovered"))
    video=assert_manifest(folder)
    status=guard(D1Ledger(),video,os.getenv("BLUESKY_HANDLE",""))
    print("BLUESKY_VALIDATION_RECOVERY_GUARD",status,flush=True)
    with open(os.environ.get("GITHUB_OUTPUT","/dev/null"),"a",encoding="utf-8") as output:
        output.write("status="+status+"\n")
        output.write("video="+str(video)+"\n")


if __name__=="__main__":
    main()
