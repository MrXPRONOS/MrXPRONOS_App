"""Read-only disaster-recovery drill from Cloudflare KV, authenticated by GitHub OIDC."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import requests
from scripts.actu_foot_github_vault import VaultError
from scripts.actu_foot_v2_oidc_backup import oidc_token, URL
from scripts.actu_foot_v2_operations import verify_directory
from scripts.actu_foot_v2_store import COLLECTIONS, verify_audit, decrypt

RECOVERY_URL=URL.replace("/v2/backup","/v2/recover")
def exercise(run,attempt,*,session=None,root=None):
    if not str(run).isdigit() or not str(attempt).isdigit():
        raise VaultError("Invalid source run/attempt")
    client=session or requests.Session()
    token=oidc_token(client)
    res=client.post(RECOVERY_URL,json={"run":str(run),"attempt":str(attempt)},
                    headers={"Authorization":"Bearer "+token},timeout=(10,65))
    res.raise_for_status()
    payload=res.json()
    if payload.get("ok") is not True or set(payload.get("files",{}))!=set(COLLECTIONS):
        raise VaultError("Cloudflare snapshot incomplete")
    proof=payload.get("provenance",{})
    if str(proof.get("run"))!=str(run) or str(proof.get("attempt"))!=str(attempt):
        raise VaultError("Snapshot provenance mismatch")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        target=Path(td)
        (target/"manifest.json").write_text(payload["manifest"],encoding="utf-8")
        for name,encrypted in payload["files"].items():
            (target/(name+".aes.json")).write_text(encrypted,encoding="utf-8")
        verified=verify_directory(target)
        if set(verified["collections"])!=set(COLLECTIONS):
            raise VaultError("Missing collection")
        audit,_=decrypt("audit",payload["files"]["audit"])
        verify_audit(audit)
        print("CLOUDFLARE_RECOVERY_DRILL_OK",len(verified["collections"]),len(audit))
        return {"collections":len(verified["collections"]),"audit_events":len(audit)}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--run",required=True)
    p.add_argument("--attempt",default="1")
    args=p.parse_args()
    exercise(args.run,args.attempt)
