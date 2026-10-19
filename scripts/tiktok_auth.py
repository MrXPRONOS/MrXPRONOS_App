#!/usr/bin/env python3
"""Safe TikTok Login Kit: exchange, verify and refresh user tokens, no publishing.

No client secrets or tokens are written to console, repository, or workflow outputs.
"""
from __future__ import annotations
import argparse
import os
import re
import shutil
import subprocess
import sys
import requests

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
USER_URL = "https://open.tiktokapis.com/v2/user/info/"
CREATOR_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
REDIRECT_URI = "https://mrxpronos.github.io/MrXPRONOS_App/tiktok-callback.html"


class TikTokError(RuntimeError):
    pass


def required(key: str) -> str:
    val = (os.getenv(key) or "").strip()
    if not val:
        raise TikTokError(f"GitHub Secret manquant : {key}")
    return val


def api_json(resp) -> dict:
    try:
        data = resp.json()
    except ValueError:
        raise TikTokError(f"TikTok a renvoyé un JSON invalide (HTTP {resp.status_code})") from None
    error = data.get("error")
    if isinstance(error, dict):
        code = str(error.get("code") or "ok")
    else:
        code = str(error or "ok")
    if resp.status_code >= 400 or code not in ("ok", "0"):
        # Never echo the raw error description: it may contain tokens or codes.
        raise TikTokError(f"TikTok HTTP {resp.status_code}, code={code[:80]}")
    return data


def token_request(data: dict) -> dict:
    try:
        response = requests.post(TOKEN_URL,
             headers={"Content-Type": "application/x-www-form-urlencoded"},
             data=data, timeout=40)
    except requests.RequestException as exc:
        raise TikTokError("TikTok OAuth inaccessible: " + type(exc).__name__) from None
    return api_json(response)


def user_info(token: str) -> tuple[str, str]:
    try:
        response = requests.get(USER_URL,
            params={"fields": "open_id,display_name"},
            headers={"Authorization": "Bearer " + token}, timeout=35)
    except requests.RequestException as exc:
        raise TikTokError("TikTok profile inaccessible: " + type(exc).__name__) from None
    info = api_json(response).get("data") or {}
    user = info.get("user") or {}
    oid = str(user.get("open_id") or "")
    name = str(user.get("display_name") or "")
    if not oid:
        raise TikTokError("TikTok /user/info sans open_id")
    expected = (os.getenv("TIKTOK_EXPECTED_OPEN_ID") or "").strip()
    if expected and expected != oid:
        raise TikTokError("Un autre compte TikTok a autorisé l'application. Aucun secret enregistré.")
    return oid, name


