#!/usr/bin/env python3
"""Archive BSD : JSON local lisible + copie chiffree versionnee dans GitHub.

Le depot public ne doit JAMAIS contenir les resultats historiques BSD en clair.
Usage Actions: restore -> backfill -> seal -> git commit de la seule archive chiffree.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

ROOT = Path("bsd")
MATCHES_FILE = ROOT / "all_matches_bsd.json"
STATE_FILE = ROOT / "backfill_state.json"
ENCRYPTED_FILE = ROOT / "all_matches_bsd.enc.json"
SCHEMA = "bsd-json-archive-v1"


def cipher() -> Fernet:
    secret = (os.getenv("BSD_HISTORY_KEY") or "").strip()
    if not secret:
        raise ValueError("Secret GitHub BSD_HISTORY_KEY manquant.")
    try:
        return Fernet(secret.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise ValueError("BSD_HISTORY_KEY invalide : cle Fernet base64 requise.") from exc


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def _read_json(path: Path, fallback: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback


def initial_state() -> dict:
    return {
        "version": 1,
        "provider": "BSD",
        "year_from": 2016,
        "year_to": 2024,
        "league_ids": [],
        "discovery_index": 0,
        "catalog_complete": False,
        "season_tasks": [],
        "completed_seasons": [],
        "invalid_seasons": [],
    }


def restore() -> None:
    key = cipher()
    if not ENCRYPTED_FILE.exists():
        # Première execution: l'archive sera creee apres un backfill reussi.
        if MATCHES_FILE.exists() or STATE_FILE.exists():
            raise ValueError("Etat local non chiffre deja present sans archive d'origine.")
        _write_json(MATCHES_FILE, [])
        _write_json(STATE_FILE, initial_state())
        print("BSD_ARCHIVE: nouvelle base locale 2016-2024")
        return

    envelope = _read_json(ENCRYPTED_FILE, {})
    if not isinstance(envelope, dict) or envelope.get("format") != SCHEMA:
        raise ValueError("Archive BSD chiffree : format inattendu.")
    try:
        compressed = key.decrypt(envelope["encrypted"].encode("ascii"))
        contents = json.loads(gzip.decompress(compressed).decode("utf-8"))
    except (InvalidToken, KeyError, TypeError, OSError, ValueError) as exc:
        raise ValueError("Archive BSD indechiffrable ou corrompue : verifier BSD_HISTORY_KEY.") from exc
    if contents.get("provider") != "BSD" or not isinstance(contents.get("matches"), list):
        raise ValueError("Archive BSD : liste matches absente.")
    state = contents.get("state")
    if not isinstance(state, dict) or state.get("provider") != "BSD":
        raise ValueError("Archive BSD : etat de reprise absent.")
    _write_json(MATCHES_FILE, contents["matches"])
    _write_json(STATE_FILE, state)
    print("BSD_ARCHIVE: historique restaure (%d matchs)" % len(contents["matches"]))


def seal() -> None:
    key = cipher()
    matches = _read_json(MATCHES_FILE, None)
    state = _read_json(STATE_FILE, None)
    if not isinstance(matches, list) or not isinstance(state, dict):
        raise ValueError("Fichiers JSON locaux manquants ou invalides.")
    if state.get("provider") != "BSD" or state.get("year_from") != 2016 or state.get("year_to") != 2024:
        raise ValueError("Intervalle BSD inattendu, refus de sceller.")
    ids = [str(m.get("id")) for m in matches if isinstance(m, dict) and m.get("id") is not None]
    if len(ids) != len(matches) or len(ids) != len(set(ids)):
        raise ValueError("Historique BSD : ID manquants ou doublons.")
    contents = {"provider": "BSD", "matches": matches, "state": state}
    plain = json.dumps(contents, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    token = key.encrypt(gzip.compress(plain, compresslevel=6, mtime=0)).decode("ascii")
    _write_json(ENCRYPTED_FILE, {"format": SCHEMA, "encrypted": token})
    print("BSD_ARCHIVE: %d matchs sauvegardes en JSON chiffre." % len(matches))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["restore", "seal"])
    action = parser.parse_args().action
    if action == "restore":
        restore()
    else:
        seal()


if __name__ == "__main__":
    main()
