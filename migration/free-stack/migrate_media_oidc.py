#!/usr/bin/env python3
"""Transfer 113 public Supabase videos to Neon using GitHub OIDC, without S3 keys in GitHub."""
import hashlib
import json
import os
import sys
import time
from urllib.parse import quote
import requests

INVENTORY_FILE="migration/free-stack/media-inventory.json"
AUDIENCE="mrxpronos-neon-media-transfer"
URL="https://br-winter-truth-b9of9tss-mediaimport.compute.c-7.eu-central-1.aws.neon.tech/"
SUPABASE="https://nhwafcpndlufzzxexikh.supabase.co/storage/v1/object"
SERVICE_KEY=os.getenv("SUPABASE_SERVICE_ROLE_KEY","")
OIDC_REQUEST_URL=os.getenv("ACTIONS_ID_TOKEN_REQUEST_URL","")
OIDC_REQUEST_TOKEN=os.getenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN","")
if not SERVICE_KEY or not OIDC_REQUEST_URL or not OIDC_REQUEST_TOKEN:
    sys.exit("Missing source credential or GitHub OIDC environment")
inventory=json.load(open(INVENTORY_FILE,encoding="utf-8"))
assert len(inventory)==113 and sum(int(x["size"]) for x in inventory)==215013480
headers={"apikey":SERVICE_KEY,"Authorization":"Bearer "+SERVICE_KEY}
token=""
expires=0
source=requests.Session()
def get_oidc():
    global token,expires
    if token and time.time()<expires-120:return token
    join="&" if "?" in OIDC_REQUEST_URL else "?"
    url=OIDC_REQUEST_URL+join+"audience="+quote(AUDIENCE,safe="")
    resp=requests.get(url,headers={"Authorization":"Bearer "+OIDC_REQUEST_TOKEN},timeout=15)
    resp.raise_for_status()
    token=resp.json()["value"]
    segment=token.split(".")[1]
    import base64
    claims=json.loads(base64.urlsafe_b64decode(segment+"="*((-len(segment))%4)))
    expires=int(claims["exp"])
    return token
verified=0
for item in inventory:
    key=item["name"]
    assert key.startswith("shorts/2026/") and key.endswith(".mp4")
    remote=quote(key,safe="/")
    response=source.get(SUPABASE+"/authenticated/videos/"+remote,headers=headers,timeout=(15,90))
    if response.status_code in (401,403):
        response=source.get(SUPABASE+"/public/videos/"+remote,headers=headers,timeout=(15,90))
    response.raise_for_status()
    blob=response.content
    if len(blob)!=int(item["size"]):raise RuntimeError("Source size mismatch")
    checksum=hashlib.sha256(blob).hexdigest()
    import_headers={
      "Authorization":"Bearer "+get_oidc(),
      "Content-Type":"video/mp4",
      "X-MRX-Object-Key":key,
      "X-MRX-Object-Size":str(len(blob)),
      "X-MRX-SHA256":checksum
    }
    result=requests.post(URL,headers=import_headers,data=blob,timeout=(20,120))
    if not result.ok:
        raise RuntimeError("Destination upload failed: status="+str(result.status_code)+", response="+result.text[:120])
    output=result.json()
    if not output.get("verified") or output.get("bytes")!=len(blob):raise RuntimeError("Destination digest not validated")
    verified+=1
    if verified%10==0 or verified==len(inventory):
        print("SHA256 verified",verified,"of",len(inventory),flush=True)
assert verified==113
print("SUCCESS: 113/113 verified; source total 215013480 bytes")
