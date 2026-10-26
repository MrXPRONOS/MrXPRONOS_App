"""Upload only validated encrypted V2 backups to private Cloudflare Workers KV.

Requires GitHub Actions secrets CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID
and CLOUDFLARE_V2_KV_NAMESPACE_ID. Never accept credentials as CLI arguments.
The account's Cloudflare token must be restricted to the backup KV namespace
where supported and must not have broad account administrator privileges.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import requests

from scripts.actu_foot_github_vault import VaultError
from scripts.actu_foot_v2_operations import verify_directory

MAX_TOTAL=18_000_000
COMMIT_PATTERN=re.compile(r"[0-9a-f]{40}")


def build_payload(directory: Path, commit: str, run_id: int):
    if not COMMIT_PATTERN.fullmatch(commit):
        raise VaultError("Exact source commit SHA required")
    if type(run_id) is not int or run_id<=0:
        raise VaultError("Positive GitHub Actions run ID required")
    manifest=verify_directory(directory)
    prefix=f"snapshots/{commit}/{run_id}"
    body=[]
    byte_count=0
    for collection,meta in sorted(manifest["collections"].items()):
        source=directory/meta["filename"]
        ciphertext=source.read_text(encoding="utf-8")
        byte_count+=len(ciphertext.encode("utf-8"))
        body.append({"key":f"{prefix}/{collection}.aes.json","value":ciphertext})
    record={"format":"actufoot-v2-cloudflare-backup","source_commit":commit,
            "source_run_id":run_id,"collections":manifest["collections"]}
    header=json.dumps(record,sort_keys=True,separators=(",",":"))
    byte_count+=len(header)
    if byte_count>MAX_TOTAL:
        raise VaultError("Cloudflare backup exceeds size limit")
    body.append({"key":prefix+"/manifest.json","value":header})
    return body


def upload(directory: Path, *, commit: str, run_id: int, session=None) -> str:
    account=os.getenv("CLOUDFLARE_ACCOUNT_ID","")
    namespace=os.getenv("CLOUDFLARE_V2_KV_NAMESPACE_ID","")
    token=os.getenv("CLOUDFLARE_API_TOKEN","")
    if (not re.fullmatch(r"[a-f0-9]{32}",account) or
        not re.fullmatch(r"[a-f0-9]{32}",namespace) or not token):
        raise VaultError("Cloudflare KV backup credentials are not configured")
    payload=build_payload(directory,commit,run_id)
    client=session or requests.Session()
    base=f"https://api.cloudflare.com/client/v4/accounts/{account}/storage/kv/namespaces/{namespace}"
    headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"}
    response=client.put(base+"/bulk",json=payload,headers=headers,timeout=(10,60))
    response.raise_for_status()
    status=response.json()
    if status.get("success") is not True or status.get("result",{}).get("successful_key_count")!=len(payload):
        raise VaultError("Cloudflare backup bulk write incomplete")
    # Remote immutable version stamp to enable restoring from independently held copies.
    path=payload[-1]["key"]
    readback=client.post(base+"/bulk/get",json={"keys":[path],"type":"text"},
                         headers=headers,timeout=(10,30))
    readback.raise_for_status()
    result=readback.json()
    if result.get("success") is not True or result.get("result",{}).get("values",{}).get(path)!=payload[-1]["value"]:
        raise VaultError("Cloudflare backup manifest readback failed")
    return path


def main():
    from argparse import ArgumentParser
    p=ArgumentParser()
    p.add_argument("--directory",default="/tmp/actufoot-v2-backup")
    p.add_argument("--commit",required=True)
    p.add_argument("--run-id",required=True,type=int)
    args=p.parse_args()
    destination=upload(Path(args.directory),commit=args.commit,run_id=args.run_id)
    print("INDEPENDENT_ENCRYPTED_BACKUP_VERIFIED",destination)


if __name__=="__main__":
    main()
