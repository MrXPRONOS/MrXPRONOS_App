#!/usr/bin/env python3
"""Immutable public photo/MP4 hosting through Cloudflare KV, independent of Neon/Supabase.

Uploads require verified GitHub Actions OIDC from the two production workflows.
Only SHA256-addressed public social assets are accepted by the Worker. The
original media never leaves this workflow except to Cloudflare; D1 continues
to manage all publication claims separately.
"""
from __future__ import annotations

import hashlib
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests

HOST = "https://mrxpronos-public-social-media.cinecanaux-xpronos.workers.dev"
AUDIENCE = "mrxpronos-public-media-v1"
MAX_BYTES = 24 * 1024 * 1024
KEY_PATTERN = re.compile(
    r"^(?:shorts/\d{4}/\d{2}/\d{2}/[a-f0-9]{24}\.mp4|"
    r"images/mrxpronos-combine/\d{4}-\d{2}-\d{2}/[a-f0-9]{24}\.jpg)$"
)


class PublicMediaError(RuntimeError):
    pass


def _token(session):
    endpoint = os.getenv("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    bearer = os.getenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    if not endpoint or not bearer:
        raise PublicMediaError("Authenticated GitHub Actions OIDC context required")
    response = session.get(
        endpoint + ("&" if "?" in endpoint else "?") + "audience=" + quote(AUDIENCE),
        headers={"Authorization": "Bearer " + bearer}, timeout=20
    )
    response.raise_for_status()
    value = response.json().get("value")
    if not isinstance(value, str) or not value:
        raise PublicMediaError("GitHub OIDC token missing")
    return value


def upload_public_media(path, key, *, session=requests, wait_for_cdn=True):
    file = Path(path)
    if not file.is_file():
        raise PublicMediaError("Public media file missing: " + file.name)
    if not KEY_PATTERN.fullmatch(str(key)):
        raise PublicMediaError("Invalid immutable public media key")
    mime = "video/mp4" if str(key).endswith(".mp4") else "image/jpeg"
    if file.suffix.lower() not in (".mp4", ".jpg") or (
        (mime == "video/mp4") != (file.suffix.lower() == ".mp4")
    ):
        raise PublicMediaError("Public media file extension and key disagree")
    size = file.stat().st_size
    if size < 100 or size > MAX_BYTES:
        raise PublicMediaError(f"Public media unsupported size {size}; maximum 24 MiB")
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    if digest[:24] not in str(key):
        raise PublicMediaError("SHA256 media path does not match file")
    token = _token(session)
    with file.open("rb") as source:
        response = session.put(
            HOST + "/upload?key=" + quote(key, safe="/"),
            data=source,
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": mime,
                "Content-Length": str(size),
            },
            timeout=180,
        )
    response.raise_for_status()
    data = response.json()
    if (data.get("ok") is not True or data.get("key") != key or
            data.get("sha256") != digest or data.get("size") != size):
        raise PublicMediaError("Cloudflare did not confirm immutable media integrity")
    url = HOST + "/" + key
    if data.get("url") != url:
        raise PublicMediaError("Cloudflare returned unexpected public media URL")
    if wait_for_cdn:
        # KV is eventually consistent across geographic locations. Preflight the
        # public URL before sending Meta a container-creation request.
        for attempt in range(20):
            try:
                public = session.head(url, timeout=14)
                if public.status_code == 200 and (
                    public.headers.get("Content-Type", "").split(";")[0] == mime and
                    int(public.headers.get("Content-Length", "0")) == size
                ):
                    return url
            except (requests.RequestException, ValueError):
                pass
            if attempt < 19:
                time.sleep(4)
        raise PublicMediaError("Public Cloudflare media URL could not be verified")
    return url
