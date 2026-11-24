"""OIDC-authenticated independent archive copy and readback; no persistent API token."""
import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse,parse_qsl,urlencode,urlunparse
import requests
from scripts.actu_foot_github_vault import VaultError
from scripts.actu_foot_v3_archive import verify_archive_path
URL="https://mrxpronos-actufoot-v2-backup.cinecanaux-xpronos.workers.dev/v3/archive"
class CloudArchive:
    def __init__(self,*,rehearsal=False,session=None):
        self.session=session or requests.Session()
        self.rehearsal=rehearsal
    def token(self):
        endpoint=os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL","")
        bearer=os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN","")
        if not endpoint.startswith("https://") or not bearer:raise VaultError("OIDC unavailable")
        parsed=urlparse(endpoint);query=dict(parse_qsl(parsed.query,keep_blank_values=True))
        query["audience"]="mrxpronos-actufoot-v3-rehearsal" if self.rehearsal else "mrxpronos-actufoot-v3-archive"
        response=self.session.get(urlunparse(parsed._replace(query=urlencode(query))),headers={"Authorization":"Bearer "+bearer},timeout=20)
        response.raise_for_status()
        token=response.json().get("value")
        if not isinstance(token,str) or len(token.split("."))!=3:raise VaultError("Invalid OIDC identity")
        return token
    def request(self,body):
        response=self.session.post(URL+("-rehearsal" if self.rehearsal else ""),json=body,headers={"Authorization":"Bearer "+self.token()},timeout=(10,60))
        response.raise_for_status()
        data=response.json()
        if data.get("ok") is not True:raise VaultError("Archive provider did not confirm")
        return data
    def recover(self,path,digest):
        data=self.request({"action":"read","path":path,"sha256":digest})
        blob=data.get("ciphertext")
        if not isinstance(blob,str) or hashlib.sha256(blob.encode()).hexdigest()!=digest:raise VaultError("Independent archive integrity mismatch")
        verify_archive_path(path,blob)
        return blob
    def persist(self,path,payload):
        verify_archive_path(path,payload)
        digest=hashlib.sha256(payload.encode()).hexdigest()
        result=self.request({"action":"write","path":path,"sha256":digest,"ciphertext":payload})
        if result.get("sha256")!=digest or self.recover(path,digest)!=payload:raise VaultError("Independent copy readback failed")
        return digest

def recover_inventory(receipts,destination,cloud,*,limit=24,after=""):
    """Restore a bounded set of independently stored ciphertexts, never overwrite live Git."""
    if type(limit) is not int or not 1<=limit<=100:
        raise VaultError("Invalid recovery bound")
    if not isinstance(after,str) or (after and after not in receipts):
        raise VaultError("Unknown archive recovery cursor")
    root=Path(destination)
    if root.exists() and any(root.iterdir()):
        raise VaultError("Recovery directory must be empty")
    root.mkdir(parents=True,exist_ok=True)
    # Inventory can be provided from a recovered and verified V2 audit collection.
    pending=[(p,m) for p,m in sorted(receipts.items()) if p>after]
    batch=pending[:limit]
    for path,meta in batch:
        blob=cloud.recover(path,meta["sha256"])
        rows,_=verify_archive_path(path,blob)
        if len(rows)!=meta["count"]:raise VaultError("Recovered archive record count differs")
        target=root/path.removeprefix("assets/data/private/actufoot_v2/archive/")
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(blob,encoding="utf-8")
    remaining=len(pending)-len(batch)
    return {"verified":len(batch),"total":len(receipts),"remaining":remaining,"next_after":batch[-1][0] if remaining else None}
