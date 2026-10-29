#!/usr/bin/env python3
"""Prepare an explicit public GitHub Pages artifact, never the repository root.

Internal generators, provider reports, training files, encrypted ledgers and
admin-only operational archives must not be published by GitHub Pages.
The original data.json and audit files remain unchanged in the main repository.
"""
from __future__ import annotations

import argparse
import importlib.util
import hashlib
import math
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    "robots.txt", "sitemap.xml", "CNAME", "favicon.ico", "manifest.json",
    "service-worker.js", "sw.js", "service_worker.js",
    "supabase-client.js",
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
    "quality_report", "model_summary", "training_stats", "provider_health",
}
TECHNICAL_TEXT = re.compile(
    r"\b(?:BSD|PSD)(?:[\s_-]*V\d+(?:\.\d+)?)?\b"
    r"|\b(?:mrxpronos_model|bsd_consensus|bsd_bookmaker)\b", re.I
)


PUBLIC_MIN_CONFIDENCE = 79.0
PUBLIC_IMAGE_LEGACY_PREFIX = "match-bsd-match-"
PUBLIC_IMAGE_PREFIX = "match-"

PUBLIC_MATCH_FIELDS = (
    "date", "event_date", "home_team", "away_team", "home_logo",
    "away_logo", "league_logo", "league", "category",
    "recommendation_eligible", "status", "is_finished", "home_score",
    "away_score", "verified_double", "combo_only",
)
PUBLIC_PICK_FIELDS = (
    "type", "label", "market", "selection_key", "outcome", "line",
    "confidence", "double_chance", "odds", "estimated_odds",
    "recommendation_eligible",
)


def _public_pick(pick):
    if not isinstance(pick, dict):
        return {}
    return {key: pick[key] for key in PUBLIC_PICK_FIELDS if key in pick}


def validate_public_prediction(pick):
    """Fail closed when a primary, secondary or combined selection is below policy."""
    if not isinstance(pick, dict):
        raise ValueError("Invalid public selection")
    confidence = pick.get("confidence")
    if (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
            or not math.isfinite(confidence)
            or not PUBLIC_MIN_CONFIDENCE <= confidence <= 100):
        raise ValueError("Public selection violates the 79 percent confidence policy")
    if pick.get("recommendation_eligible") is False:
        raise ValueError("Ineligible selection cannot be published")


def public_copy(value):
    """Strictly project a generated feed into the visitor-facing product schema.

    This is an allowlist, not a blacklist: newly added private data fields
    cannot accidentally become public. The operational source is not mutated.
    """
    if not isinstance(value, dict) or not isinstance(value.get("matches"), list):
        raise ValueError("A generated feed with a matches array is required")
    # Only a rank is exported. Precise internal scoring and calibration stay
    # with the engine; page ordering is preserved exactly.
    matches = value["matches"]
    ranked = sorted(
        enumerate(matches),
        key=lambda pair: (
            -float(pair[1].get("final_score") or pair[1].get("xpronos_score") or 0),
            pair[0],
        ),
    )
    ranks = {original_index: order for order, (original_index, _) in enumerate(ranked, 1)}
    public = []
    for index, match in enumerate(matches):
        if not isinstance(match, dict):
            raise ValueError("Invalid match in generated feed")
        if match.get("category") not in ("pro", "vip"):
            raise ValueError("Public match must be Pro or VIP")
        if match.get("recommendation_eligible") is False:
            raise ValueError("Ineligible match cannot be published")
        validate_public_prediction(match.get("prediction"))
        if match.get("predictions") is not None:
            if not isinstance(match["predictions"], list):
                raise ValueError("Invalid secondary selection list")
            for secondary in match["predictions"]:
                validate_public_prediction(secondary)
        selection = _public_pick(match.get("prediction"))
        if not selection:
            raise ValueError("Match without a public primary prediction")
        item = {field: match[field] for field in PUBLIC_MATCH_FIELDS if field in match}
        # Public IDs are stable and opaque; do not leak engine or provider IDs.
        item["id"] = "match-" + hashlib.sha256(
            str(match.get("id", "")).encode("utf-8")
        ).hexdigest()[:16]
        item["display_rank"] = ranks[index]
        item["prediction"] = selection
        if isinstance(match.get("predictions"), list) and match["predictions"]:
            item["predictions"] = [_public_pick(pick) for pick in match["predictions"]]
        public.append(item)
    if len({match["id"] for match in public}) != len(public):
        raise ValueError("Public match identifiers are not unique")
    result = {"generated_at": value.get("generated_at"), "matches": public}
    if isinstance(value.get("bookmakers"), list):
        public_bookmaker_fields = {"name", "logo", "url", "desc", "bonus", "promo_code"}
        result["bookmakers"] = [
            {key: row[key] for key in public_bookmaker_fields if key in row}
            for row in value["bookmakers"] if isinstance(row, dict)
        ]
    return result


