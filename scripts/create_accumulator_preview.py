#!/usr/bin/env python3
"""Découpe EXACTEMENT les pixels du coupon HD, de l'en-tête à la fin du 2e match.

Le renderer Playwright fournit la hauteur réelle des deux premières lignes
via leurs bounding boxes CSS. Il n'y a ni recomposition graphique ni zoom.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from PIL import Image, ImageChops


def create_preview(
    full_path: Path,
    preview_path: Path,
    metadata_path: Path,
) -> tuple[int, int, int]:
    if not full_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError("Coupon complet ou métadonnées de découpe introuvables")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    height = metadata.get("preview_height")
    matches = metadata.get("preview_matches")
    total = metadata.get("match_count")
    if not all(type(x) is int for x in (height, matches, total)):
        raise ValueError("Dimensions de découpe / compteurs de matchs incorrects")
    if not 1 <= matches <= 2 or matches != min(total, 2):
        raise ValueError("Aperçu incorrect : maximum 2 matchs autorisés")
    with Image.open(full_path) as source:
        if source.format != "PNG" or source.width != 1080:
            raise ValueError("Coupon source attendu : PNG 1080 px")
        if not 300 < height < source.height:
            raise ValueError(f"Découpe hors limites : {height}/{source.height}")
        if source.height + source.width > 10000:
            raise ValueError("Le coupon dépasse la taille d'une photo Telegram")
        preview = source.convert("RGB").crop((0, 0, source.width, height))
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview.save(preview_path, format="PNG", optimize=True)
        with Image.open(preview_path) as saved:
            # Garantit une vraie découpe, sans image différente ou re-rendu.
            delta = ImageChops.difference(saved.convert("RGB"), preview)
            if delta.getbbox() is not None:
                raise RuntimeError("L'aperçu ne correspond pas aux pixels d'origine")
        print(
            "ACCUMULATOR_PREVIEW_OK",
            json.dumps({
                "width": preview.width,
                "height": preview.height,
                "matches_shown": matches,
                "total_matches": total,
                "origin": str(full_path),
                "preview": str(preview_path),
                "pixel_identical": True,
            }, ensure_ascii=False),
        )
        return preview.width, preview.height, matches


def main() -> None:
    complete = Path(os.getenv("ACCUMULATOR_OUTPUT", "telegram_out/accumulator_reference.png"))
    preview = Path(os.getenv("ACCUMULATOR_PREVIEW", "telegram_out/accumulator_preview.png"))
    meta = Path(os.getenv("ACCUMULATOR_CROP_META", "telegram_out/accumulator_crop.json"))
    create_preview(complete, preview, meta)


if __name__ == "__main__":
    main()
