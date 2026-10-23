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