def clean_match_article_text(value: str) -> str:
    text = str(value)
    # Legacy articles used private engine branding in titles, snippets and copy.
    text = text.replace(" : fiche match BSD V2", " : analyse du match")
    text = text.replace(" : affiche vérifiée dans le flux football BSD V2, le ", " : rencontre du ")
    text = text.replace("## Signal calculé par le moteur BSD V2", "## Analyse de la rencontre")
    text = text.replace("**Score final BSD :**", "**Score final :**")
    text = text.replace("Non précisée dans les données BSD", "Non précisée")
    text = text.replace("dernier flux BSD disponible", "dernier relevé disponible")
    text = text.replace(
        "Il s'agit d'une estimation du modèle, pas d'un résultat certain.",
        "Ce pronostic est indicatif et ne garantit aucun résultat.",
    )
    text = re.sub(r"(?m)^\*\*Source des données :\*\* BSD V2, identifiant [^\n]*\n?", "", text)
    text = re.sub(r"(?i)\b(?:BSD|PSD)[\s_-]+V\d+(?:\.\d+)?\b", "Mr XPRONOS", text)
    text = re.sub(r"(?i)\b(?:BSD|PSD)\b(?![-_/:])", "Mr XPRONOS", text)
    return text


def prepare_public_editorial_media(destination: Path):
    """Provide clean public media aliases without breaking previously shared image URLs."""
    editorial = destination / "assets/images/editorial"
    if not editorial.is_dir():
        return
    for original in editorial.glob(PUBLIC_IMAGE_LEGACY_PREFIX + "*"):
        if not original.is_file() or original.is_symlink():
            continue
        alias = original.with_name(original.name.replace(
            PUBLIC_IMAGE_LEGACY_PREFIX, PUBLIC_IMAGE_PREFIX, 1
        ))
        if not alias.exists():
            shutil.copy2(original, alias)


def prepare_public_articles(destination: Path):
    file = destination / "articles.json"
    if file.exists():
        rows = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError("Unexpected public article feed shape")
        for row in rows:
            if not isinstance(row, dict):
                continue
            if row.get("type") != "match" or row.get("source") != "bsd":
                continue
            if isinstance(row.get("slug"), str) and row["slug"].startswith("bsd-match-"):
                row["slug"] = "match-" + row["slug"][len("bsd-match-"):]
            for field in ("title", "excerpt", "meta_description", "keywords", "content"):
                if isinstance(row.get(field), str):
                    row[field] = clean_match_article_text(row[field])
            for image_field in ("image_url", "social_image", "story_image", "og_image", "ab_image_url"):
                if isinstance(row.get(image_field), str):
                    row[image_field] = row[image_field].replace(
                        PUBLIC_IMAGE_LEGACY_PREFIX, PUBLIC_IMAGE_PREFIX
                    )
            for key in ("source", "bsd_event_id", "bsd_match_date", "editorial_importance",
                        "editorial_reasons", "editorial_role", "visual_variant", "visual_hash"):
                row.pop(key, None)
        file.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # Preserve legacy redirects for old shared links, but use clean URLs for
    # new links, canonical tags and sitemap entries.
    for html in destination.glob("articles/bsd-match-*/index.html"):
        old = html.read_text(encoding="utf-8")
        cleaned = clean_match_article_text(old)
        cleaned = cleaned.replace("slug=bsd-match-", "slug=match-")
        cleaned = cleaned.replace("/articles/bsd-match-", "/articles/match-")
        html.write_text(cleaned, encoding="utf-8")
        alias = html.parents[1] / html.parent.name.replace("bsd-match-", "match-") / "index.html"
        alias.parent.mkdir(parents=True, exist_ok=True)
        alias.write_text(cleaned, encoding="utf-8")
    sitemap = destination / "sitemap.xml"
    if sitemap.exists():
        body = sitemap.read_text(encoding="utf-8")
        sitemap.write_text(body.replace("/articles/bsd-match-", "/articles/match-"), encoding="utf-8")


