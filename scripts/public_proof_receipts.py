"""Public, append-only pre-kickoff prediction receipts for the GitHub Pages build.

A receipt is written on the FIRST Pages build containing a future selection.
GitHub's gh-pages file commit history supplies the external audit timestamp.
Do not use internal first-observed times as independent publication evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import shutil

MINIMUM_PUBLICATION_LEAD = timedelta(minutes=15)
REPO = "MrXPRONOS/MrXPRONOS_App"


def utc_date(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        value = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def canonical(payload):
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(payload):
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def identity(match_id, key):
    return f"{match_id}:{key}"


def receipt_filename(match_id, key):
    return hashlib.sha256(identity(match_id, key).encode("utf-8")).hexdigest()[:32] + ".json"


def validate_receipt(receipt, expected_name=None):
    if not isinstance(receipt, dict) or receipt.get("schema") != "mx-public-proof-v1":
        raise ValueError("Invalid public proof schema")
    content = receipt.get("snapshot")
    if not isinstance(content, dict) or receipt.get("sha256") != digest(content):
        raise ValueError("Proof digest mismatch")
    if any(key not in content for key in ("id", "recorded_at_utc", "kickoff_utc", "selection")):
        raise ValueError("Proof missing mandatory field")
    publication = utc_date(content["recorded_at_utc"])
    kickoff = utc_date(content["kickoff_utc"])
    if not publication or not kickoff or publication + MINIMUM_PUBLICATION_LEAD >= kickoff:
        raise ValueError("Receipt not recorded before cutoff")
    key = content["id"]
    if not isinstance(key, str) or ":" not in key:
        raise ValueError("Invalid proof identity")
    selection_key = key.rsplit(":", 1)[1]
    match_id = key[:-(len(selection_key) + 1)]
    if expected_name and receipt_filename(match_id, selection_key) != expected_name:
        raise ValueError("Proof filename does not match immutable selection identity")
    return key


def selections(match):
    picks = match.get("predictions")
    if not isinstance(picks, list) or not picks:
        picks = [match.get("prediction")]
    used = set()
    for ix, pick in enumerate(picks):
        if not isinstance(pick, dict):
            continue
        key = str(pick.get("selection_key") or ("primary" if ix == 0 else f"secondary-{ix}"))
        if key in used:
            continue
        used.add(key)
        yield key, pick


def build_proofs(destination: Path, previous: Path | None, public_data: dict, now=None):
    """Preserve old receipts byte for byte, add only eligible FUTURE selections."""
    now = now or datetime.now(timezone.utc)
    receipt_dir = destination / "proofs" / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)

    old = previous / "proofs" / "receipts" if previous else None
    if old and old.is_dir():
        for path in old.glob("*.json"):
            if not path.is_file() or not re.fullmatch(r"[0-9a-f]{32}\.json", path.name):
                continue
            content = json.loads(path.read_text(encoding="utf-8"))
            validate_receipt(content, path.name)
            target = receipt_dir / path.name
            if target.exists() and target.read_bytes() != path.read_bytes():
                raise ValueError("Attempt to mutate existing publication proof")
            if not target.exists():
                shutil.copy2(path, target)

    for match in public_data.get("matches", []):
        kickoff = utc_date(match.get("event_date"))
        if (not kickoff or now + MINIMUM_PUBLICATION_LEAD >= kickoff or
                match.get("is_finished") or match.get("combo_only")):
            continue
        match_id = match.get("id", "")
        if not isinstance(match_id, str) or not match_id.startswith("match-"):
            continue
        for selection_key, pick in selections(match):
            filename = receipt_filename(match_id, selection_key)
            target = receipt_dir / filename
            if target.exists():
                continue
            snapshot = {
                "id": identity(match_id, selection_key),
                "recorded_at_utc": now.isoformat(timespec="seconds"),
                "kickoff_utc": kickoff.isoformat(timespec="seconds"),
                "fixture": {
                    "home_team": match.get("home_team", ""),
                    "away_team": match.get("away_team", ""),
                    "league": match.get("league", ""),
                },
                "category": match.get("category"),
                "selection": {
                    "selection_key": selection_key,
                    "type": pick.get("type", ""),
                    "confidence": pick.get("confidence"),
                    "odds": pick.get("odds"),
                    "estimated_odds": bool(pick.get("estimated_odds")),
                },
            }
            receipt = {"schema": "mx-public-proof-v1",
                       "snapshot": snapshot, "sha256": digest(snapshot)}
            validate_receipt(receipt, filename)
            target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")

    manifest = {}
    for file in sorted(receipt_dir.glob("*.json")):
        proof = json.loads(file.read_text(encoding="utf-8"))
        key = validate_receipt(proof, file.name)
        recorded = proof["snapshot"]["recorded_at_utc"]
        manifest[key] = {
            "recorded_at_utc": recorded,
            "kickoff_utc": proof["snapshot"]["kickoff_utc"],
            "sha256": proof["sha256"],
            "receipt_url": f"proofs/receipts/{file.name}",
            "github_history_url": f"https://github.com/{REPO}/commits/gh-pages/proofs/receipts/{file.name}",
        }
    output = destination / "proofs" / "index.json"
    output.write_text(json.dumps({"schema": "mx-public-proof-index-v1",
                                   "receipts": manifest}, ensure_ascii=False,
                                  separators=(",", ":")) + "\n", encoding="utf-8")
    return len(manifest)
