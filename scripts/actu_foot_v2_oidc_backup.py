"""Push validated V2 ciphertext archives to Cloudflare using GitHub OIDC.

No permanent Cloudflare API token is stored in GitHub. Short-lived GitHub OIDC
JWT is cryptographically verified by Cloudflare Worker (repository, workflow,
branch, audience and claims). No plaintext is transmitted.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from urllib.parse import urlparse,parse_qsl,urlencode,urlunparse
import requests

from scripts.actu_foot_github_vault import VaultError
from scripts.actu_foot_v2_operations import verify_directory

AUDIENCE="mrxpronos-actufoot-v2-backup"
URL="https://mrxpronos-actufoot-v2-backup.cinecanaux-xpronos.workers.dev/v2/backup"


def oidc_token(session=None) -> str:
    endpoint=os.getenv("ACTIONS_ID_TOKEN_REQUEST_URL","")
    bearer=os.getenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN","")
    if not endpoint.startswith("https://") or not bearer:
        raise VaultError("GitHub Actions OIDC identity not available")
    parts=urlparse(endpoint)
    query=dict(parse_qsl(parts.query,keep_blank_values=True))
    query["audience"]=AUDIENCE
    target=urlunparse(parts._replace(query=urlencode(query)))
    client=session or requests.Session()
    resp=client.get(target,headers={"Authorization":"Bearer "+bearer},timeout=20)
    resp.raise_for_status()
    value=resp.json().get("value")
    if not isinstance(value,str) or len(value.split("."))!=3:
        raise VaultError("Invalid OIDC token response")
    return value


def push(directory: Path, session=None) -> dict:
    index=verify_directory(directory)
    if set(index["collections"])!={"audit","live_events","matches","news","publications","settings","statistics"}:
        raise VaultError("All seven collections required for immutable snapshot")
    files={name:(directory/meta["filename"]).read_text(encoding="utf-8")
           for name,meta in index["collections"].items()}
    manifest=(directory/"manifest.json").read_text(encoding="utf-8")
    client=session or requests.Session()
    token=oidc_token(client)
    reply=client.post(URL,json={"files":files,"manifest":manifest},
                      headers={"Authorization":"Bearer "+token},timeout=(12,65))
    reply.raise_for_status()
    data=reply.json()
    if data.get("ok") is not True or data.get("count")!=7:
        raise VaultError("Cloudflare did not confirm complete encrypted snapshot")
    return {"run":data["run"],"collections":data["count"]}


if __name__=="__main__":
    summary=push(Path("/tmp/actufoot-v2-backup"))
    print("CLOUDFLARE_OIDC_ENCRYPTED_BACKUP_DONE",summary["run"],summary["collections"])
