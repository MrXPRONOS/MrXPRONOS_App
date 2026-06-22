#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
refresh_social_tokens.py - Mr XPRONOS

But : éviter le renouvellement manuel des tokens.
Le script rafraîchit les tokens possibles puis écrit :
- refreshed_tokens.json pour mise à jour GitHub Secrets
- optionnellement $GITHUB_ENV pour utiliser les nouveaux tokens dans le même workflow

Plateformes :
- Facebook / Instagram : échange META_LONG_LIVED_USER_TOKEN puis récupère Page Access Token + IG_USER_ID
- Threads : rafraîchit un long-lived token via graph.threads.net/refresh_access_token
- TikTok : rafraîchit TIKTOK_ACCESS_TOKEN avec TIKTOK_REFRESH_TOKEN

Important :
- Les tokens déjà expirés ne peuvent généralement pas être rafraîchis. Il faut les recréer une fois.
- Ne jamais afficher les tokens en clair dans les logs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests

GRAPH_VERSION = os.getenv("GRAPH_API_VERSION", "v25.0")


def log(msg: str) -> None:
    print(msg, flush=True)


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name, default)
    if v is None:
        return None
    v = str(v).strip()
    return v or default


def mask(value: Optional[str]) -> None:
    if value:
        print(f"::add-mask::{value}", flush=True)


def request_json(method: str, url: str, *, params=None, data=None, headers=None, timeout: int = 60) -> Dict[str, Any]:
    r = requests.request(method, url, params=params, data=data, headers=headers, timeout=timeout)
    try:
        payload = r.json()
    except Exception:
        payload = {"raw": r.text[:1000]}
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code} sur {url}: {payload}")
    return payload


@dataclass
class RefreshSummary:
    platform: str
    ok: bool
    message: str


def refresh_meta() -> tuple[Dict[str, str], RefreshSummary]:
    """Rafraîchit Facebook/Instagram à partir d'un long-lived user token Meta."""
    app_id = env("META_APP_ID")
    app_secret = env("META_APP_SECRET")
    user_token = env("META_LONG_LIVED_USER_TOKEN")
    page_id_target = env("META_PAGE_ID")
    page_name_target = (env("META_PAGE_NAME") or "").lower()

    if not (app_id and app_secret and user_token):
        return {}, RefreshSummary(
            "meta",
            False,
            "Ignoré: META_APP_ID, META_APP_SECRET ou META_LONG_LIVED_USER_TOKEN manquant.",
        )

    out: Dict[str, str] = {}

    # 1) Tenter de prolonger le user token Meta.
    try:
        data = request_json(
            "GET",
            f"https://graph.facebook.com/{GRAPH_VERSION}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": user_token,
            },
        )
        new_user_token = data.get("access_token") or user_token
        if new_user_token:
            mask(new_user_token)
            out["META_LONG_LIVED_USER_TOKEN"] = new_user_token
            user_token = new_user_token
    except Exception as e:
        # On continue avec le token actuel si encore valide.
        log(f"⚠️ Meta user token non prolongé, tentative avec le token existant: {e}")

    # 2) Récupérer le Page token + Instagram business account.
    accounts = request_json(
        "GET",
        f"https://graph.facebook.com/{GRAPH_VERSION}/me/accounts",
        params={
            "fields": "id,name,access_token,instagram_business_account{id,username}",
            "access_token": user_token,
        },
    )

    pages = accounts.get("data") or []
    selected = None
    for page in pages:
        if page_id_target and str(page.get("id")) == str(page_id_target):
            selected = page
            break
        if page_name_target and str(page.get("name", "")).lower() == page_name_target:
            selected = page
            break
    if not selected and pages:
        selected = pages[0]

    if not selected:
        return out, RefreshSummary("meta", False, "Aucune Page trouvée avec ce token Meta.")

    page_token = selected.get("access_token")
    if page_token:
        mask(page_token)
        out["META_PAGE_ACCESS_TOKEN"] = page_token
        # Ton script utilise META_ACCESS_TOKEN pour Instagram.
        out["META_ACCESS_TOKEN"] = page_token

    page_id = selected.get("id")
    if page_id:
        out["META_PAGE_ID"] = str(page_id)

    ig = selected.get("instagram_business_account") or {}
    ig_id = ig.get("id")
    if ig_id:
        out["IG_USER_ID"] = str(ig_id)

    return out, RefreshSummary(
        "meta",
        True,
        f"OK: Page={selected.get('name')} PageID={selected.get('id')} IG={ig.get('username') or ig_id or 'non lié'}",
    )