def github_writer() -> tuple[str, str]:
    pat = required("GH_PAT_SECRETS")
    repo = (os.getenv("GITHUB_REPOSITORY") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise TikTokError("GITHUB_REPOSITORY invalide")
    if not shutil.which("gh"):
        raise TikTokError("GitHub CLI absent")
    return pat, repo


def store(changes: dict[str, str]) -> None:
    pat, repo = github_writer()
    env = dict(os.environ, GH_TOKEN=pat)
    for key, value in changes.items():
        if not value:
            raise TikTokError(f"Valeur vide: {key}")
        p = subprocess.run(["gh", "secret", "set", key, "--repo", repo],
                           input=value, text=True, capture_output=True, env=env,
                           check=False)
        if p.returncode:
            raise TikTokError(
                f"Impossible d'écrire le secret {key}, code {p.returncode}. "
                "Vérifier GH_PAT_SECRETS (Actions secrets write).")
        print("✅ GitHub Secret sauvegardé : " + key, flush=True)


def check_publishing_permission(token: str) -> None:
    try:
        r = requests.post(CREATOR_URL,
             headers={"Authorization": "Bearer " + token,
                      "Content-Type": "application/json"},
             json={}, timeout=40)
    except requests.RequestException as exc:
        raise TikTokError("TikTok creator_info inaccessible: "+type(exc).__name__) from None
    obj = api_json(r)
    profile = obj.get("data") or {}
    options = profile.get("privacy_level_options") or []
    print("✅ video.publish accordé: creator_info accessible. "
          "Options de confidentialité: " + ",".join(options),
          flush=True)
    print("ℹ️ Ceci ne confirme pas l'audit TikTok ni le droit à la publication publique.", flush=True)


def exchange() -> None:
    # Check GitHub write capability before consuming the single-use OAuth code.
    github_writer()
    ck = required("TIKTOK_CLIENT_KEY")
    secret = required("TIKTOK_CLIENT_SECRET")
    code = required("TIKTOK_AUTH_CODE")
    redirect = (os.getenv("TIKTOK_REDIRECT_URI") or REDIRECT_URI).strip()
    if redirect != REDIRECT_URI:
        raise TikTokError("TIKTOK_REDIRECT_URI inattendue; configurer l'adresse GitHub Pages officielle")
    data = token_request({"client_key": ck, "client_secret": secret,
                          "code": code, "grant_type": "authorization_code",
                          "redirect_uri": redirect})
    access = data.get("access_token")
    refresh = data.get("refresh_token")
    granted = set(str(data.get("scope") or "").split(","))
    if not access or not refresh or "user.info.basic" not in granted:
        raise TikTokError("Token incomplet ou scope user.info.basic non accordé")
    oid, nickname = user_info(access)
    if str(data.get("open_id") or "") != oid:
        raise TikTokError("open_id du token ne correspond pas au profil")
    store({"TIKTOK_OPEN_ID": oid, "TIKTOK_ACCESS_TOKEN": access,
           "TIKTOK_REFRESH_TOKEN": refresh})
    print(f"✅ TikTok connecté : {nickname} ; autorisations : "
          + ", ".join(sorted(granted)), flush=True)
    pat, repo = github_writer()
    deleted = subprocess.run(["gh", "secret", "delete", "TIKTOK_AUTH_CODE",
                              "--repo", repo],capture_output=True,text=True,
                             env=dict(os.environ, GH_TOKEN=pat))
    if deleted.returncode:
        print("⚠️ Supprimer TIKTOK_AUTH_CODE manuellement : code à usage unique.",flush=True)


def verify() -> None:
    access = required("TIKTOK_ACCESS_TOKEN")
    oid, nickname = user_info(access)
    saved = (os.getenv("TIKTOK_OPEN_ID") or "").strip()
    if saved and saved != oid:
        raise TikTokError("TIKTOK_OPEN_ID ne correspond pas au token.")
    print("✅ TikTok token et profil valides pour " + nickname,flush=True)
    if os.getenv("TIKTOK_VERIFY_PUBLISH_SCOPE") == "true":
        check_publishing_permission(access)


def refresh() -> None:
    github_writer()
    ck = required("TIKTOK_CLIENT_KEY")
    secret = required("TIKTOK_CLIENT_SECRET")
    old = required("TIKTOK_REFRESH_TOKEN")
    response = token_request({
        "client_key": ck, "client_secret": secret,
        "grant_type": "refresh_token", "refresh_token": old,
    })
    access = str(response.get("access_token") or "")
    new_refresh = str(response.get("refresh_token") or "")
    if not access or not new_refresh:
        raise TikTokError("TikTok n'a pas retourné un access_token et refresh_token")
    oid, nickname = user_info(access)
    old_id = (os.getenv("TIKTOK_OPEN_ID") or "").strip()
    if old_id and old_id != oid:
        raise TikTokError("Le token rafraîchi appartient à un autre utilisateur.")
    if response.get("open_id") and str(response["open_id"]) != oid:
        raise TikTokError("open_id inattendu pendant le renouvellement.")
    store({"TIKTOK_OPEN_ID": oid, "TIKTOK_ACCESS_TOKEN": access,
           "TIKTOK_REFRESH_TOKEN": new_refresh})
    print("✅ TikTok token actualisé et persistant pour " + nickname, flush=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--action",choices=("exchange","verify","refresh"),required=True)
    args=p.parse_args()
    try:
        {"exchange": exchange,"verify":verify,"refresh":refresh}[args.action]()
        return 0
    except TikTokError as e:
        print("::error::"+str(e),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
