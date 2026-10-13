#!/usr/bin/env python3
"""Install the 10 ORIGINAL Arty PNG designs from the archived ZIP.

Usage:
 python scripts/install_arty_originals.py "Arty_Football_10_Templates_Premium_Originaux.zip"
 python scripts/install_arty_originals.py "Arty_Football_10_Templates_Premium_Originaux.zip" --dry-run

This is an OFFLINE import. It never creates/changes the underlying artwork,
and never overwrites the 12 existing procedural fallbacks.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "assets" / "images" / "arty_football" / "originals"
BY_NUMBER = {
    1: "composition",
    2: "kickoff",
    3: "goal",
    4: "mi_temps",
    5: "score_update",
    6: "statistique_avancee",
    7: "community_vote",
    8: "quiz",
    9: "debat",
    10: "reaction",
}
ALIASES = {
    "composition": "composition",
    "coup_envoi": "kickoff",
    "kickoff": "kickoff",
    "buuuut": "goal",
    "but": "goal",
    "goal": "goal",
    "mi_temps": "mi_temps",
    "score_live": "score_update",
    "score_update": "score_update",
    "statistique": "statistique_avancee",
    "vote": "community_vote",
    "community_vote": "community_vote",
    "quiz": "quiz",
    "debat": "debat",
    "reaction": "reaction",
}


def identify(name: str) -> str | None:
    stem = Path(name).stem.lower()
    numeric = re.search(r"image[-_ ]?gen[-_ ]?([1-9]|10)(?!\d)", stem)
    if numeric:
        return BY_NUMBER.get(int(numeric.group(1)))
    normalized = re.sub(r"[^a-z0-9]+", "_", stem)
    for alias in sorted(ALIASES, key=len, reverse=True):
        if alias in normalized:
            return ALIASES[alias]
    leading_number = re.match(r"^(?:template_)?0?(\d{1,2})(?:_|$)", normalized)
    if leading_number:
        return BY_NUMBER.get(int(leading_number.group(1)))
    return None


def import_archive(archive: Path, output: Path, dry_run: bool = False):
    if not archive.is_file():
        raise FileNotFoundError(f"Archive introuvable: {archive}")
    chosen: dict[str, tuple[str, bytes]] = {}
    with zipfile.ZipFile(archive) as zip_ref:
        for item in zip_ref.infolist():
            if item.is_dir() or not item.filename.lower().endswith(".png"):
                continue
            if item.file_size > 10 * 1024 * 1024:
                raise ValueError(f"Image supérieure à 10 Mo: {item.filename}")
            category = identify(item.filename)
            if category is None:
                continue
            if category in chosen:
                raise ValueError(f"Doublon pour {category}: {item.filename}")
            data = zip_ref.read(item)
            with Image.open(io.BytesIO(data)) as source:
                if source.format != "PNG" or source.width < 900 or source.height < 1100:
                    raise ValueError(f"PNG original invalide: {item.filename}")
                ratio = source.width / source.height
                if not 0.76 <= ratio <= 0.84:
                    raise ValueError(f"Format portrait inattendu: {item.filename}")
                source.verify()
            chosen[category] = (item.filename, data)

    missing = [category for category in BY_NUMBER.values() if category not in chosen]
    if missing:
        raise ValueError("Archive incomplète, formats manquants: " + ", ".join(missing))

    for category in BY_NUMBER.values():
        name, data = chosen[category]
        print(f"{name} -> {output / (category + '.png')} ({len(data)} octets)")

    if dry_run:
        print("DRY RUN: aucune écriture")
        return chosen

    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="arty-import-") as work:
        workdir = Path(work)
        for category, (_, data) in chosen.items():
            temp_png = workdir / (category + ".png")
            temp_png.write_bytes(data)
        # Verify every image before touching final assets. Keep existing originals
        # untouched in case any input is corrupt.
        for category in chosen:
            with Image.open(workdir / (category + ".png")) as image:
                image.verify()
        for category in chosen:
            shutil.copy2(workdir / (category + ".png"), output / (category + ".png"))
    print(f"OK: {len(chosen)} originaux Arty installés dans {output}")
    return chosen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_path", type=Path, help="Archive PNG originale")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    import_archive(args.zip_path, args.out, args.dry_run)


if __name__ == "__main__":
    main()
