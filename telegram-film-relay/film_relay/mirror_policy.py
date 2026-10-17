"""Politique centralisée de suspension de TOUS les transferts vers Torrent9.

On ne change aucun reçu ni l'historique ; la pause est sans rattrapage auto.
Toute erreur de lecture du fichier bloque les transferts (fail closed).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

POLICY = Path(__file__).resolve().parents[1] / "config" / "torrent9_policy.json"


def torrent9_paused() -> bool:
    if os.getenv("CINEX_TORRENT9_PAUSED", "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    try:
        cfg = json.loads(POLICY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    return cfg.get("transfers_enabled") is not True


def assert_torrent9_enabled() -> None:
    if torrent9_paused():
        raise RuntimeError("Transferts Torrent9 temporairement suspendus à la demande du propriétaire.")
