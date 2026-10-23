#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publie les sélections BSD V2 éligibles sur Bluesky, sans régénérer les cotes.

Utilise les mêmes fenêtres et critères d'éligibilité que la diffusion Telegram
de production. Supabase protège les publications de chaque canal des doublons.
La commande sans --publish est un diagnostic sans envoi.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import requests
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bsd"))
sys.path.insert(0, str(ROOT / "scripts"))

from bsd_h2h import _utc
from bsd_v2_labels import market_label
from bsd_v2_card import render as render_single
from bsd_v2_combo_card import render_combo
from bsd_v2_combos import build_combos
from bsd_v2_night import batch_date, is_night_match, matches_for_night, night_date
from bsd_v2_telegram import due, expand_tickets, combos_due

SITE_URL = "https://mrxpronos.github.io/MrXPRONOS_App/pronos.html"
MAX_AGE = timedelta(hours=36)
LEDGER_TABLE = "telegram_sent"  # réutilise l'index unique existant, sous des kinds distincts


def selections(data: dict, now: datetime) -> list[tuple[str, dict, bool]]:
    """Reproduit la sélection BSD V2 Telegram, sans ses boutons bookmakers."""
    if data.get("source") != "bsd" or data.get("model_version") != "bsd-v2-isolated":
        raise ValueError("Flux source non-BSD V2 : envoi bloqué")
    generated = _utc(str(data.get("generated_at") or ""))
    if now - generated > MAX_AGE or generated > now + timedelta(minutes=15):
        raise ValueError("Flux BSD V2 périmé ou daté du futur : envoi bloqué")

    matches = data.get("matches") or []
    night_matches = matches_for_night(matches, now)
    singles = [p for m in due(matches, now) for p in expand_tickets(m)]
    singles.extend(p for m in night_matches for p in expand_tickets(m))
    queue = [("single", m, is_night_match(m)) for m in singles]

    combos = combos_due(matches, now)
    night_batch = batch_date(now)
    if night_batch is not None:
        combos.extend(
            c for c in build_combos(night_matches)
            if night_date(c["event_date"]) == night_batch
        )
    queue.extend(("combo", c, bool(night_batch and is_night_match(c["legs"][0])))
                 for c in combos)

    # Évite aussi les doublons locaux au sein d'un même déclenchement.
    seen = set()
    result = []
    for kind, item, is_night in queue:
        ref = item.get("_telegram_selection_ref") if kind == "single" else None
        key = (kind, str(ref or item["id"]), str(item["date"]))
        if key not in seen:
            seen.add(key)
            result.append((kind, item, is_night))
    return result


def identity(kind: str, item: dict, handle: str) -> tuple[str, str, str]:
    raw_id = item.get("_telegram_selection_ref") if kind == "single" else None
    ref_id = f"{handle.lower()}:{str(raw_id or item['id'])}"
    ledger_kind = "bsd_v2_bluesky_single" if kind == "single" else "bsd_v2_bluesky_combo"
    return ledger_kind, ref_id, str(item["date"])


def ledger_headers(key: str) -> dict:
    return {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "Prefer": "return=representation,resolution=ignore-duplicates",
    }


def claim(session, base, key, ident):
    from neon_telegram_ledger import claim as reserve
    return bool(reserve(*ident))


def release(session, base, key, ident):
    from neon_telegram_ledger import release as undo
    undo(*ident)


def jpeg_bytes(path: Path, limit: int = 950_000) -> tuple[bytes, tuple[int, int]]:
    """Respecte la limite de taille des uploads image de Bluesky."""
    with Image.open(path) as source:
        picture = ImageOps.exif_transpose(source).convert("RGB")
        picture.thumbnail((1600, 1600))
        for side in (1600, 1400, 1200, 1000, 800):
            working = picture.copy()
            working.thumbnail((side, side))
            for quality in (85, 75, 65, 55):
                output = io.BytesIO()
                working.save(output, "JPEG", quality=quality, optimize=True)
                if output.tell() <= limit:
                    return output.getvalue(), working.size
    raise ValueError("Impossible de compresser l'image sous la limite Bluesky")


def short_text(value, limit=44):
    value = " ".join(str(value or "").split())
    return value[:limit - 1] + "…" if len(value) > limit else value


