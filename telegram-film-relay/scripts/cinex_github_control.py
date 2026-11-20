"""GitHub-only CinéX distribution switch; no Telegram administration approval.

Called by the catalogue workflow. Never sends Telegram messages and never
touches stored videos. D1 is only the mirror of GitHub configuration.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
from collections import defaultdict
from pathlib import Path

ENABLED_VAR = "CINEX_DOWNLOADS_ENABLED"
TOKEN_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"


def github_enabled(env=None):
    value = (env or os.environ).get(ENABLED_VAR, "")
    return str(value).strip().lower() == "true"


def valid_sequence(kind, season, media, expected=None):
    if not media or len(media) > 100:
        return False
    if kind == "film":
        return season == 0 and len(media) == 1 and all(
            x.get("season_number") is None and x.get("episode_number") is None for x in media
        )
    if kind != "series" or not isinstance(season, int) or not 1 <= season <= 50:
        return False
    # Never infer season completion from the largest episode number discovered.
    if not isinstance(expected, int) or not 1 <= expected <= 100 or len(media) != expected:
        return False
    try:
        episodes = sorted(int(x["episode_number"]) for x in media)
        return all(int(x["season_number"]) == season for x in media) and episodes == list(range(1, len(episodes) + 1))
    except (KeyError, ValueError, TypeError):
        return False


def eligible_links(report):
    """Build only complete, unambiguous film/season links from the CURRENT scan."""
    if {x.get("category") for x in report.get("libraries", [])} != {"series", "action"}:
        raise ValueError("Inventaire incomplet : vidéothèques séries/action requises")
    candidates = []
    for lib in report["libraries"]:
        if lib.get("status") != "scanned":
            raise ValueError("Inventaire incomplet : une vidéothèque est inaccessible")
        if lib.get("owner_access") != "verified" or lib.get("bot_access") != "verified" or not lib.get("rights_attested"):
            continue
        grouped = defaultdict(list)
        for m in lib.get("media", []):
            season = m.get("season_number") or 0
            key = (str(m.get("title_key") or ""), int(season))
            if len(key[0]) == 32 and m.get("category") == lib["category"]:
                grouped[key].append(m)
        for (title, season), media in grouped.items():
            expected = 0
            if lib["category"] == "series":
                claims = {int(m["declared_total"]) for m in media if m.get("declared_total") is not None}
                if len(claims) != 1 or next(iter(claims)) <= 0:
                    continue
                expected = next(iter(claims))
            if valid_sequence("series" if lib["category"] == "series" else "film", season, media,
                              expected=expected if season else None):
                candidates.append((lib["category"], title, season, expected))
    return sorted(set(candidates))


def make_token():
    # URL-safe, cryptographically random, exactly 24 characters.
    return "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(24))


EVIDENCE_SCHEMA = """CREATE TABLE IF NOT EXISTS cine_delivery_season_evidence (
 category TEXT NOT NULL CHECK(category='series'),
 title_key TEXT NOT NULL,
 season_key INTEGER NOT NULL CHECK(season_key BETWEEN 1 AND 50),
 expected_episodes INTEGER NOT NULL CHECK(expected_episodes BETWEEN 1 AND 100),
 observed_at TEXT NOT NULL,
 PRIMARY KEY(category,title_key,season_key)
)"""


def queries_for_report(report):
    """Replace current evidence and links, WITHOUT changing the global switch."""
    eligible = eligible_links(report)
    scanned_at = report.get("scanned_at")
    if not scanned_at:
        raise ValueError("Horodatage d'inventaire absent")
    yield {"sql": EVIDENCE_SCHEMA}
    yield {"sql": "UPDATE cine_delivery_links SET enabled=0,updated_at=CURRENT_TIMESTAMP WHERE enabled<>0"}
    yield {"sql": "DELETE FROM cine_delivery_season_evidence"}
    for category, title, season, expected in eligible:
        if season:
            yield {
                "sql": """INSERT INTO cine_delivery_season_evidence
                          (category,title_key,season_key,expected_episodes,observed_at)
                          VALUES(?,?,?,?,?)""",
                "params": [category, title, season, expected, scanned_at],
            }
        yield {
            "sql": """INSERT INTO cine_delivery_links(token,title_key,category,season_key,enabled)
                      VALUES(?,?,?,?,1) ON CONFLICT(category,title_key,season_key)
                      DO UPDATE SET enabled=1,updated_at=CURRENT_TIMESTAMP""",
            "params": [make_token(), title, category, season],
        }


def toggle_queries(enabled):
    # The global switch is the ONLY distribution permission. Links remain
    # indexed when off so that a five-minute sync can switch them back on.
    return [{"sql": EVIDENCE_SCHEMA}, {
        "sql": """INSERT INTO bot_settings(setting_key,value) VALUES('cine_delivery_enabled',?)
                   ON CONFLICT(setting_key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP""",
        "params": ["1" if enabled else "0"],
    }]


def toggle_off_queries():
    return toggle_queries(False)


def d1_execute(queries, *, token, account, database):
    import requests
    if not all((token, account, database)):
        raise RuntimeError("Identifiants Cloudflare D1 manquants")
    endpoint = f"https://api.cloudflare.com/client/v4/accounts/{account}/d1/database/{database}/query"
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    # Preserve order: switch remains off until all valid links are in D1.
    for q in queries:
        response = requests.post(endpoint, headers=headers, json=q, timeout=35)
        if not response.ok:
            raise RuntimeError("Cloudflare D1 a refusé une opération (HTTP " + str(response.status_code) + ")")
        data = response.json()
        if data.get("success") is not True or not all(v.get("success", False) for v in data.get("result", [])):
            raise RuntimeError("Cloudflare D1 n'a pas confirmé l'opération")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--toggle-only", action="store_true")
    parser.add_argument("--report")
    args = parser.parse_args()
    enabled = github_enabled()
    credentials = {
        "token": os.getenv("CLOUDFLARE_API_TOKEN", ""),
        "account": os.getenv("CLOUDFLARE_ACCOUNT_ID", ""),
        "database": os.getenv("CINERADAR_D1_DATABASE_ID", ""),
    }
    if args.toggle_only:
        d1_execute(toggle_queries(enabled), **credentials)
        print("CinéX : interrupteur GitHub synchronisé (" + str(enabled).lower() + ")")
        return
    if not args.report:
        parser.error("--report est requis pour la réconciliation")
    if not enabled:
        d1_execute(toggle_queries(False), **credentials)
        print("CinéX : désactivé par GitHub")
        return
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    links = eligible_links(report)
    d1_execute(queries_for_report(report), **credentials)
    print(f"CinéX : inventaire réconcilié; {len(links)} films/saisons vérifiés et indexés")


if __name__ == "__main__":
    main()
