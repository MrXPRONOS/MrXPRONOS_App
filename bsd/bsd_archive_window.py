#!/usr/bin/env python3
"""Nettoie la fenêtre BSD par date réelle sans toucher aux anciennes données SportData."""
from __future__ import annotations
from datetime import date
from bsd_archive import MATCHES_FILE, _read_json, _write_json


def keep_window(matches, start_year=2024, end_year=2026):
    if not isinstance(matches, list):
        raise ValueError("Historique BSD doit être une liste JSON")
    kept = []
    removed = 0
    invalid = 0
    for m in matches:
        if not isinstance(m, dict) or m.get("id") is None:
            invalid += 1
            continue
        value = str(m.get("event_date") or "")[:10]
        try:
            d = date.fromisoformat(value)
        except ValueError:
            invalid += 1
            continue
        if start_year <= d.year <= end_year:
            kept.append(m)
        else:
            removed += 1
    return kept, removed, invalid


def main():
    matches = _read_json(MATCHES_FILE, None)
    if not isinstance(matches, list) or not matches:
        raise ValueError("Historique BSD absent ou vide, aucune modification")
    kept, removed, invalid = keep_window(matches)
    if not kept or len(kept) < len(matches) * 0.90:
        raise ValueError("Nettoyage refuse : plus de 10% des matchs seraient perdus")
    ids = [str(m["id"]) for m in kept]
    if len(ids) != len(set(ids)):
        raise ValueError("Doublons dans le JSON nettoyé")
    if removed or invalid:
        _write_json(MATCHES_FILE, kept)
    print("BSD_WINDOW_2024_2026: total=%d retained=%d outside_window=%d invalid=%d" %
          (len(matches), len(kept), removed, invalid))


if __name__ == "__main__":
    main()