def post_copy(kind: str, item: dict, is_night: bool) -> tuple[str, str]:
    """Texte court avec valeurs BSD vérifiées; pas de promesse de gain."""
    label = "🌙 Sélection de nuit" if is_night else "⚽ Pronostic football"
    if kind == "single":
        pred = item["prediction"]
        fixture = f"{short_text(item.get('home_team'))} – {short_text(item.get('away_team'))}"
        market = short_text(market_label(pred.get("selection_key"),
                                         pred.get("label") or pred.get("type") or "Sélection"), 68)
        odds = pred.get("odds")
        text = f"{label} | Mr XPRONOS\n{fixture}\n🎯 {market}\n📊 Cote : {odds}"
        alt = f"Carte de pronostic Mr XPRONOS : {fixture}, sélection {market}, cote {odds}"
    else:
        legs = item.get("legs") or []
        if len(legs) != 2:
            raise ValueError("Combiné invalide : deux matchs requis")
        fixtures = [
            f"{short_text(x.get('home_team'), 28)} – {short_text(x.get('away_team'), 28)}"
            for x in legs
        ]
        text = f"{label} · Combiné | Mr XPRONOS\n" + "\n".join(fixtures)
        text += f"\n📊 Cote combinée : {item.get('combined_odds')}"
        alt = "Carte de pronostic combiné Mr XPRONOS : " + "; ".join(fixtures)
    return text, alt


def publish_one(client, kind: str, item: dict, is_night: bool) -> str:
    from atproto import client_utils, models

    with TemporaryDirectory() as folder:
        target = Path(folder) / "prediction.png"
        if kind == "single":
            image_path = Path(render_single(item, target))
        else:
            image_path = Path(render_combo(item, target))
        image, (width, height) = jpeg_bytes(image_path)
        caption, alt = post_copy(kind, item, is_night)
        text = (client_utils.TextBuilder()
                .text(caption + "\n🔗 ")
                .link("Voir les analyses", SITE_URL)
                .text("\n18+ · Jeu responsable"))
        result = client.send_image(
            text=text,
            image=image,
            image_alt=alt[:900],
            image_aspect_ratio=models.AppBskyEmbedDefs.AspectRatio(width=width, height=height),
        )
        return str(result.uri)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data.json")
    parser.add_argument("--publish", action="store_true", help="Autorise les envois réels")
    parser.add_argument("--check-auth", action="store_true", help="Teste uniquement la connexion Bluesky")
    parser.add_argument("--max-posts", type=int, default=4)
    args = parser.parse_args()
    if args.publish:
        raise SystemExit("Publication des coupons photo Bluesky désactivée. Seules les vidéos Shorts sont autorisées.")
    if args.check_auth:
        handle = os.getenv("BLUESKY_HANDLE", "").strip().lstrip("@")
        password = os.getenv("BLUESKY_APP_PASSWORD", "").strip()
        if not handle or not password:
            raise RuntimeError("BLUESKY_HANDLE ou BLUESKY_APP_PASSWORD manquant")
        from atproto import Client
        client = Client()
        profile = client.login(handle, password)
        print("BLUESKY_AUTH_OK", getattr(profile, "handle", handle))
        return 0

    now = datetime.now(timezone.utc)
    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    queue = selections(data, now)
    if not args.publish:
        print("BLUESKY_DRY_RUN", json.dumps(
            [{"kind": kind, "id": str(item["id"])} for kind, item, _ in queue],
            ensure_ascii=False,
        ))
        return 0

    handle = os.getenv("BLUESKY_HANDLE", "").strip().lstrip("@")
    password = os.getenv("BLUESKY_APP_PASSWORD", "").strip()
    supabase_url = ""  # legacy internal call signature; Neon does not need an HTTP URL
    supabase_key = ""
    if not all((handle, password, os.getenv("NEON_DATABASE_URL"))):
        raise RuntimeError("Secrets BLUESKY and NEON_DATABASE_URL required")
    if not queue:
        print("BLUESKY_NO_DUE_POSTS")
        return 0

    from atproto import Client
    client = Client()
    client.login(handle, password)
    session = requests.Session()
    sent, duplicates, errors = 0, 0, 0
    for kind, item, night in queue:
        if sent >= max(1, min(args.max_posts, 10)):
            break
        ident = identity(kind, item, handle)
        claimed = False
        posting_started = False
        try:
            claimed = claim(session, supabase_url, supabase_key, ident)
            if not claimed:
                duplicates += 1
                continue
            # Si l'API Bluesky répond de manière ambiguë, garder le claim:
            # cela évite de publier deux fois après un timeout réseau.
            posting_started = True
            uri = publish_one(client, kind, item, night)
            sent += 1
            print("BLUESKY_PUBLISHED", kind, item["id"], uri)
        except Exception as exc:
            errors += 1
            print("BLUESKY_ERROR", kind, str(item.get("id")), type(exc).__name__, str(exc)[:180])
            if claimed and not posting_started:
                try:
                    release(session, supabase_url, supabase_key, ident)
                except Exception as release_error:
                    print("BLUESKY_LEDGER_RELEASE_ERROR", type(release_error).__name__)
    print("BLUESKY_REPORT", json.dumps(
        {"eligible": len(queue), "sent": sent, "already_claimed": duplicates, "errors": errors}))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
