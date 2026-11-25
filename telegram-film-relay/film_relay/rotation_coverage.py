"""Read-only exhaustive inventory of cinema channels vs safe rotating destinations.

Uses the same service-role-only Vault-backed RPC as the Telegram cinema
campaign. Private channel IDs/titles are never printed, exported or persisted.
A public cinema channel without an explicitly verified *different* archive
remains uncovered; this module NEVER tries to delete or move its media.
"""
from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser(description='CinéX : vérifier la couverture des canaux publics par des archives configurées')
    parser.add_argument('--require-complete', action='store_true',
                        help='Échouer tant que tous les canaux publics vérifiés ne possèdent pas une association d archive configurée')
    args = parser.parse_args(argv)
    try:
        rows = fetch_secure_cinema_targets()
        report = evaluate_coverage(rows, category_targets())
    except CoverageError as exc:
        print("::error::CINEX_ROTATION_COVERAGE " + str(exc))
        return 1
    print("CINEX_ROTATION_COVERAGE " + json.dumps(report, ensure_ascii=False,
                                                  sort_keys=True))
    if report["verified_public_uncovered"]:
        print("::warning::CINEX_ROTATION_COVERAGE_INCOMPLETE: " +
              str(report["verified_public_uncovered"]) +
              " public cinema channels are NOT configured for rotation")
    if report["configured_not_in_verified_cinema"]:
        print("::warning::CINEX_ROTATION_CONFIG_NOT_IN_SECURE_INVENTORY")
    summary = (os.getenv("GITHUB_STEP_SUMMARY") or "").strip()
    if summary:
        with Path(summary).open("a", encoding="utf-8") as output:
            output.write("\n### Couverture réelle du nettoyage CinéX (sans suppression)\n")
            output.write(
                f"Canaux cinéma vérifiés : **{report['verified_cinema_total']}** "
                f"({report['verified_cinema_public']} publics, "
                f"{report['verified_cinema_private_not_rotated']} privés). "
                "Les canaux privés peuvent être des archives et ne sont pas purgés.\n\n"
            )
            output.write(
                f"Canaux publics couverts par la rotation : "
                f"**{report['verified_public_covered']}/{report['verified_cinema_public']}**.\n\n"
            )
            output.write(
                "Canaux publics non couverts (archivage et droits à vérifier avant activation) : "
                + (", ".join(report["uncovered_public"]) or "aucun") + "\n\n"
            )
            if report["uncovered_possible_source_or_stock"]:
                output.write(
                    "Sources/stock potentiels : ne pas vider sans preuve d'une sauvegarde distincte : "
                    + ", ".join(report["uncovered_possible_source_or_stock"]) + "\n"
                )
    if args.require_complete and not report["complete_public_coverage"]:
        print("::error::CINEX_ARCHIVE_COVERAGE_PARTIAL: "
              + str(report["verified_public_covered"]) + "/"
              + str(report["verified_cinema_public"])
              + " canaux publics dotés d'une association privée configurée. "
              + "La conformité des archives reste à vérifier pour chaque canal.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
