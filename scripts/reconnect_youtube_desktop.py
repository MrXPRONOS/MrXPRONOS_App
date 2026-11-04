#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconnect Mr XPRONOS YouTube with a Google OAuth Desktop client.

Runs ONLY on the user's own computer. Never upload OAuth JSON or refresh tokens
to GitHub or chat. The output file is saved in the user's HOME, outside the repo.

Usage:
  py -m pip install google-auth-oauthlib google-auth
  py scripts/reconnect_youtube_desktop.py --client-json "C:\\Users\\YOU\\Downloads\\client_secret_XXXX.json"

You can omit --client-json if exactly one client_secret_*.json is in Downloads.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"


def locate_credentials(raw_path: str | None) -> Path:
    if raw_path:
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Fichier OAuth introuvable: {path}")
        return path
    downloads = Path.home() / "Downloads"
    candidates = sorted(downloads.glob("client_secret_*.json"))
    if len(candidates) != 1:
        raise ValueError(
            "Indique le fichier Google JSON avec --client-json. "
            f"Trouves dans Downloads: {len(candidates)} fichiers client_secret_*.json"
        )
    return candidates[0]


def write_private_file(content: dict) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = Path.home() / f"youtube_mrxpronos_secrets_{stamp}.json"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    with os.fdopen(os.open(output, flags, 0o600), "w", encoding="utf-8") as stream:
        json.dump(content, stream, indent=2)
        stream.write("\n")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconnecter YouTube Mr XPRONOS (OAuth Desktop)")
    parser.add_argument("--client-json", help="Chemin vers le JSON OAuth Application de bureau")
    args = parser.parse_args()
    credentials_path = locate_credentials(args.client_json)

    raw = json.loads(credentials_path.read_text(encoding="utf-8"))
    config = raw.get("installed")
    if not isinstance(config, dict) or not config.get("client_id") or not config.get("client_secret"):
        raise ValueError(
            "Ce JSON n'est pas un client OAuth Application de bureau avec ID et secret. "
            "Dans Google Cloud, telecharge les informations d'identification du client Desktop."
        )

    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    print("Connexion au compte Google de la chaine YouTube Mr XPRONOS...")
    print("Le navigateur va s'ouvrir. Autorise l'importation de videos YouTube.")
    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_path), scopes=[UPLOAD_SCOPE]
    )
    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        open_browser=True,
        authorization_prompt_message="Ouvre cette URL si le navigateur ne s'ouvre pas: {url}",
        success_message="Autorisation recue. Tu peux fermer cet onglet.",
        access_type="offline",
        prompt="consent",
    )
    refresh_token = credentials.refresh_token
    if not refresh_token:
        raise RuntimeError("Google n'a pas remis de refresh token. Verifie acces offline et prompt consent.")

    # Verify the new refresh token before asking the user to store it in GitHub.
    probe = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        scopes=[UPLOAD_SCOPE],
    )
    probe.refresh(Request())
    if not probe.valid:
        raise RuntimeError("Le refresh token a ete recu mais son renouvellement a echoue.")

    output = write_private_file({
        "YOUTUBE_CLIENT_ID": config["client_id"],
        "YOUTUBE_CLIENT_SECRET": config["client_secret"],
        "YOUTUBE_REFRESH_TOKEN": refresh_token,
    })
    print("\nSUCCES : OAuth YouTube reconnecte, nouveau refresh token verifie.")
    print(f"Fichier PRIVE cree dans ton dossier utilisateur: {output}")
    print("Ouvre le fichier LOCAL et copie les trois valeurs dans GitHub > Settings >")
    print("Secrets and variables > Actions > Repository secrets.")
    print("Ne partage PAS le fichier ou son contenu. Ne le commite jamais dans GitHub.")
    print("Supprime ce fichier prive et le JSON Google telecharge apres avoir mis a jour les secrets.")
    print("Teste ensuite le workflow 'YouTube OAuth - Safe Credential Check'.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print("ERREUR:", str(exc), file=sys.stderr)
        raise SystemExit(1)
