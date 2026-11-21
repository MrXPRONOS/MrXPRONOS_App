#!/usr/bin/env python3
"""CinéX T04: offline encrypted backup of FULL D1 SQL + integrity-checked local restore.

The public key is committed; the private key must NEVER enter GitHub, D1, Telegram
or GitHub Actions. No production import/write operations exist in this program.
Requires: cryptography (pinned by GitHub workflow).
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
import sqlite3
import struct
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b"CINEX-T04-SEALED-V1\x00"
LIMIT = 512 * 1024 * 1024  # hard limit on uncompressed SQL and archive size
REQUIRED = frozenset(("channels", "cine_series_jobs", "cine_owner_vault"))
INFO = b"cine-xpronos/t04/d1-sql-backup/v1"
DATABASE = "cinecanaux-directory"


def load_public(path):
    value = Path(path).read_text(encoding="utf-8").strip()
    if not value.startswith("x25519:"):
        raise ValueError("invalid_public_key_format")
    data = value.partition(":")[2]
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    if len(raw) != 32:
        raise ValueError("invalid_public_key_length")
    return X25519PublicKey.from_public_bytes(raw)


def derive(secret, salt):
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=INFO).derive(secret)


def check_database(conn):
    # A full D1 export must be executable and contain the essential catalogue
    # AND owner-vault schema; otherwise an incomplete dump is rejected.
    integrity = conn.execute("PRAGMA integrity_check").fetchone()
    if not integrity or integrity[0] != "ok":
        raise ValueError("sqlite_integrity_check_failed")
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )}
    missing = REQUIRED - tables
    if missing:
        raise ValueError("essential_tables_missing:" + ",".join(sorted(missing)))
    # Source and subscriber identifiers stay INSIDE encrypted payload only.
    counts = {}
    for name in sorted(tables):
        if not name.replace("_", "").isalnum():
            raise ValueError("unsafe_table_name")
        counts[name] = int(conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
    return counts


def apply_dump(sql, destination=None):
    if not sql or len(sql) > LIMIT:
        raise ValueError("invalid_dump_size")
    if b"ATTACH DATABASE" in sql.upper() or b"DETACH DATABASE" in sql.upper():
        raise ValueError("unsupported_sql_attachment")
    conn = sqlite3.connect(str(destination) if destination else ":memory:")
    try:
        conn.enable_load_extension(False)
        conn.executescript(sql.decode("utf-8-sig"))
        return check_database(conn)
    finally:
        conn.close()


def seal(sql_bytes, public):
    counts = apply_dump(sql_bytes)  # reject broken / incomplete D1 exports
    manifest = {
        "format": 1, "database": DATABASE,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "sql_sha256": hashlib.sha256(sql_bytes).hexdigest(),
        "sql_bytes": len(sql_bytes),
        "table_counts": counts,
        "media_bytes_included": False,
        "media_source_references_included": True,
    }
    meta = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    raw = struct.pack(">I", len(meta)) + meta + sql_bytes
    compressed = gzip.compress(raw, compresslevel=6)
    ephemeral = X25519PrivateKey.generate()
    from cryptography.hazmat.primitives import serialization as ser
    ephemeral_pub = ephemeral.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
    salt, nonce = os.urandom(16), os.urandom(12)
    head = MAGIC + ephemeral_pub + salt + nonce
    key = derive(ephemeral.exchange(public), salt)
    ciphertext = AESGCM(key).encrypt(nonce, compressed, head)
    # Assert that the newly produced encrypted bytes authenticate correctly.
    if AESGCM(key).decrypt(nonce, ciphertext, head) != compressed:
        raise ValueError("roundtrip_encrypt_failed")
    return head + ciphertext, manifest


def unseal(blob, private):
    if len(blob) < len(MAGIC) + 32 + 16 + 12 + 16 or not blob.startswith(MAGIC):
        raise ValueError("invalid_backup_format")
    at = len(MAGIC)
    ephemeral = X25519PublicKey.from_public_bytes(blob[at:at + 32])
    salt, nonce = blob[at + 32:at + 48], blob[at + 48:at + 60]
    head, ciphertext = blob[:at + 60], blob[at + 60:]
    key = derive(private.exchange(ephemeral), salt)
    try:
        compressed = AESGCM(key).decrypt(nonce, ciphertext, head)
    except InvalidTag as error:
        raise ValueError("invalid_private_key_or_modified_archive") from error
    # Stream bounded gzip decompression to prevent untrusted archive bombs.
    import zlib
    unzip = zlib.decompressobj(16 + zlib.MAX_WBITS)
    raw = unzip.decompress(compressed, LIMIT + 262144)
    if not unzip.eof or unzip.unconsumed_tail or len(raw) > LIMIT + 262143:
        raise ValueError("backup_payload_too_large_or_truncated")
    raw += unzip.flush()
    if len(raw) < 5:
        raise ValueError("invalid_backup_payload")
    length = struct.unpack(">I", raw[:4])[0]
    if length > 262144 or len(raw) < 4 + length:
        raise ValueError("invalid_backup_manifest")
    manifest = json.loads(raw[4:4 + length])
    sql = raw[4 + length:]
    if manifest.get("format") != 1 or manifest.get("database") != DATABASE:
        raise ValueError("wrong_backup_source")
    if len(sql) != manifest.get("sql_bytes") or hashlib.sha256(sql).hexdigest() != manifest.get("sql_sha256"):
        raise ValueError("backup_checksum_mismatch")
    return sql, manifest


def write_new(path, content):
    path = Path(path)
    if path.exists():
        raise ValueError("output_already_exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    cmd = parser.add_subparsers(dest="command", required=True)
    enc = cmd.add_parser("encrypt", help="encrypt full SQL export to offline public key")
    enc.add_argument("--sql", required=True)
    enc.add_argument("--public-key", required=True)
    enc.add_argument("--out", required=True)
    dec = cmd.add_parser("restore-local", help="decrypt ONLY to a NEW local SQLite database")
    dec.add_argument("--archive", required=True)
    dec.add_argument("--private-key", required=True)
    dec.add_argument("--out", required=True)
    verify = cmd.add_parser("verify-local", help="decrypt and validate in memory; never writes production D1")
    verify.add_argument("--archive", required=True)
    verify.add_argument("--private-key", required=True)
    args = parser.parse_args(argv)
    if args.command == "encrypt":
        sql = Path(args.sql).read_bytes()
        ciphertext, manifest = seal(sql, load_public(args.public_key))
        write_new(args.out, ciphertext)
        print("T04_BACKUP_SEALED_VALID", "tables", len(manifest["table_counts"]),
              "size_bytes", len(ciphertext), "videos_included", False)
        return 0
    key = serialization.load_pem_private_key(Path(args.private_key).read_bytes(), password=None)
    if not isinstance(key, X25519PrivateKey):
        raise ValueError("incorrect_private_key_type")
    sql, manifest = unseal(Path(args.archive).read_bytes(), key)
    if args.command == "verify-local":
        actual = apply_dump(sql)
        if actual != manifest["table_counts"]:
            raise ValueError("backup_table_count_mismatch")
        print("T04_RESTORE_VERIFIED", "tables", len(actual), "sqlite_integrity", "ok")
        return 0
    target = Path(args.out)
    if target.exists():
        raise ValueError("output_already_exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".cinex-restore-", suffix=".sqlite", dir=target.parent)
    os.close(fd)
    os.chmod(temp, 0o600)
    try:
        actual = apply_dump(sql, temp)
        if actual != manifest["table_counts"]:
            raise ValueError("backup_table_count_mismatch")
        if target.exists():
            raise ValueError("output_already_exists")
        os.link(temp, target)  # fails if destination already exists
    finally:
        Path(temp).unlink(missing_ok=True)
    print("T04_LOCAL_RESTORE_VERIFIED", "tables", len(actual),
          "production_modified", False, "media_bytes_present", False)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, sqlite3.Error, UnicodeError) as error:
        # Never print the dump, private key or data-bearing DB statements.
        print("T04_BACKUP_ERROR", type(error).__name__, file=sys.stderr)
        sys.exit(1)
