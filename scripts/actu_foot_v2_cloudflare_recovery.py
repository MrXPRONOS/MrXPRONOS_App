"""Restore independently encrypted Cloudflare KV snapshots to an isolated directory.

Caller uses the recovery workflow's own OIDC audience. No production writes.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl,urlencode,urlparse,urlunparse
import requests
from scripts.actu_foot_github_vault import VaultError
from scripts.actu_foot_v2_store import COLLECTIONS,decrypt,verify_audit
from scripts.actu_foot_v2_operations import verify_directory
AUDIENCE="mrxpronos-actufoot-v2-recovery"
URL="https://mrxpronos-actufoot-v2-backup.cinecanaux-xpronos.workers.dev/v2/recovery"
def oidc_token(session):
    endpoint=os.getenv("ACTIONS_ID_TOKEN_REQUEST_URL","")
    secret=os.getenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN","")
    if not endpoint.startswith("https://") or not secret: raise VaultError("Missing GitHub OIDC identity")
    parsed=urlparse(endpoint)
    params=dict(parse_qsl(parsed.query,keep_blank_values=True))
    params["audience"]=AUDIENCE
    resp=session.get(urlunparse(parsed._replace(query=urlencode(params))),headers={"Authorization":"Bearer "+secret},timeout=20)
    resp.raise_for_status()
    token=resp.json().get("value")
    if not isinstance(token,str) or len(token.split("."))!=3: raise VaultError("Invalid OIDC response")
    return token
def verify_payload(payload,run_id,attempt):
    if not isinstance(payload,dict) or payload.get("ok") is not True: raise VaultError("Invalid backup response")
    files=payload.get("files")
    if not isinstance(files,dict) or set(files)!=set(COLLECTIONS): raise VaultError("Incomplete backup")
    try: manifest=json.loads(payload["manifest"])
    except (ValueError,KeyError,TypeError) as exc: raise VaultError("Invalid manifest") from exc
    if manifest.get("format")!="actufoot-v2-backup-v2" or set(manifest.get("collections",{}))!=set(COLLECTIONS):
        raise VaultError("Incorrect archive manifest")
    proof=payload.get("provenance")
    if not isinstance(proof,dict) or any((proof.get(k)!=v for k,v in
       {"run":str(run_id),"attempt":str(attempt),"repository":"MrXPRONOS/MrXPRONOS_App"}.items())):
        raise VaultError("Incorrect archive origin")
    if not re.fullmatch(r"[a-f0-9]{40}",str(proof.get("commit",""))): raise VaultError("Invalid source commit")
    decrypted={}
    for name in COLLECTIONS:
        ciphertext=files[name]
        if not isinstance(ciphertext,str) or len(ciphertext)>2500000: raise VaultError("Unexpected ciphertext")
        meta=manifest["collections"][name]
        if meta.get("filename")!=name+".aes.json" or hashlib.sha256(ciphertext.encode()).hexdigest()!=meta.get("sha256"):
            raise VaultError("Ciphertext digest mismatch")
        data,header=decrypt(name,ciphertext)
        if header["generation"]!=meta["generation"] or header["key_version"]!=meta["key_version"] or len(data)!=meta["record_count"]:
            raise VaultError("Encrypted collection metadata mismatch")
        if name=="audit":verify_audit(data)
        decrypted[name]=data
    anchor=payload.get("anchor")
    if anchor is not None:
        audit=decrypted["audit"]
        head=max(audit.values(),key=lambda row:row["sequence"]) if audit else None
        if not isinstance(anchor,dict) or anchor.get("sequence")!=(head["sequence"] if head else 0) or anchor.get("entry_hash")!=(head["entry_hash"] if head else "0"*64) or anchor.get("audit_generation")!=manifest["collections"]["audit"]["generation"]:
            raise VaultError("Audit anchor mismatch")
    return files,manifest
def recover(run_id,attempt,destination,session=None):
    if type(run_id) is not int or type(attempt) is not int or not (1<=run_id<10**18 and 1<=attempt<10**18):
        raise VaultError("Invalid snapshot selector")
    client=session or requests.Session()
    jwt=oidc_token(client)
    response=client.post(URL,json={"run_id":str(run_id),"attempt":str(attempt)},headers={"Authorization":"Bearer "+jwt},timeout=(10,60))
    response.raise_for_status()
    files,manifest=verify_payload(response.json(),run_id,attempt)
    destination=Path(destination)
    if destination.exists() and any(destination.iterdir()): raise VaultError("Recovery directory must be empty")
    destination.mkdir(mode=0o700,parents=True,exist_ok=True)
    for name in COLLECTIONS:
        file=destination/(name+".aes.json")
        file.write_text(files[name],encoding="utf-8")
        file.chmod(0o600)
    file=destination/"manifest.json"
    file.write_text(json.dumps(manifest,sort_keys=True),encoding="utf-8")
    file.chmod(0o600)
    verify_directory(destination)
    return {"run_id":run_id,"attempt":attempt,"verified_collections":len(COLLECTIONS)}
def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--run-id",required=True,type=int)
    p.add_argument("--attempt",type=int,default=1)
    p.add_argument("--destination",default="/tmp/actufoot-v2-rehearsal")
    args=p.parse_args()
    result=recover(args.run_id,args.attempt,Path(args.destination))
    print("V2_CLOUDFLARE_RECOVERY_VERIFIED",result["run_id"],result["verified_collections"])
if __name__=="__main__":main()
