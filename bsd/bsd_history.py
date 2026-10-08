#!/usr/bin/env python3
"""Historique BSD indépendant, stockage local privé, sans publication."""
from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from bsd_api import BSDAPIError, BSDClient


def ingest_events(existing, incoming):
    """Fusion stable par ID BSD, sans doublons; conserve les champs précédents."""
    result = {str(e["id"]): dict(e) for e in existing if isinstance(e, dict) and e.get("id") is not None}
    for entry in incoming:
        if not isinstance(entry, dict) or entry.get("id") is None:
            raise ValueError("Événement sans ID BSD")
        key = str(entry["id"])
        result[key] = {**result.get(key, {}), **entry}
    return sorted(result.values(), key=lambda e: str(e["id"]))


def save_private_json(path: Path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({
        "provider": "BSD",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "events": events,
    }, ensure_ascii=False), encoding="utf-8")
    os.chmod(temp, 0o600)
    temp.replace(path)


def load_private_json(path: Path):
    if not path.exists():
        return []
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("provider") != "BSD" or not isinstance(obj.get("events"), list):
        raise ValueError("Historique incompatible : fournisseur BSD attendu")
    return obj["events"]


def main():
    parser = argparse.ArgumentParser(description="Importer une saison de BSD en local, sans publication")
    parser.add_argument("--league-id", type=int, required=True)
    parser.add_argument("--season-id", type=int, required=True)
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--max-requests", type=int, default=4)
    parser.add_argument("--output-dir", default="bsd/private_history")
    args = parser.parse_args()
    if args.league_id <= 0 or args.season_id <= 0:
        parser.error("Identifiants BSD positifs obligatoires")
    if not 1 <= args.max_pages <= 20:
        parser.error("max-pages entre 1 et 20")
    if not 1 <= args.max_requests <= 25:
        parser.error("max-requests entre 1 et 25")
    path = Path(args.output_dir) / ("league_%d_season_%d.json" % (args.league_id, args.season_id))
    try:
        client = BSDClient(max_requests=args.max_requests)
        page = client.list_season_events(
            args.league_id, args.season_id, max_pages=args.max_pages
        )
        if not page.complete:
            print("Pagination incomplète : import annulé pour ne pas confondre échantillon et saison.", file=sys.stderr)
            return 2
        old = load_private_json(path)
        merged = ingest_events(old, page.events)
        save_private_json(path, merged)
        print(json.dumps({
            "league_id": args.league_id, "season_id": args.season_id,
            "received": len(page.events), "stored_total": len(merged),
            "http_requests": client.requests_made,
            "quota_remaining": client.rate_limit_remaining,
            "output": str(path), "complete": True
        }, ensure_ascii=False))
        return 0
    except (BSDAPIError, ValueError, OSError) as exc:
        print("ERREUR historique BSD:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
