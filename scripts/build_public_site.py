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
# Publish only routes, data and assets consumed by visitors. No owner CMS,
# social OAuth callbacks, paused LIVE pages, telemetry, experimental scripts or
# internal content-generation prompts in the GitHub Pages artifact.
PUBLIC_HTML = {
    "index.html", "pronos.html", "historique.html", "blog.html",
    "bonus.html", "bookmakers.html", "conseils.html", "infos.html",
    "contact.html", "article.html", "conseil.html", "offline.html",
}
ROOT_FILES = {
    "robots.txt", "sitemap.xml", "CNAME", "favicon.ico", "manifest.json",
    "service-worker.js", "googlebf35e152c3bdd841.html",
}
PUBLIC_JSON = {
    "data.json", "footnews.json", "articles.json", "infos.json",
    "bonus.json", "bookmakers.json", "conseils.json", "testimonials.json",
}
PUBLIC_JS = {
    "main.js", "cms-url-guard.mjs", "pwa.js", "menu.js",
    "back-to-top.js", "home-premium.js", "loading-ui.js",
    "bonus-catalogue.js", "bonus-offers.js",
    # Browser push notifications and opt-in services currently use a
    # Supabase publishable (not privileged/service-role) key.
    "config.js",
}
PUBLIC_CSS = {
    "style.css", "loading-ui.css", "home-premium.css",
    "home-polish.css", "pronos-premium.css", "history-premium.css",
    "blog-premium.css", "conseils-premium.css", "infos-premium.css",
    "bonus-premium.css", "bookmakers-premium.css", "contact-premium.css",
    "article-detail-premium.css", "conseil-detail-premium.css",
    "mobile-nav-premium.css", "brand-signatures.css",
}
PUBLIC_DIRS = (
    "assets/css", "assets/js", "assets/images", "assets/fonts",
    "assets/icons", "assets/media", "assets/videos", "assets/video",
    "articles", "conseils",
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
# User-facing fields only. Scraper diagnostics, provider snapshots, quality
# scores, Telegram draft captions and internal verification reports stay private.
PUBLIC_NEWS_FIELDS = {
    "slug", "title", "summary", "summary_short", "content", "paragraphs",
    "key_points", "published", "source", "link", "source_url", "site_url",
    "image", "source_image", "category", "category_emoji",
}
PUBLIC_ARTICLE_FIELDS = {
    "slug", "title", "date", "author", "reading_time", "excerpt",
    "meta_description", "keywords", "content", "active", "type", "match",
    "league", "home_logo", "away_logo", "visual_format", "image_url",
    "social_image", "story_image", "og_image", "ab_image_url", "category",
    "topic_id",
}
PUBLIC_FEED_FIELDS = {
    "conseils.json": {
        "slug", "title", "content", "excerpt", "meta_description", "date",
        "published_at", "author", "reading_time", "keywords", "category",
        "type", "image_url", "og_image", "ab_image_url", "active", "faq",
        "visual_format", "description",
    },
    "bonus.json": {
        "id", "title", "bookmaker", "description", "image", "code",
        "footer", "link", "active", "start_date", "end_date",
    },
    "bookmakers.json": {
        "id", "name", "logo", "url", "description", "desc", "bonus",
        "promo_code", "active",
    },
    "infos.json": {
        "id", "slug", "title", "content", "image_url", "date",
        "published_at", "category", "tag", "active", "link",
    },
    "testimonials.json": {"name", "city", "text", "rating"},
}


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


def structure_legacy_match_article(article: dict) -> str:
    """Improve presentation of historic match briefs without inventing evidence.

    The source article predates the structured editorial format; any market
    mentioned is described as a historical mention, not as a verified pick.
    """
    original = clean_match_article_text(article.get("content") or "")
    if "## 1. Présentation de la rencontre" in original:
        return original
    title = str(article.get("match") or article.get("title") or "Rencontre de football")
    league = str(article.get("league") or "Compétition non précisée")
    def original_fact(pattern: str) -> str:
        match = re.search(pattern, original, flags=re.I | re.M)
        return match.group(1).strip() if match else ""
    when = original_fact(r"\*\*Date et heure\s*:\*\*\s*([^\n]+)")
    score = original_fact(r"\*\*Score final\s*:\*\*\s*([^\n]+)")
    old_market = original_fact(r"\*\*Marché identifié\s*:\*\*\s*([^\n]+)")
    parts = [
        "## 1. Présentation de la rencontre",
        f"**Match :** {title}.",
        f"**Compétition :** {league}.",
        f"**Date et heure :** {when}" if when else
            "La date précise du match n'est pas indiquée dans cette fiche.",
        "",
        "## 2. Contexte et enjeux",
        "Cette affiche s'inscrit dans la compétition citée ci-dessus. "
        "Les enjeux de classement ou de qualification ne sont pas documentés ici.",
        "",
        "## 3. Forme récente",
        "Les résultats récents vérifiés de chaque équipe ne figurent pas dans cette fiche.",
        "",
        "## 4. Confrontations directes",
        "Aucun historique de confrontations fiable n'a été conservé dans cette fiche.",
        "",
        "## 5. Statistiques clés",
        f"**Score final indiqué dans la fiche initiale :** {score}" if score else
            "Cette fiche ne comporte pas de score final confirmé.",
        "Les statistiques de tirs, de corners et de possession ne sont pas suffisamment étayées.",
        "",
        "## 6. Points de vigilance",
        "Les conclusions fondées sur la forme récente ou les confrontations "
        "seraient spéculatives sans données complémentaires vérifiées.",
        "",
        "## 7. Notre lecture",
        "Cette présentation reprend uniquement les faits conservés dans "
        "la fiche initiale : rencontre, compétition, date et score lorsqu'ils sont renseignés.",
        "",
        "## 8. Pronostic associé",
        (f"**Marché mentionné dans la fiche d'origine :** {old_market} "
         "Cette mention ne prouve pas qu'un pronostic a été publié avant le coup d'envoi."
         if old_market else
         "Aucun pronostic pré-match vérifiable n'est présenté dans cette fiche."),
        "Vérifiez les résultats et les preuves de publication dans la rubrique Résultats.",
        "",
        "**18+ — Les paris sportifs comportent un risque de perte.**",
    ]
    return "\n".join(parts)


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


def prepare_public_news(destination: Path):
    path = destination / "footnews.json"
    if not path.exists():
        return
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Public news must be a list")
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not isinstance(row.get("title"), str) or not row["title"].strip():
            continue
        result.append({key: value for key, value in row.items() if key in PUBLIC_NEWS_FIELDS})
    path.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def prepare_public_feeds(destination: Path):
    """CMS drafts and administrator fields must never be in the public JSON."""
    for name, visible_fields in PUBLIC_FEED_FIELDS.items():
        file = destination / name
        if not file.exists():
            continue
        rows = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"Unexpected public feed shape: {name}")
        cleaned = [
            {key: value for key, value in row.items() if key in visible_fields}
            for row in rows
            if isinstance(row, dict) and row.get("active") is not False
        ]
        file.write_text(json.dumps(cleaned, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def prepare_public_articles(destination: Path):
    file = destination / "articles.json"
    if file.exists():
        rows = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError("Unexpected public article feed shape")
        published = []
        for raw in rows:
            if not isinstance(raw, dict) or raw.get("active") is False:
                continue
            row = {key: value for key, value in raw.items() if key in PUBLIC_ARTICLE_FIELDS}
            if not isinstance(row.get("title"), str) or not row["title"].strip():
                continue
            if isinstance(row.get("slug"), str) and row["slug"].startswith("bsd-match-"):
                row["slug"] = "match-" + row["slug"][len("bsd-match-"):]
            for field in ("title", "excerpt", "meta_description", "keywords", "content"):
                if isinstance(row.get(field), str):
                    row[field] = clean_match_article_text(row[field])
            if row.get("type") == "match":
                row["content"] = structure_legacy_match_article(row)
                row["reading_time"] = max(1, (len(row["content"].split()) + 199) // 200)
            for image_field in ("image_url", "social_image", "story_image", "og_image", "ab_image_url"):
                if isinstance(row.get(image_field), str):
                    row[image_field] = row[image_field].replace(
                        PUBLIC_IMAGE_LEGACY_PREFIX, PUBLIC_IMAGE_PREFIX
                    )
            published.append(row)
        file.write_text(json.dumps(published, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
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
            r"(assets/(?:js|css)/[a-zA-Z0-9_.-]+\.(?:js|css))(?:\?v=[a-zA-Z0-9_.-]+)?",
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
                r"""(?i)<script\b[^>]*\bsrc=["'](?:\./)?assets/js/(?:assistant|web-vitals-monitor)\.js(?:\?[^"']*)?["'][^>]*>\s*</script>""",
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
        if source.name == "js" and path.name not in PUBLIC_JS:
            continue
        if source.name == "css" and path.name not in PUBLIC_CSS:
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
        if item.name in PUBLIC_HTML or item.name in ROOT_FILES or item.name in PUBLIC_JSON:
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
    prepare_public_news(destination)
    prepare_public_feeds(destination)
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
        "admin.html", "admin-dashboard.html", "admin-supervision.html",
        "admin-vip.html", "telegram-analytics.html", "threads-callback.html",
        "tiktok-callback.html", "live.html", "live-suspended.html",
        "prono-live", "evergreen_topics.json", "historical_scores.json",
        "assets/js/assistant.js", "assets/js/admin-real.js",
        "assets/js/admin-supervision.js", "assets/js/live.precompiled.js",
        "assets/js/actu-foot-neon.js", "assets/js/web-vitals-monitor.js",
        "assets/css/admin-premium.css", "assets/css/live-premium.css",
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
