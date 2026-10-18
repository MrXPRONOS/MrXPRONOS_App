#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconnect and maintain the official Threads API user token.

No access token, app secret or one-time authorization code is printed.
Only GitHub Actions Secrets are used to persist credentials. Never commit tokens.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

import requests

GRAPH = "https://graph.threads.net"
DEFAULT_REDIRECT = "https://mrxpronos.github.io/MrXPRONOS_App/threads-callback.html"
EXPECTED_USERNAME = "mr_xpronos"


class ThreadsError(RuntimeError):
    """An actionable, sanitized error (never includes secrets)."""


def required(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise ThreadsError(f"GitHub Secret manquant : {name}")
    return value


def api_json(method: str, path: str, *, params=None, data=None, token=None) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = requests.request(
            method, GRAPH + path, params=params, data=data, headers=headers, timeout=45,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {}
    except requests.RequestException as exc:
        raise ThreadsError(f"Requête Threads impossible ({type(exc).__name__})") from None
    if not response.ok:
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        code = error.get("code", "n/a") if isinstance(error, dict) else "n/a"
        subcode = error.get("error_subcode", "n/a") if isinstance(error, dict) else "n/a"
        # Never include URL, query parameters, response raw text or access tokens.
        raise ThreadsError(f"Threads HTTP {response.status_code}, code {code}, subcode {subcode}")
    if not isinstance(payload, dict):
        raise ThreadsError("Réponse JSON Threads invalide")
    return payload


def check_profile(token: str, *, expected: str = EXPECTED_USERNAME) -> tuple[str, str]:
    profile = api_json(
        "GET", "/v1.0/me", params={"fields": "id,username"}, token=token
    )
    user_id = str(profile.get("id") or "").strip()
    username = str(profile.get("username") or "").strip().lstrip("@")
    if not user_id or not username:
        raise ThreadsError("Identité Threads absente de /me")
    if expected and username.casefold() != expected.lstrip("@").casefold():
        raise ThreadsError(
            f"Mauvais compte Threads: @{username} au lieu de @{expected.lstrip('@')}. "
            "Aucun secret modifié."
        )
    return user_id, username


def ensure_github_writer() -> tuple[str, str]:
    pat = required("GH_PAT_SECRETS")
    repo = (os.getenv("GITHUB_REPOSITORY") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ThreadsError("GITHUB_REPOSITORY invalide")
    if shutil.which("gh") is None:
        raise ThreadsError("GitHub CLI gh introuvable sur le runner")
    return pat, repo


def store_secrets(changes: dict[str, str]) -> None:
    pat, repo = ensure_github_writer()
    env = dict(os.environ)
    env["GH_TOKEN"] = pat
    for name, value in changes.items():
        if not value:
            raise ThreadsError(f"Valeur vide pour {name}")
        command = ["gh", "secret", "set", name, "--repo", repo]
        result = subprocess.run(
            command, input=value, text=True, capture_output=True, env=env, check=False,
        )
        if result.returncode:
            # GitHub CLI stdout/stderr can include sensitive data: do not print either.
            raise ThreadsError(
                f"Échec enregistrement GitHub Secret {name} (code {result.returncode}). "
                "Vérifier que GH_PAT_SECRETS a le droit Actions secrets:write."
            )
        print(f"✅ Secret {name} mis à jour dans GitHub", flush=True)


def exchange() -> None:
    # Fail BEFORE consuming one-time OAuth code if persistence is not configured.
    ensure_github_writer()
    app_id = required("THREADS_APP_ID")  # Threads App ID, not META_APP_ID
    app_secret = required("THREADS_APP_SECRET")  # Threads App Secret
    code = required("THREADS_AUTH_CODE").removesuffix("#_")
    redirect = (os.getenv("THREADS_REDIRECT_URI") or DEFAULT_REDIRECT).strip()
    if not redirect.startswith("https://"):
        raise ThreadsError("THREADS_REDIRECT_URI doit commencer par https://")
    short = api_json(
        "POST", "/oauth/access_token",
        data={
            "client_id": app_id, "client_secret": app_secret,
            "grant_type": "authorization_code", "redirect_uri": redirect, "code": code,
        }
    )
    short_token = short.get("access_token")
    if not short_token:
        raise ThreadsError("Threads n'a pas retourné de jeton de courte durée")
    long = api_json(
        "GET", "/access_token",
        params={"grant_type": "th_exchange_token", "client_secret": app_secret,
                "access_token": short_token},
    )
    long_token = long.get("access_token")
    if not long_token:
        raise ThreadsError("Threads n'a pas retourné de jeton de longue durée")
    user_id, username = check_profile(long_token)
    store_secrets({"THREADS_USER_ID": user_id, "THREADS_ACCESS_TOKEN": long_token})
    print(f"✅ Threads reconnecté : @{username} (id {user_id})", flush=True)
    # One-time code must not remain in GitHub Secrets after successful use.
    pat, repo = ensure_github_writer()
    env = dict(os.environ, GH_TOKEN=pat)
    removed = subprocess.run(
        ["gh", "secret", "delete", "THREADS_AUTH_CODE", "--repo", repo],
        capture_output=True, text=True, env=env, check=False,
    )
    if removed.returncode:
        print("⚠️ Supprimer manuellement THREADS_AUTH_CODE (code à usage unique).")


def verify() -> None:
    token = required("THREADS_ACCESS_TOKEN")
    user_id, username = check_profile(token)
    configured_id = (os.getenv("THREADS_USER_ID") or "").strip()
    if configured_id and user_id != configured_id:
        raise ThreadsError("THREADS_USER_ID ne correspond pas au jeton; aucun post envoyé")
    print(f"✅ Threads valide : @{username} (id {user_id})", flush=True)


def refresh() -> None:
    token = required("THREADS_ACCESS_TOKEN")
    user_id, username = check_profile(token)
    # Ensure persistence is possible before rotating a valid production token.
    ensure_github_writer()
    try:
        result = api_json(
            "GET", "/refresh_access_token",
            params={"grant_type": "th_refresh_token", "access_token": token}
        )
    except ThreadsError as exc:
        # A newly-created token can only be refreshed after 24 hours.
        # Profile validation already succeeded, so it is safe to postpone.
        if "HTTP 400" in str(exc):
            print("ℹ️ Threads actif; rafraîchissement refusé (peut être trop récent). "
                  "La prochaine exécution réessaiera.", flush=True)
            return
        raise
    new_token = result.get("access_token")
    if not new_token:
        raise ThreadsError("Refresh Threads sans access_token")
    new_id, new_username = check_profile(new_token)
    if new_id != user_id:
        raise ThreadsError("Le nouveau jeton appartient à un autre compte")
    store_secrets({"THREADS_USER_ID": new_id, "THREADS_ACCESS_TOKEN": new_token})
    print(f"✅ Jeton Threads de @{new_username} renouvelé et sauvegardé", flush=True)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Connexion et maintenance Threads Mr XPRONOS")
    parser.add_argument("--action", choices=("exchange", "verify", "refresh"), required=True)
    action = parser.parse_args().action
    try:
        {"exchange": exchange, "verify": verify, "refresh": refresh}[action]()
    except ThreadsError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
