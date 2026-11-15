#!/usr/bin/env python3
"""Read-only diagnostic for Bluesky SDK login and DID resolution.

No publishing, upload, media processing, or D1 writes. Never prints tokens,
passwords, API responses, handles, or exception messages.
"""
from __future__ import annotations

import os
import traceback
from pathlib import Path


def call_stage(stage, func):
    """Return a value or raise an exception with safe diagnostic breadcrumbs."""
    try:
        result = func()
    except Exception as exc:
        stack = traceback.extract_tb(exc.__traceback__)[-6:]
        frames = ",".join(f"{Path(f.filename).name}:{f.lineno}:{f.name}" for f in stack)
        print(f"BLUESKY_DIAG_FAIL stage={stage} type={type(exc).__name__} frames={frames}", flush=True)
        raise
    else:
        print(f"BLUESKY_DIAG_OK stage={stage}", flush=True)
        return result


def audit(handle, password):
    if not handle or not password:
        print("BLUESKY_DIAG_FAIL stage=configuration type=MissingCredentials", flush=True)
        return 3
    try:
        from atproto import Client
        from requests import Session
        from bluesky_video_processed import resolve_did_document, pds_host
    except Exception as exc:
        print(f"BLUESKY_DIAG_FAIL stage=imports type={type(exc).__name__}", flush=True)
        return 4

    try:
        client = call_stage("Client_constructor", Client)
        login_result = call_stage("Client_login", lambda: client.login(handle, password))
        did = str(getattr(login_result, "did", "") or "")
        if not did.startswith("did:"):
            print("BLUESKY_DIAG_FAIL stage=login_response type=MissingDid", flush=True)
            return 5
        did_doc = call_stage("resolve_DID", lambda: resolve_did_document(
            client, login_result, session=Session()
        ))
        host = call_stage("validate_PDS", lambda: pds_host(did_doc))
        # Requesting an auth assertion is read-only: no video upload, no post.
        import time
        authorization = call_stage("service_auth_token", lambda:
            client.com.atproto.server.get_service_auth({
                "aud": "did:web:" + host,
                "lxm": "com.atproto.repo.uploadBlob",
                "exp": int(time.time()) + 1800,
            })
        )
        if not getattr(authorization, "token", None):
            print("BLUESKY_DIAG_FAIL stage=service_auth_token type=MissingToken", flush=True)
            return 7
        account = call_stage("get_session", lambda:
            client.com.atproto.server.get_session()
        )
        confirmed = getattr(account, "email_confirmed", None)
        print("BLUESKY_DIAG_EMAIL_VERIFIED",
              "yes" if confirmed is True else "no" if confirmed is False else "unknown",
              flush=True)
        limits = call_stage("get_video_upload_limits", lambda:
            client.app.bsky.video.get_upload_limits()
        )
        can_upload = getattr(limits, "can_upload", None)
        daily_videos = getattr(limits, "remaining_daily_videos", None)
        daily_bytes = getattr(limits, "remaining_daily_bytes", None)
        print("BLUESKY_DIAG_VIDEO_LIMITS",
              "can_upload="+("yes" if can_upload is True else "no" if can_upload is False else "unknown"),
              "remaining_daily_videos="+str(daily_videos if isinstance(daily_videos,int) else "unknown"),
              "remaining_daily_bytes="+str(daily_bytes if isinstance(daily_bytes,int) else "unknown"),
              flush=True)
    except Exception:
        return 6
    print("BLUESKY_DIAG_AUTH_AND_LIMITS_OK (no upload, no post, no D1 write)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(audit(
        (os.environ.get("BLUESKY_HANDLE") or "").strip().lstrip("@").lower(),
        (os.environ.get("BLUESKY_APP_PASSWORD") or "").strip(),
    ))