def refresh_threads() -> tuple[Dict[str, str], RefreshSummary]:
    token = env("THREADS_ACCESS_TOKEN")
    if not token:
        return {}, RefreshSummary("threads", False, "Ignoré: THREADS_ACCESS_TOKEN manquant.")

    out: Dict[str, str] = {}

    # Rafraîchissement d'un long-lived token Threads non expiré.
    try:
        data = request_json(
            "GET",
            "https://graph.threads.net/refresh_access_token",
            params={"grant_type": "th_refresh_token", "access_token": token},
        )
        new_token = data.get("access_token")
        if not new_token:
            return {}, RefreshSummary("threads", False, f"Réponse sans access_token: {data}")
        mask(new_token)
        out["THREADS_ACCESS_TOKEN"] = new_token
        return out, RefreshSummary("threads", True, f"OK: token Threads rafraîchi, expires_in={data.get('expires_in')}")
    except Exception as refresh_error:
        # Si le token actuel est short-lived, tenter l'échange en long-lived si app secret disponible.
        app_secret = env("THREADS_APP_SECRET")
        if not app_secret:
            return {}, RefreshSummary("threads", False, f"Échec refresh Threads et THREADS_APP_SECRET manquant: {refresh_error}")
        try:
            data = request_json(
                "GET",
                "https://graph.threads.net/access_token",
                params={
                    "grant_type": "th_exchange_token",
                    "client_secret": app_secret,
                    "access_token": token,
                },
            )
            new_token = data.get("access_token")
            if not new_token:
                return {}, RefreshSummary("threads", False, f"Réponse sans access_token: {data}")
            mask(new_token)
            out["THREADS_ACCESS_TOKEN"] = new_token
            return out, RefreshSummary("threads", True, f"OK: token Threads converti/prolongé, expires_in={data.get('expires_in')}")
        except Exception as exchange_error:
            return {}, RefreshSummary(
                "threads",
                False,
                f"Échec refresh Threads: {refresh_error} | Échec exchange: {exchange_error}",
            )


def refresh_tiktok() -> tuple[Dict[str, str], RefreshSummary]:
    client_key = env("TIKTOK_CLIENT_KEY")
    client_secret = env("TIKTOK_CLIENT_SECRET")
    refresh_token = env("TIKTOK_REFRESH_TOKEN")
    if not (client_key and client_secret and refresh_token):
        return {}, RefreshSummary(
            "tiktok",
            False,
            "Ignoré: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET ou TIKTOK_REFRESH_TOKEN manquant.",
        )

    data = request_json(
        "POST",
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )

    access_token = data.get("access_token")
    new_refresh_token = data.get("refresh_token") or refresh_token
    if not access_token:
        return {}, RefreshSummary("tiktok", False, f"Réponse sans access_token: {data}")

    mask(access_token)
    mask(new_refresh_token)
    return {
        "TIKTOK_ACCESS_TOKEN": access_token,
        "TIKTOK_REFRESH_TOKEN": new_refresh_token,
    }, RefreshSummary(
        "tiktok",
        True,
        f"OK: token TikTok rafraîchi, access_expires_in={data.get('expires_in')}, refresh_expires_in={data.get('refresh_expires_in')}",
    )


def write_github_env(path: str, tokens: Dict[str, str]) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        for key, value in tokens.items():
            if not value:
                continue
            # Format multi-ligne sûr.
            f.write(f"{key}<<MRXEOF\n{value}\nMRXEOF\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rafraîchir les tokens sociaux Mr XPRONOS")
    parser.add_argument("--out", default="refreshed_tokens.json", help="Fichier JSON de sortie")
    parser.add_argument("--github-env", default=os.getenv("GITHUB_ENV"), help="Chemin GITHUB_ENV pour réutiliser les tokens dans le même workflow")
    args = parser.parse_args()

    all_tokens: Dict[str, str] = {}
    summaries: list[RefreshSummary] = []

    for fn in (refresh_meta, refresh_threads, refresh_tiktok):
        try:
            tokens, summary = fn()
            all_tokens.update({k: v for k, v in tokens.items() if v})
            summaries.append(summary)
        except Exception as e:
            name = fn.__name__.replace("refresh_", "")
            summaries.append(RefreshSummary(name, False, f"Exception: {e}"))

    Path(args.out).write_text(json.dumps(all_tokens, ensure_ascii=False, indent=2), encoding="utf-8")
    write_github_env(args.github_env or "", all_tokens)

    log("=" * 70)
    log("🔐 Résumé refresh tokens")
    for s in summaries:
        icon = "✅" if s.ok else "⚠️"
        log(f"{icon} {s.platform.upper()} : {s.message}")
    log(f"🧾 Tokens rafraîchis écrits dans: {args.out}")
    log("⚠️ Les valeurs ne sont pas affichées dans les logs.")
    log("=" * 70)

    # Ne pas faire échouer tout le workflow si une plateforme n'est pas encore configurée.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
