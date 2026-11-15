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
        call_stage("validate_PDS", lambda: pds_host(did_doc))
    except Exception:
        return 6
    print("BLUESKY_DIAG_PREFLIGHT_OK (no upload, no post, no D1 write)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(audit(
        (os.environ.get("BLUESKY_HANDLE") or "").strip().lstrip("@").lower(),
        (os.environ.get("BLUESKY_APP_PASSWORD") or "").strip(),
    ))
