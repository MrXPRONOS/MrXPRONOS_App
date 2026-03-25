#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
convert_images.py - Convertit récursivement assets/images/** en WebP et met à jour les JSON.

Optimisations:
- scan récursif
- exclusions (icônes PWA .png à conserver)
- conversion + mapping old->new
- mise à jour JSON en BATCH (1 lecture/écriture par fichier)
- limite conversions par run (MAX_CONVERSIONS_PER_RUN) pour éviter timeout CI
- suppression optionnelle des originaux (DELETE_ORIGINALS=true) pour réduire le repo
"""

import os
import re
import json
import glob
import logging
from pathlib import Path
from typing import Dict, List

from PIL import Image, ImageOps, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True  # évite blocage sur images tronquées

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

IMAGE_DIR = "assets/images"
OUTPUT_FORMAT = "webp"

QUALITY = int(os.getenv("WEBP_QUALITY", "85"))
METHOD = int(os.getenv("WEBP_METHOD", "4"))  # 0..6 (4 = bon compromis vitesse/qualité)
DELETE_ORIGINALS = os.getenv("DELETE_ORIGINALS", "false").lower() in ("1", "true", "yes")
MAX_CONVERSIONS_PER_RUN = int(os.getenv("MAX_CONVERSIONS_PER_RUN", "0"))  # 0 = illimité

JSON_FILES = ["data.json", "articles.json", "conseils.json", "footnews.json", "testimonials.json"]

# Icônes PWA / fichiers à ne PAS convertir (manifest + service worker + navigateur)
EXCLUDE_PATTERNS = [
    r"assets/images/icon-\d+x\d+\.png$",   # icon-192x192.png etc
    r"assets/images/icon-\d+\.png$",       # icon-192.png si jamais
    r"assets/images/favicon\.png$",        # si présent
]

EXCLUDE_REGEX = re.compile("|".join(EXCLUDE_PATTERNS), re.IGNORECASE)


def norm(p: str) -> str:
    return p.replace("\\", "/")


def is_excluded(path: str) -> bool:
    return EXCLUDE_REGEX.search(norm(path)) is not None


def convert_image(src_path: str) -> str | None:
    """
    Convertit un fichier png/jpg/jpeg en webp dans le même dossier.
    Retourne le chemin du .webp ou None.
    """
    src = Path(src_path)
    if not src.exists():
        return None

    dst = src.with_suffix(f".{OUTPUT_FORMAT}")

    # Si déjà converti, on skip (on ne se base pas uniquement sur mtime à cause des checkouts git)
    if dst.exists() and dst.stat().st_size > 200:
        return str(dst)

    try:
        img = Image.open(src)
        img = ImageOps.exif_transpose(img)

        # transparence
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")

        img.save(dst, "WEBP", quality=QUALITY, method=METHOD)
        return str(dst)

    except Exception as e:
        logger.error(f"Erreur conversion {src_path}: {e}")
        return None


def replace_in_obj(obj, mapping: Dict[str, str]) -> bool:
    """
    Remplace les chemins dans un objet JSON (dict/list/str) selon mapping.
    Retourne True si modifié.
    """
    modified = False

    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                modified = replace_in_obj(v, mapping) or modified
            elif isinstance(v, str):
                nv = v
                for old, new in mapping.items():
                    if old in nv:
                        nv = nv.replace(old, new)
                if nv != v:
                    obj[k] = nv
                    modified = True

    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, (dict, list)):
                modified = replace_in_obj(v, mapping) or modified
            elif isinstance(v, str):
                nv = v
                for old, new in mapping.items():
                    if old in nv:
                        nv = nv.replace(old, new)
                if nv != v:
                    obj[i] = nv
                    modified = True

    return modified


def update_json_files(mapping: Dict[str, str]):
    if not mapping:
        return

    for jf in JSON_FILES:
        if not os.path.exists(jf):
            continue

        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            logger.warning(f"Impossible de lire {jf}, ignoré.")
            continue

        modified = replace_in_obj(data, mapping)

        if modified:
            with open(jf, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ {jf} mis à jour (batch)")

    logger.info("✅ Mise à jour JSON terminée (batch).")


def main():
    if not os.path.exists(IMAGE_DIR):
        logger.error(f"Le dossier {IMAGE_DIR} n'existe pas.")
        return

    # scan récursif
    images: List[str] = []
    images += glob.glob(os.path.join(IMAGE_DIR, "**", "*.png"), recursive=True)
    images += glob.glob(os.path.join(IMAGE_DIR, "**", "*.jpg"), recursive=True)
    images += glob.glob(os.path.join(IMAGE_DIR, "**", "*.jpeg"), recursive=True)

    # exclusions
    images = [p for p in images if not is_excluded(p)]

    if not images:
        logger.info("Aucune image à convertir.")
        return

    logger.info(f"{len(images)} images trouvées sous {IMAGE_DIR} (récursif).")

    mapping: Dict[str, str] = {}
    converted = 0
    skipped = 0

    for idx, src in enumerate(images, 1):
        if MAX_CONVERSIONS_PER_RUN and converted >= MAX_CONVERSIONS_PER_RUN:
            logger.info(f"⏹️ Limite atteinte: {MAX_CONVERSIONS_PER_RUN} conversions (stop).")
            break

        dst = Path(src).with_suffix(".webp")
        if dst.exists() and dst.stat().st_size > 200:
            skipped += 1
            continue

        new_path = convert_image(src)
        if not new_path:
            continue

        converted += 1
        old_norm = norm(src)
        new_norm = norm(new_path)

        # mapping pour JSON
        mapping[old_norm] = new_norm

        if converted % 100 == 0:
            logger.info(f"…progress: {converted} converties (sur {idx}/{len(images)} analysées)")

        # suppression optionnelle de l'original (réduit taille repo et accélère les runs suivants)
        if DELETE_ORIGINALS:
            try:
                os.remove(src)
            except Exception:
                pass

    logger.info(f"✅ Conversion terminée. converties={converted}, déjà_ok={skipped}")

    # MAJ JSON une seule fois (batch)
    update_json_files(mapping)


if __name__ == "__main__":
    main()