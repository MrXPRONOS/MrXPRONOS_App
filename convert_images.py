#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
convert_images.py - Convertit toutes les images du dossier assets/images/
au format WebP et met à jour les chemins dans les fichiers JSON.
Utilise Pillow pour la conversion.
"""

import os
import json
import glob
from PIL import Image

IMAGE_DIR = "assets/images"
OUTPUT_FORMAT = "webp"
QUALITY = 85

JSON_FILES = ["data.json", "articles.json", "conseils.json", "footnews.json"]

def convert_image(filepath):
    try:
        img = Image.open(filepath)
        basename = os.path.splitext(os.path.basename(filepath))[0]
        new_filename = f"{basename}.{OUTPUT_FORMAT}"
        new_filepath = os.path.join(IMAGE_DIR, new_filename)
        img.save(new_filepath, OUTPUT_FORMAT.upper(), quality=QUALITY)
        return new_filepath
    except Exception as e:
        print(f"❌ Erreur lors de la conversion de {filepath} : {e}")
        return None

def update_json_files(old_path, new_path):
    old = old_path.replace("\\", "/")
    new = new_path.replace("\\", "/")
    for json_file in JSON_FILES:
        if not os.path.exists(json_file):
            continue
        with open(json_file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except:
                print(f"⚠️ Impossible de lire {json_file}, passage...")
                continue
        modified = False
        if isinstance(data, dict):
            modified = replace_in_dict(data, old, new) or modified
        elif isinstance(data, list):
            modified = replace_in_list(data, old, new) or modified
        if modified:
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✅ {json_file} mis à jour")

def replace_in_dict(d, old, new):
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

def replace_in_list(lst, old, new):
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

def main():
    if not os.path.exists(IMAGE_DIR):
        print(f"❌ Le dossier {IMAGE_DIR} n'existe pas.")
        return

    images = glob.glob(os.path.join(IMAGE_DIR, "*.png")) + \
             glob.glob(os.path.join(IMAGE_DIR, "*.jpg")) + \
             glob.glob(os.path.join(IMAGE_DIR, "*.jpeg"))

    if not images:
        print("✅ Aucune image à convertir.")
        return

    print(f"🔍 {len(images)} images trouvées.")

    for img_path in images:
        print(f"🔄 Conversion de {img_path}...")
        new_path = convert_image(img_path)
        if new_path:
            update_json_files(img_path, new_path)
            print(f"   → {new_path}")

    print("🎉 Conversion terminée.")

if __name__ == "__main__":
    main()