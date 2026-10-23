#!/usr/bin/env python3
"""Private uploads to Neon Object Storage with an explicitly configured public CDN.

The S3 endpoint is not assumed public. No Supabase fallback.
"""
from pathlib import Path
from urllib.parse import quote, urlsplit
import mimetypes
import os
import requests


def upload_public(path, object_key, *, content_type=None):
    import boto3
    from botocore.config import Config
    src=Path(path)
    if not src.is_file() or src.stat().st_size<1:
        raise FileNotFoundError(src)
    if object_key.startswith("/") or ".." in object_key.split("/"):
        raise ValueError("Unsafe media object key")
    # Preferred in GitHub Actions: short-lived, signed GitHub OIDC token.
    # S3 credentials stay only in Cloudflare, never in GitHub Secrets.
    worker=os.getenv("NEON_MEDIA_UPLOAD_URL","").strip()
    if worker:
        token_url=os.getenv("ACTIONS_ID_TOKEN_REQUEST_URL","").strip()
        token_secret=os.getenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN","").strip()
        if not token_url or not token_secret:
            raise RuntimeError("GitHub Actions id-token: write permission required for Neon media")
        from urllib.parse import urlencode
        joiner="&" if "?" in token_url else "?"
        jwt_response=requests.get(token_url+joiner+urlencode({"audience":"mrxpronos-media"}),
            headers={"Authorization":"Bearer "+token_secret},timeout=(8,20))
        jwt_response.raise_for_status()
        jwt=jwt_response.json().get("value")
        if not jwt:
            raise RuntimeError("GitHub OIDC request did not return a token")
        mime=content_type or mimetypes.guess_type(src.name)[0] or "application/octet-stream"
        with src.open("rb") as content:
            response=requests.post(worker,headers={
                "Authorization":"Bearer "+jwt,"Content-Type":mime},data=content,
                timeout=(12,160))
        response.raise_for_status()
        result=response.json()
        if not result.get("url") or not result.get("key"):
            raise RuntimeError("Cloudflare Neon upload missing public media URL")
        return result["url"]
    endpoint=(os.getenv("NEON_S3_ENDPOINT") or "").rstrip("/")
    public=(os.getenv("NEON_PUBLIC_MEDIA_BASE_URL") or "").rstrip("/")
    access=os.getenv("NEON_S3_ACCESS_KEY_ID")
    secret=os.getenv("NEON_S3_SECRET_ACCESS_KEY")
    bucket=os.getenv("NEON_S3_BUCKET") or "videos"
    if not all((endpoint,public,access,secret)):
        raise RuntimeError("Neon S3 credentials and public media CDN URL required")
    for u in (endpoint,public):
        parts=urlsplit(u)
        if parts.scheme!="https" or not parts.hostname:
            raise RuntimeError("Media URL must be HTTPS")
    mime=content_type or mimetypes.guess_type(src.name)[0] or "application/octet-stream"
    client=boto3.client("s3",endpoint_url=endpoint,
        region_name=os.getenv("NEON_S3_REGION","eu-central-1"),
        aws_access_key_id=access,aws_secret_access_key=secret,
        config=Config(s3={"addressing_style":"path"}))
    client.upload_file(str(src),bucket,object_key,ExtraArgs={"ContentType":mime})
    meta=client.head_object(Bucket=bucket,Key=object_key)
    if int(meta.get("ContentLength",-1))!=src.stat().st_size:
        raise RuntimeError("Neon upload size mismatch")
    url=public+"/"+quote(object_key,safe="/")
    with requests.get(url,headers={"Range":"bytes=0-0"},
                      stream=True,timeout=(8,25),allow_redirects=True) as response:
        response.raise_for_status()
        remote_mime=response.headers.get("Content-Type","").lower()
        if not remote_mime.startswith(mime.split("/")[0]+"/"):
            raise RuntimeError("Public CDN URL does not return expected media type")
        if urlsplit(response.url).scheme!="https":
            raise RuntimeError("Media CDN redirects to non-HTTPS URL")
    return url
