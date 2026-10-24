"""Upload public photo/MP4 to Neon Storage through restricted GitHub OIDC service."""
import hashlib
import os
import requests
from urllib.parse import quote
from pathlib import Path

UPLOAD_URL="https://br-winter-truth-b9of9tss-mrxmedia.compute.c-7.eu-central-1.aws.neon.tech/"
AUDIENCE="mrxpronos-public-media"

def upload_public_media(path, key):
    path=Path(path)
    if not path.is_file() or not path.stat().st_size:
        raise RuntimeError("Media file unavailable")
    endpoint=os.getenv("ACTIONS_ID_TOKEN_REQUEST_URL","")
    bearer=os.getenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN","")
    if not endpoint or not bearer:
        raise RuntimeError("GitHub OIDC required for Neon media")
    token_result=requests.get(endpoint+("&" if "?" in endpoint else "?")+"audience="+quote(AUDIENCE),
        headers={"Authorization":"Bearer "+bearer},timeout=15)
    token_result.raise_for_status()
    token=token_result.json().get("value")
    if not token:raise RuntimeError("Neon media OIDC empty")
    mime="video/mp4" if key.endswith(".mp4") else "image/jpeg"
    data=path.read_bytes()
    digest=hashlib.sha256(data).hexdigest()
    response=requests.post(UPLOAD_URL,headers={
        "Authorization":"Bearer "+token,"Content-Type":mime,
        "X-MRX-Object-Key":key,"X-MRX-SHA256":digest
    },data=data,timeout=(15,150))
    if response.status_code!=200:
        raise RuntimeError("Neon media upload HTTP "+str(response.status_code))
    result=response.json()
    if not result.get("verified") or result.get("sha256")!=digest or result.get("bytes")!=len(data):
        raise RuntimeError("Neon public media integrity not confirmed")
    url=result.get("url")
    if not isinstance(url,str) or not url.startswith("https://"):
        raise RuntimeError("Neon media public URL invalid")
    return url
