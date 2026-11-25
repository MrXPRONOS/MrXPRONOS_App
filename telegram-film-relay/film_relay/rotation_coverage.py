"""Read-only exhaustive inventory of cinema channels vs safe rotating destinations.

Uses the same service-role-only Vault-backed RPC as the Telegram cinema
campaign. Private channel IDs/titles are never printed, exported or persisted.
A public cinema channel without an explicitly verified *different* archive
remains uncovered; this module NEVER tries to delete or move its media.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import requests

from .ten_video_rotation import category_targets

PUBLIC_NAME = re.compile(r"^[A-Za-z0-9_]{5,32}$")
BASE_URL = re.compile(r"^https://[a-z0-9-]+\.supabase\.co$")
RPC = "/rest/v1/rpc/mrx_cinema_campaign_targets_v1"
# These are content/source catalogues, not automatically disposable relays.
REVIEW_AS_LIBRARY_OR_SOURCE = {"fastandfuriousvffr", "fichiers_cloud"}


class CoverageError(RuntimeError):
    pass


def public_handle(value: str) -> str:
    handle = str(value or "").strip().lstrip("@")
    if not PUBLIC_NAME.fullmatch(handle):
        raise CoverageError("Invalid verified public username")
    return handle.casefold()


def evaluate_coverage(rows: list[dict], pairs: list[tuple[str, str, int]]) -> dict:
    """Return only PUBLIC handles and aggregate counts, never private identities."""
    if not isinstance(rows, list) or not rows:
        raise CoverageError("Verified cinema inventory empty")
    public = set()
    private = 0
    for row in rows:
        if not isinstance(row, dict) or type(row.get("is_private")) is not bool:
            raise CoverageError("Invalid secure inventory payload")
        if row["is_private"]:
            private += 1
            if row.get("public_username"):
                raise CoverageError("Private channel carried a public username")
        else:
            public_name = public_handle(row.get("public_username"))
            if public_name in public:
                raise CoverageError("Duplicate verified public cinema destination")
            public.add(public_name)
    configured = {}
    for category, username, backup in pairs:
        handle = public_handle(username)
        if handle in configured:
            raise CoverageError("Duplicate rotating public destination")
        if not isinstance(backup, int) or backup >= -1000000000000:
            raise CoverageError("Backup destination is not a Telegram private channel ID")
        configured[handle] = category
    missing = sorted(public - set(configured))
    covered = sorted(public & set(configured))
    unverified = sorted(set(configured) - public)
    return {
        "verified_cinema_total": len(rows),
        "verified_cinema_public": len(public),
        "verified_cinema_private_not_rotated": private,
        "configured_rotation_pairs": len(configured),
        "verified_public_covered": len(covered),
        "verified_public_uncovered": len(missing),
        "configured_not_in_verified_cinema": len(unverified),
        "covered_public": ["@" + name for name in covered],
        "uncovered_public": ["@" + name for name in missing],
        "uncovered_possible_source_or_stock": [
            "@" + name for name in missing if name in REVIEW_AS_LIBRARY_OR_SOURCE
        ],
        "configured_not_verified": ["@" + name for name in unverified],
        "complete_public_coverage": not missing and not unverified,
    }



# User-approved distribution scope, 2026-11-25. Visibility is not a role.
# Fingerprints identify five verified private distribution channels without
# persisting their Telegram IDs, titles or invite links in GitHub.
SELECTED_PUBLIC = frozenset({
    "cinexfilms_vf", "seriesvf_cinex", "cinexdesirfr", "cinexcomediefr",
    "cinexanimefr", "filmsaction2026vf", "fichiers_cloud",
})
EXCLUDED_PUBLIC = frozenset({
    "bleachvffr", "lecarnetdelapovf", "lupin4saisonsvf", "fastandfuriousvffr",
})
SELECTED_PRIVATE = {
    "private-01": "390a70c6d70fc01e07c9c0725fe1063d02e742b5278dcbf1a22a8b21cda825a4",
    "private-02": "f06b9f2b6eef692865c4a6074954c9a9fb8aee1bf2becfe2caa23f2b49c6fbaa",
    "private-03": "7ff0c6d87c1d8f4c56f14a605586dba48fc43b0c60187ee98878bb81cdc8f610",
    "private-04": "5b5b3f3902d4242f5e5d03341ab7a7d790fd6fd29a5527ce4902220a62e4be9e",
    "private-05": "51e0fa571a2c070ab9b22a3815819ccb0421f7ba04762cc20d973e00b880c017",
}


def _private_fingerprint(channel_id: int) -> str:
    return hashlib.sha256(str(channel_id).encode("ascii")).hexdigest()


def evaluate_selected_scope(rows: list[dict], pairs: list[tuple[str, str, int]]) -> dict:
    """Certify only approved distribution sources, never archives or single works.

    Only actual engine pairs count as configured. A selected private source is
    not a backup destination and cannot be considered covered merely because it
    appears in the secure inventory. No Telegram changes are made here.
    """
    if not isinstance(rows, list) or not rows:
        raise CoverageError("Verified cinema inventory empty")
    public = {}
    private = set()
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or type(row.get("is_private")) is not bool:
            raise CoverageError("Invalid secure inventory payload")
        cid = row.get("channel_id")
        if type(cid) is not int or cid >= -1000000000000 or cid in seen:
            raise CoverageError("Invalid or duplicate verified channel identity")
        seen.add(cid)
        if row["is_private"]:
            if row.get("public_username"):
                raise CoverageError("Private channel carried a public username")
            private.add(cid)
        else:
            name = public_handle(row.get("public_username"))
            if name in public:
                raise CoverageError("Duplicate verified public cinema destination")
            public[name] = cid
    fingerprints = {_private_fingerprint(cid): cid for cid in private}
    source_ids = {name: public[name] for name in SELECTED_PUBLIC if name in public}
    source_ids.update({alias: fingerprints[fp] for alias, fp in SELECTED_PRIVATE.items()
                       if fp in fingerprints})
    selected = SELECTED_PUBLIC | set(SELECTED_PRIVATE)
    excluded_ids = {public[name] for name in EXCLUDED_PUBLIC if name in public}
    by_id = {cid: name for name, cid in source_ids.items()}
    configured = set()
    rejected = 0
    seen_pairs = set()
    for category, source, backup in pairs:
        # The present engine emits public @usernames. If private-source support
        # is later added to the engine, its explicit numeric source may count.
        if type(source) is int:
            cid = source
        else:
            try:
                cid = public.get(public_handle(source))
            except CoverageError:
                cid = None
        if (cid is None or cid not in by_id or cid in seen_pairs
                or type(backup) is not int or backup not in private
                or backup == cid or backup in by_id or backup in excluded_ids):
            rejected += 1
            continue
        seen_pairs.add(cid)
        configured.add(by_id[cid])
    missing_inventory = selected - set(source_ids)
    missing_pairs = selected - configured
    # Unclassified new public channels require human review, not automatic
    # rotation. They are reported separately from the approved twelve.
    unknown_public = set(public) - SELECTED_PUBLIC - EXCLUDED_PUBLIC
    return {
        "inventory_total": len(rows),
        "approved_scope_total": len(selected),
        "approved_public_total": len(SELECTED_PUBLIC),
        "approved_private_total": len(SELECTED_PRIVATE),
        "approved_verified_in_inventory": len(source_ids),
        "approved_configured": len(configured),
        "approved_pending": len(missing_pairs),
        "configured_public": sorted("@" + n for n in configured & SELECTED_PUBLIC),
        "pending_public": sorted("@" + n for n in missing_pairs & SELECTED_PUBLIC),
        "private_configured_count": len(configured & set(SELECTED_PRIVATE)),
        "private_pending_count": len(missing_pairs & set(SELECTED_PRIVATE)),
        "inventory_missing_count": len(missing_inventory),
        "excluded_public": sorted("@" + n for n in set(public) & EXCLUDED_PUBLIC),
        "private_outside_approved_scope_count": len(private) - len(set(source_ids) & set(SELECTED_PRIVATE)),
        "unclassified_public": sorted("@" + n for n in unknown_public),
        "rejected_pairs": rejected,
        "complete_approved_coverage": not missing_pairs and not rejected and not missing_inventory,
    }


def fetch_secure_cinema_targets() -> list[dict]:
    base = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not BASE_URL.fullmatch(base) or not key:
        raise CoverageError("Supabase service-role inventory credentials missing")
    try:
        response = requests.post(
            base + RPC, json={},
            headers={"apikey": key, "Authorization": "Bearer " + key,
                     "Content-Type": "application/json"},
            timeout=(8, 35),
        )
        if response.status_code != 200:
            raise CoverageError("Verified cinema RPC unavailable HTTP " +
                                str(response.status_code))
        rows = response.json()
    except (requests.RequestException, ValueError):
        # Do not print exceptions containing Supabase URLs or credentials.
        raise CoverageError("Verified cinema inventory transport unavailable") from None
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='CinéX : vérifier les canaux de diffusion approuvés')
    parser.add_argument('--require-complete', action='store_true',
                        help='Échouer tant que les douze canaux approuvés ne possèdent pas une archive configurée')
    args = parser.parse_args(argv)
    try:
        rows = fetch_secure_cinema_targets()
        report = evaluate_selected_scope(rows, category_targets())
    except CoverageError as exc:
        print("::error::CINEX_ROTATION_COVERAGE " + str(exc))
        return 1
    print("CINEX_APPROVED_SCOPE " + json.dumps(report, ensure_ascii=False, sort_keys=True))
    if report["approved_pending"]:
        print("::warning::CINEX_ROTATION_COVERAGE_INCOMPLETE: "
              + str(report["approved_pending"]) + " approved channels pending")
    summary = (os.getenv("GITHUB_STEP_SUMMARY") or "").strip()
    if summary:
        with Path(summary).open("a", encoding="utf-8") as output:
            output.write("\n### CinéX : couverture des canaux de diffusion approuvés\n\n")
            output.write(f"Inventaire cinéma : {report['inventory_total']} canaux. "
                         f"Périmètre approuvé : {report['approved_scope_total']} "
                         f"({report['approved_public_total']} publics, "
                         f"{report['approved_private_total']} privés).\n\n")
            output.write(f"Associations configurées : **{report['approved_configured']}/"
                         f"{report['approved_scope_total']}**. "
                         f"Privés en attente : {report['private_pending_count']}.\n\n")
            output.write("Publics en attente : " + (", ".join(report["pending_public"]) or "aucun") + "\n\n")
            output.write("Publics spécialisés exclus : " + (", ".join(report["excluded_public"]) or "aucun") + "\n\n")
            output.write("Les autres privés (œuvres, archives, secours, actualités) "
                         "restent hors périmètre. Aucune suppression n'est autorisée par cet audit.\n")
    if args.require_complete and not report["complete_approved_coverage"]:
        print("::error::CINEX_ARCHIVE_COVERAGE_PARTIAL: "
              + str(report["approved_configured"]) + "/"
              + str(report["approved_scope_total"])
              + " canaux approuvés dotés d'une association privée configurée; "
              "la preuve média est distincte.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
