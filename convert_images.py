#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
convert_images.py - Convertit toutes les images sous assets/images/ (récursif)
au format WebP et met à jour les chemins dans les fichiers JSON.

Améliorations:
- scan récursif (assets/images/**)
- conserve les sous-dossiers (teams/, leagues/, etc.)
- skip si .webp déjà à jour
- conversion robuste (EXIF transpose)
"""

import os
import json
import glob
import logging
from pathlib import Path

from PIL import Image, ImageOps

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

IMAGE_DIR = "assets/images"
OUTPUT_FORMAT = "webp"
QUALITY = 85

JSON_FILES = ["data.json", "articles.json", "conseils.json", "footnews.json", "testimonials.json"]


def normalize_path(p: str) -> str:
    return p.replace("\\", "/")


def convert_image(filepath: str) -> str | None:
    """
    Convertit une image (png/jpg/jpeg) en webp dans le même dossier.
    Retourne le nouveau filepath (str) ou None.
    """
    try:
        src = Path(filepath)
        if not src.exists():
            return None

        # Destination = même dossier, même nom, extension .webp
        dst = src.with_suffix(f".{OUTPUT_FORMAT}")

        # Skip si dst existe et plus récent que src
        if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime and dst.stat().st_size > 200:
            return str(dst)

        img = Image.open(src)
        img = ImageOps.exif_transpose(img)

        # WEBP: gérer transparence
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")

        img.save(dst, "WEBP", quality=QUALITY, method=6)

        return str(dst)

    except Exception as e:
        logger.error(f"Erreur conversion {filepath} : {e}")
        return None


def replace_in_dict(d, old: str, new: str) -> bool:
    modified = False
    for key, value in d.items():
        if isinstance(value, str) and old in value:
            d[key] = value.replace(old, new)
            modified = True
        elif isinstance(value, dict):
            modified = replace_in_dict(value, old, new) or modified
        elif isinstance(value, list):
            modified = replace_in_list(value, old, new) or modified
    return modified


def replace_in_list(lst, old: str, new: str) -> bool:
    modified = False
    for i, item in enumerate(lst):
        if isinstance(item, str) and old in item:
            lst[i] = item.replace(old, new)
            modified = True
        elif isinstance(item, dict):
            modified = replace_in_dict(item, old, new) or modified
        elif isinstance(item, list):
            modified = replace_in_list(item, old, new) or modified
    return modified


def update_json_files(old_path: str, new_path: str):
    old = normalize_path(old_path)
    new = normalize_path(new_path)

    for json_file in JSON_FILES:
        if not os.path.exists(json_file):
            continue

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            logger.warning(f"Impossible de lire {json_file}, passage...")
            continue

        modified = False
        if isinstance(data, dict):
            modified = replace_in_dict(data, old, new) or modified
        elif isinstance(data, list):
            modified = replace_in_list(data, old, new) or modified

        if modified:
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ {json_file} mis à jour (paths remplacés)")


def main():
    if not os.path.exists(IMAGE_DIR):
        logger.error(f"Le dossier {IMAGE_DIR} n'existe pas.")
        return

    # ✅ scan récursif
    images = []
    images += glob.glob(os.path.join(IMAGE_DIR, "**", "*.png"), recursive=True)
    images += glob.glob(os.path.join(IMAGE_DIR, "**", "*.jpg"), recursive=True)
    images += glob.glob(os.path.join(IMAGE_DIR, "**", "*.jpeg"), recursive=True)

    if not images:
        logger.info("Aucune image à convertir.")
        return

    logger.info(f"{len(images)} images trouvées sous {IMAGE_DIR} (récursif).")

    converted = 0
    updated_refs = 0

    for img_path in images:
        new_path = convert_image(img_path)
        if not new_path:
            continue

        converted += 1

        # Mise à jour JSON si conversion a changé l'extension
        old_norm = normalize_path(img_path)
        new_norm = normalize_path(new_path)

        if old_norm != new_norm:
            update_json_files(old_norm, new_norm)
            updated_refs += 1

    logger.info(f"✅ Conversion terminée. Images traitées: {converted}, JSON maj: {updated_refs}")


if __name__ == "__main__":
    main()