#!/usr/bin/env python3
"""Bind legacy PostgREST ledger clients to Cloudflare D1 using GitHub OIDC.

This adapter never exposes long-lived database credentials. It only sets
environment variables for subsequent steps in the same GitHub Actions job.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

DEFAULT_WORKER = "https://mrxpronos-publication-ledger.cinecanaux-xpronos.workers.dev"
AUDIENCE = "mrxpronos-telegram-ledger"


def main():
    url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    bearer = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    output = os.environ.get("GITHUB_ENV", "")
    if not all((url, bearer, output)):
        raise RuntimeError("GitHub OIDC permissions/id-token or GITHUB_ENV missing")
    worker = os.environ.get("MRX_PUBLICATION_LEDGER_URL", DEFAULT_WORKER).strip().rstrip("/")
    if not worker.startswith("https://") or ".workers.dev" not in urllib.parse.urlparse(worker).netloc:
        raise RuntimeError("Invalid Cloudflare ledger URL")
    endpoint = url + ("&" if "?" in url else "?") + urllib.parse.urlencode({"audience": AUDIENCE})
    req = urllib.request.Request(endpoint, headers={"Authorization": f"Bearer {bearer}"})
    with urllib.request.urlopen(req, timeout=25) as response:
        token = json.load(response)["value"]
    if token.count(".") != 2:
        raise RuntimeError("GitHub OIDC token not received")
    print("::add-mask::" + token, flush=True)
    with open(output, "a", encoding="utf-8") as fp:
        fp.write(f"SUPABASE_URL={worker}\n")
        fp.write(f"SUPABASE_SERVICE_ROLE_KEY={token}\n")
        fp.write(f"SUPABASE_KEY={token}\n")
    print("Publication ledger backend: Cloudflare D1 (GitHub OIDC).")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"LEDGER_CONFIG_ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