def refresh_public_script_versions(destination: Path):
    # Cached scripts otherwise keep showing outdated technical labels after deploy.
    for html in destination.rglob("*.html"):
        body = html.read_text(encoding="utf-8")
        # Generated article metadata and redirects must use clean image URLs.
        body = body.replace(PUBLIC_IMAGE_LEGACY_PREFIX, PUBLIC_IMAGE_PREFIX)
        # GitHub Pages assets used to carry a fixed old query version.
        # Pin the browser-visible version to the current source revision.
        import os
        version = re.sub(r"[^0-9a-f]", "", os.environ.get("GITHUB_SHA", ""))[:12] or "local"
        replacement = re.sub(
            r"(assets/(?:js|css)/[a-zA-Z0-9_.-]+\\.(?:js|css))(?:\\?v=[a-zA-Z0-9_.-]+)?",
            lambda m: m.group(1) + "?v=" + version,
            body,
        )
        if replacement != html.read_text(encoding="utf-8"):
            html.write_text(replacement, encoding="utf-8")


def pause_public_features(destination: Path):
    """Hide the visitor assistant and LIVE discovery without deleting source code."""
    for html in destination.rglob("*.html"):
        if not html.is_file():
            continue
        body = html.read_text(encoding="utf-8")
        if not html.name.startswith("admin"):
            body = re.sub(
                r"""(?i)<script\b[^>]*\bsrc=["'](?:\./)?assets/js/assistant\.js(?:\?[^"']*)?["'][^>]*>\s*</script>""",
                "",
                body,
            )
        if html == destination / "live.html" and 'name="robots"' not in body:
            body = body.replace("<head>", '<head>\n  <meta name="robots" content="noindex, nofollow">', 1)
        html.write_text(body, encoding="utf-8")

    # Do not let a stale sitemap expose the paused LIVE section again.
    sitemap = destination / "sitemap.xml"
    if sitemap.is_file():
        body = sitemap.read_text(encoding="utf-8")
        body = re.sub(
            r"(?s)\s*<url>\s*<loc>[^<]*/prono-live/[^<]*</loc>.*?</url>",
            "",
            body,
        )
        sitemap.write_text(body, encoding="utf-8")


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

    prepare_public_editorial_media(destination)
    prepare_public_articles(destination)
    refresh_public_script_versions(destination)
    pause_public_features(destination)

    public_feed = destination / "data.json"
    if public_feed.exists():
        data = json.loads(public_feed.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("matches"), list):
            raise ValueError("Refusing to deploy invalid football feed")
        # Keep the operational feed intact on main; publish a redacted view.
        safe_data = public_copy(data)
        public_feed.write_text(json.dumps(safe_data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        # Separate pre-kickoff snapshots from settlement data. Receipts are
        # immutable public files; their GitHub commit history is the audit trail.
        module_path = Path(__file__).resolve().parent / "public_proof_receipts.py"
        spec = importlib.util.spec_from_file_location("public_proof_receipts", module_path)
        proof_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(proof_module)
        count = proof_module.build_proofs(destination, previous, safe_data)
        print("PUBLIC_PREDICTION_RECEIPTS", count)


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
