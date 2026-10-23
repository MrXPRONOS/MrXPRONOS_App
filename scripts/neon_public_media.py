#!/usr/bin/env python3
"""Upload a newly generated public image or video to Neon Object Storage."""
import mimetypes
import os
from pathlib import Path
from urllib.parse import quote


def upload_public(path, object_key, content_type=None):
    import boto3
    from botocore.config import Config
    endpoint = (os.getenv("NEON_S3_ENDPOINT") or "").strip().rstrip("/")
    access = os.getenv("NEON_S3_ACCESS_KEY_ID")
    secret = os.getenv("NEON_S3_SECRET_ACCESS_KEY")
    bucket = os.getenv("NEON_S3_BUCKET", "videos")
    if not all((endpoint, access, secret)) or not endpoint.startswith("https://"):
        raise RuntimeError("Neon Object Storage credentials are missing")
    file = Path(path)
    if not file.is_file() or file.stat().st_size < 1:
        raise FileNotFoundError(str(file))
    if object_key.startswith("/") or ".." in object_key.split("/"):
        raise ValueError("Unsafe object key")
    mime = content_type or mimetypes.guess_type(file.name)[0] or "application/octet-stream"
    client = boto3.client("s3", endpoint_url=endpoint, region_name="eu-central-1",
        aws_access_key_id=access, aws_secret_access_key=secret,
        config=Config(s3={"addressing_style": "path"}))
    client.upload_file(str(file), bucket, object_key, ExtraArgs={"ContentType": mime})
    remote = client.head_object(Bucket=bucket, Key=object_key)
    if int(remote.get("ContentLength", -1)) != file.stat().st_size:
        raise RuntimeError("Neon media upload verification failed")
    return endpoint + "/" + quote(bucket, safe="") + "/" + quote(object_key, safe="/")
