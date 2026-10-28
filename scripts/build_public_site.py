#!/usr/bin/env python3
"""Prepare an explicit public GitHub Pages artifact, never the repository root.

Internal generators, provider reports, training files, encrypted ledgers and
admin-only operational archives must not be published by GitHub Pages.
The original data.json and audit files remain unchanged in the main repository.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    "robots.txt", "sitemap.xml", "CNAME", "favicon.ico", "manifest.json",
    "service-worker.js", "sw.js", "service_worker.js",
    "admin-config.js", "supabase-client.js",
}
PUBLIC_JSON = {
    "data.json", "footnews.json", "historical_scores.json",
    "articles.json", "infos.json", "bonus.json", "bookmakers.json",
    "conseils.json", "testimonials.json", "evergreen_topics.json",
}
PUBLIC_DIRS = (
    "assets/css", "assets/js", "assets/images", "assets/fonts",
    "assets/icons", "assets/media", "assets/videos", "assets/video",
    "articles", "conseils", "telegram-guides", "prono-live/assets",
)
LEGACY_MEDIA = (
    "assets/images/footnews", "assets/images/arty_football",
)
ALLOWED_ASSET_EXTS = {
    ".html", ".htm", ".css", ".js", ".mjs", ".json", ".webmanifest",
    ".png", ".webp", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".webm", ".txt", ".xml",
}
PRIVATE_DATA_KEYS = {
    "diagnostics", "model_odds_observations", "multisource_verification",
    "model_version", "source", "source_event_id", "odds_source",
    "quote_timestamp_type", "per_market_update_verified",
    "odds_provider", "provider", "provider_response", "provider_payload",
    "provider_snapshot", "debug", "debug_info", "internal_notes",
    "internal", "pipeline", "calibration", "model_details", "model_features",
    "raw_provider_quote", "provider_market_id", "provider_match_id",
}
TECHNICAL_TEXT = re.compile(
    r"\\b(?:BSD|PSD)(?:[\\s_-]*V\\d+(?:\\.\\d+)?)?\\b"
    r"|\\b(?:mrxpronos_model|bsd_consensus|bsd_bookmaker)\\b", re.I
)


def public_copy(value):
    """Remove diagnostic metadata without changing match or prediction fields."""
    if isinstance(value, list):
        return [public_copy(item) for item in value]
    if isinstance(value, dict):
        return {
            k: public_copy(v) for k, v in value.items()
            if k.lower() not in PRIVATE_DATA_KEYS
            and not k.lower().startswith(("diagnostic_", "debug_", "model_", "provider_"))
            and not k.lower().endswith(("_provider", "_diagnostics", "_source"))
        }
    return value


def copy_public_tree(source: Path, dest: Path):
    if not source.exists():
        return
    for path in source.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        if path.suffix.lower() not in ALLOWED_ASSET_EXTS:
            continue
        if any(part.startswith(".") or part in {"private", "__pycache__", "node_modules", "tmp"} for part in path.relative_to(source).parts):
            continue
        output = dest / path.relative_to(source)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, output)


def stage_site(destination: Path, previous: Path | None):
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    (destination / ".nojekyll").write_text("", encoding="utf-8")
    for item in ROOT.iterdir():
        if not item.is_file():
            continue
        if (item.suffix.lower() == ".html" and item.name != "live-scrape-test.html") or item.name in ROOT_FILES or item.name in PUBLIC_JSON:
            shutil.copy2(item, destination / item.name)
    for section in PUBLIC_DIRS:
        copy_public_tree(ROOT / section, destination / section)
    if previous is not None:
        # These historical media files exist on gh-pages only. Preserve their
        # URLs while replacing the unsafe branch with the curated artifact.
        for section in LEGACY_MEDIA:
            old = previous / section
            if old.exists():
                for file in old.rglob("*"):
                    if not file.is_file() or file.suffix.lower() not in ALLOWED_ASSET_EXTS:
                        continue
                    target = destination / section / file.relative_to(old)
                    if not target.exists():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(file, target)

    public_feed = destination / "data.json"
    if public_feed.exists():
        data = json.loads(public_feed.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("matches"), list):
            raise ValueError("Refusing to deploy invalid football feed")
        # Keep the operational feed intact on main; publish a redacted view.
        safe_data = public_copy(data)
        public_feed.write_text(json.dumps(safe_data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    for forbidden in (
        "bsd", "supabase", ".github", "scripts", "tests", "docs", "config",
        "node_modules", "model_meta.json", "data_backup.json", "logo_cache.json",
        "assets/data/private", "admin-config.template.js", "package-lock.json",
    ):
        if (destination / forbidden).exists():
            raise ValueError(f"Private path leaked to public artifact: {forbidden}")

    if not (destination / "index.html").is_file() or not (destination / "pronos.html").is_file():
        raise ValueError("Public homepage/pronostics missing")
    if not (destination / "assets/js/main.js").is_file():
        raise ValueError("Main public script missing")
    if not (destination / "footnews.json").is_file():
        raise ValueError("Public news feed missing")
    if not (destination / "data.json").is_file():
        raise ValueError("Public predictions feed missing")
    print("PUBLIC_SITE_PREPARED", len(list(destination.rglob("*"))), "entries")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="_public_site")
    parser.add_argument("--previous", default="_previous_pages")
    args = parser.parse_args()
    stage_site(ROOT / args.out, ROOT / args.previous if (ROOT / args.previous).exists() else None)
