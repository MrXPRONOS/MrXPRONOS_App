"""Actu Foot V2: authenticated, modular, versioned encrypted GitHub storage.

This is an offline-first foundation, not a realtime transaction database.
Writes and backup promotions use SHA compare-and-swap. No Telegram integration.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import os
import re
import secrets
import zlib
from datetime import datetime, timezone
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from scripts.actu_foot_github_vault import GitHubVault, VaultError, VaultConflict

COLLECTIONS = ("matches", "live_events", "publications", "news", "statistics", "settings", "audit")
PREFIX = "assets/data/private/actufoot_v2"
FORMAT = "mrxp.actufoot.v2.aes256gcm"
MAX_BYTES = 2_000_000
MAX_ITEMS = 5000
MAX_UNCOMPRESSED = 2_000_000
SCHEMA_VERSION = 2


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha(obj: Any) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def validate_name(name: str) -> str:
    if name not in COLLECTIONS:
        raise VaultError("Unknown V2 collection")
    return name


def validate_records(collection: str, records: Any) -> dict:
    validate_name(collection)
    if not isinstance(records, dict) or len(records) > MAX_ITEMS:
        raise VaultError("Collection must be a bounded object")
    if len(canonical(records)) > MAX_BYTES:
        raise VaultError("Collection too large; archive or shard before writing")
    for key, record in records.items():
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9:_./-]{1,180}", key):
            raise VaultError("Invalid record key")
        if not isinstance(record, dict) or not record:
            raise VaultError("Records must be nonempty JSON objects")
        if collection in {"matches", "live_events"}:
            if not isinstance(record.get("home_team"), str) or not isinstance(record.get("away_team"), str):
                raise VaultError("Football fixture requires team names")
            if not record["home_team"].strip() or not record["away_team"].strip():
                raise VaultError("Empty football team")
            for field in ("home_score", "away_score"):
                if field in record and (type(record[field]) is not int or not 0 <= record[field] <= 30):
                    raise VaultError("Invalid football score")
        elif collection == "publications":
            if record.get("status") not in {"pending", "claimed", "sent", "failed", "uncertain", "archived"}:
                raise VaultError("Invalid publication state")
        elif collection == "audit":
            for field in ("sequence", "previous_hash", "entry_hash", "operation", "occurred_at"):
                if field not in record:
                    raise VaultError("Incomplete audit entry")
    return records


def master_key(version: int) -> bytes:
    if type(version) is not int or not 1 <= version <= 9999:
        raise VaultError("Invalid key version")
    # V2 can have its own master; legacy secret is used solely as a migration option.
    raw = os.getenv(f"ACTU_FOOT_V2_KEY_B64_V{version}", "").strip()
    if not raw and version == 1:
        raw = os.getenv("ACTU_FOOT_V2_KEY_B64", "").strip() or os.getenv("ML_V2_HISTORY_KEY_B64", "").strip()
    try:
        key = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise VaultError("Missing or malformed encryption key") from exc
    if len(key) != 32:
        raise VaultError("V2 master key must contain exactly 32 bytes")
    return key


def derive(collection: str, version: int) -> bytes:
    name = validate_name(collection)
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                info=f"MrXPRONOS/ActuFoot/v2/{name}/key/{version}".encode()).derive(master_key(version))


def encrypt(collection: str, records: dict, *, key_version: int = 1, generation: int = 1) -> str:
    validate_records(collection, records)
    if type(generation) is not int or generation < 1:
        raise VaultError("Invalid generation")
    header = {"format": FORMAT, "collection": collection,
              "schema_version": SCHEMA_VERSION, "key_version": key_version,
              "generation": generation}
    clear = canonical(records)
    compressed = zlib.compress(clear, level=6)
    codec, payload = ("zlib", compressed) if len(compressed) < len(clear) else ("none", clear)
    header["codec"] = codec
    nonce = secrets.token_bytes(12)
    blob = AESGCM(derive(collection, key_version)).encrypt(nonce, payload, canonical(header))
    return json.dumps({**header, "nonce_b64": base64.b64encode(nonce).decode(),
                       "ciphertext_b64": base64.b64encode(blob).decode()},
                      sort_keys=True, separators=(",", ":")) + "\n"


def decrypt(collection: str, envelope: str) -> tuple[dict, dict]:
    validate_name(collection)
    try:
        obj = json.loads(envelope)
        header = {k: obj[k] for k in
                  ("format", "collection", "schema_version", "key_version", "generation", "codec")}
        if (header["format"] != FORMAT or header["collection"] != collection
                or header["schema_version"] != SCHEMA_VERSION
                or header["codec"] not in {"zlib", "none"}
                or type(header["generation"]) is not int or header["generation"] < 1):
            raise VaultError("V2 envelope identity/version mismatch")
        nonce = base64.b64decode(obj["nonce_b64"], validate=True)
        blob = base64.b64decode(obj["ciphertext_b64"], validate=True)
        if len(nonce) != 12 or len(blob) > MAX_UNCOMPRESSED + 2048:
            raise VaultError("Invalid V2 envelope size")
        payload = AESGCM(derive(collection, header["key_version"])).decrypt(
            nonce, blob, canonical(header))
        if header["codec"] == "zlib":
            d = zlib.decompressobj()
            payload = d.decompress(payload, MAX_UNCOMPRESSED + 1)
            if not d.eof or d.unconsumed_tail or d.unused_data:
                raise VaultError("Invalid compressed content")
        if len(payload) > MAX_UNCOMPRESSED:
            raise VaultError("Decompressed collection too large")
        records = json.loads(payload)
        validate_records(collection, records)
        return records, header
    except (InvalidTag, ValueError, TypeError, KeyError, UnicodeDecodeError, zlib.error) as exc:
        raise VaultError("V2 authentication, decoding or validation failed") from exc


def collection_path(collection: str) -> str:
    return f"{PREFIX}/{validate_name(collection)}.aes.json"


class CollectionVault:
    def __init__(self, collection: str, *, repo: str | None = None,
                 branch: str | None = None, token: str | None = None, session=None):
        self.collection = validate_name(collection)
        self.backend = GitHubVault(repo=repo, branch=branch, token=token,
                                   path=collection_path(collection), session=session)

    def read(self, *, allow_new: bool = False):
        response = self.backend.session.get(self.backend.url, headers=self.backend.headers,
                                            params={"ref": self.backend.branch}, timeout=20)
        if response.status_code == 404 and allow_new:
            return {}, None, {"generation": 0, "key_version": 1}
        response.raise_for_status()
        doc = response.json()
        if doc.get("type") != "file" or doc.get("encoding") != "base64" or not doc.get("sha"):
            raise VaultError("Unexpected GitHub response")
        envelope = base64.b64decode(doc["content"], validate=True).decode()
        records, header = decrypt(self.collection, envelope)
        return records, doc["sha"], header

    def write(self, records: dict, *, expected_sha: str | None, generation: int,
              key_version: int = 1, message: str = "ops(actu-foot): update encrypted collection") -> str:
        envelope = encrypt(self.collection, records, generation=generation, key_version=key_version)
        body = {"message": message, "branch": self.backend.branch,
                "content": base64.b64encode(envelope.encode()).decode()}
        if expected_sha:
            body["sha"] = expected_sha
        response = self.backend.session.put(self.backend.url, headers=self.backend.headers,
                                            json=body, timeout=30)
        if response.status_code in (409, 422):
            raise VaultConflict("Concurrent collection update, reload before retry")
        response.raise_for_status()
        return response.json()["content"]["sha"]

    def update(self, callback, *, max_attempts: int = 3, allow_new: bool = False):
        for attempt in range(max_attempts):
            records, commit_sha, header = self.read(allow_new=allow_new)
            modified = callback(copy.deepcopy(records))
            validate_records(self.collection, modified)
            if modified == records:
                return commit_sha
            try:
                return self.write(modified, expected_sha=commit_sha,
                                  generation=header["generation"] + 1,
                                  key_version=header["key_version"])
            except VaultConflict:
                if attempt + 1 == max_attempts:
                    raise
        raise VaultConflict("Failed optimistic update")

    def rotate(self, new_version: int) -> str:
        records, commit_sha, header = self.read()
        if new_version <= header["key_version"]:
            raise VaultError("Rotation must advance key version")
        # Validate the new key before writing. Never retire the old key before backups.
        derive(self.collection, new_version)
        return self.write(records, expected_sha=commit_sha,
                          generation=header["generation"] + 1, key_version=new_version,
                          message="ops(actu-foot): rotate encrypted collection key")


def new_audit_entry(sequence: int, previous_hash: str, operation: str,
                    details: dict, *, when: str | None = None) -> dict:
    if type(sequence) is not int or sequence < 1 or not operation or len(operation) > 80:
        raise VaultError("Invalid audit operation")
    if not isinstance(details, dict):
        raise VaultError("Audit details must be a JSON object")
    body = {"sequence": sequence, "previous_hash": previous_hash,
            "operation": operation, "details": details, "occurred_at": when or utc_now()}
    body["entry_hash"] = sha(body)
    return body


def verify_audit(entries: dict) -> bool:
    validate_records("audit", entries)
    previous = "0" * 64
    for number, item in enumerate(sorted(entries.values(), key=lambda e: e["sequence"]), 1):
        if item["sequence"] != number or item["previous_hash"] != previous:
            raise VaultError("Broken audit sequence")
        body = {k: v for k, v in item.items() if k != "entry_hash"}
        if not hmac.compare_digest(sha(body), item["entry_hash"]):
            raise VaultError("Tampered audit entry")
        previous = item["entry_hash"]
    return True


def append_audit(entries: dict, operation: str, details: dict) -> dict:
    verify_audit(entries)
    last = max(entries.values(), key=lambda x: x["sequence"]) if entries else None
    seq = last["sequence"] + 1 if last else 1
    event = new_audit_entry(seq, last["entry_hash"] if last else "0" * 64,
                            operation, details)
    return {**entries, str(seq): event}


def backup_bundle(collection: str, records: dict, generation: int,
                  *, key_version: int = 1) -> str:
    """Self-contained encrypted export. Stored off-repository by the operator."""
    return encrypt(collection, records, key_version=key_version, generation=generation)


def verify_backup(collection: str, backup: str):
    return decrypt(collection, backup)


def restore_backup(vault: CollectionVault, backup: str, *, expected_sha: str,
                   confirm: bool = False, minimum_generation: int = 0) -> str:
    """Explicitly guarded restoration; no silent overwrite or downgrade."""
    if not confirm or not expected_sha:
        raise VaultError("Restoration requires explicit confirmation and current SHA")
    saved, info = verify_backup(vault.collection, backup)
    _, current_sha, current = vault.read()
    if current_sha != expected_sha:
        raise VaultConflict("Storage has changed since restoration approval")
    if info["generation"] < minimum_generation:
        raise VaultError("Backup generation below approved minimum")
    return vault.write(saved, expected_sha=current_sha,
                       generation=current["generation"] + 1,
                       key_version=current["key_version"],
                       message="ops(actu-foot): restore verified encrypted backup")
