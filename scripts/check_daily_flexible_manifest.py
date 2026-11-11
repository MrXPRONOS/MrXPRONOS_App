#!/usr/bin/env python3
"""Strict daily pre-publication audit for 1–10 authentic social video cards.

Executed after render and before any token refresh or social provider calls.
Actual prediction/storyboard/MP4 proofs are also rechecked by the publisher.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate_daily_manifest(manifest: dict, *, day: str, mode: str) -> int:
    if mode not in {"strict", "flexible"}:
        raise ValueError("Mode de publication inconnu")
    n = manifest.get("count")
    expected_schema = (
        "mrx-dixon-coles-social-flex-v3" if mode == "flexible"
        else "mrx-dixon-coles-social-top10-v1"
    )
    if (
        manifest.get("schema") != expected_schema
        or manifest.get("publication_mode") != mode
        or manifest.get("target") != day
        or manifest.get("status") != "READY"
        or manifest.get("ready_for_video") is not True
        or type(n) is not int or not 1 <= n <= 10
        or (mode == "strict" and n != 10)
    ):
        raise ValueError("Manifeste quotidien invalide : date, mode ou nombre de matchs")

    video = manifest.get("video")
    if (not isinstance(video, str)
            or Path(video).name != f"social_exact_scores_{n}.mp4"):
        raise ValueError("Le nom du MP4 ne correspond pas au nombre de rencontres")

    proof = manifest.get("render_evidence") or {}
    if (
        not isinstance(proof, dict)
        or proof.get("real_logo_instances") != 2 * n
        or proof.get("placeholder_logo_instances") != 0
        or proof.get("resolution") != "1080x1920"
    ):
        raise ValueError("Preuves invalides : deux vrais écussons par rencontre requis")
    if mode == "flexible":
        ids = manifest.get("match_ids")
        if (not isinstance(ids, list) or len(ids) != n
                or not all(isinstance(x, str) and x for x in ids)
                or len(set(ids)) != n):
            raise ValueError("Les matchs du manifeste ne sont pas tous distincts")
    return n


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--day", required=True)
    p.add_argument("--mode", required=True, choices=("flexible", "strict"))
    p.add_argument("--output", type=Path, help="Optional GITHUB_OUTPUT file")
    args = p.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    n = validate_daily_manifest(manifest, day=args.day, mode=args.mode)
    if args.output:
        with args.output.open("a", encoding="utf-8") as stream:
            stream.write(f"validated_count={n}\n")
    print(f"DAILY_FLEXIBLE_MANIFEST_VALIDATED day={args.day} mode={args.mode} "
          f"cards={n} empty_slots={10 - n} real_crests={2 * n}", flush=True)


if __name__ == "__main__":
    main()
