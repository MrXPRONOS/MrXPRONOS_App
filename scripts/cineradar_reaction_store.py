"""CineRadar reaction state: authenticated encryption and GitHub-only persistence.

No D1 or Telegram calls here. No implicit empty-state recovery on read failure.
The caller must import a validated snapshot before activating a replacement runner.
"""
from __future__ import annotations

import base64
import binascii
import sqlite3
import zlib

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from scripts.actu_foot_github_vault import GitHubVault, VaultError

PATH = "assets/data/private/cineradar/reactions.aes.json"
CONTEXT = b"MrXPRONOS/CineRadar/Reactions/GitHubState/v1"
FORMAT = "cineradar-reactions-sqlite-v1"
MAX_DB_BYTES = 16_000_000
MAX_COMPRESSED_BYTES = 2_500_000
REQUIRED = frozenset({
    "channel_reaction_posts",
    "channel_reaction_jobs",
    "channel_reaction_extra_jobs",
    "channel_reaction_extra_bot_activation",
    "channel_reaction_terminal_posts",
})


def safe_decompress(compressed):
    obj = zlib.decompressobj()
    data = obj.decompress(compressed, MAX_DB_BYTES + 1)
    if len(data) > MAX_DB_BYTES or obj.unconsumed_tail or not obj.eof:
        raise VaultError("Reaction snapshot exceeds size limit")
    return data


class ReactionVault(GitHubVault):
    """Reuse the existing vault protocol, with a separate subkey and file."""
    def __init__(self, **kwargs):
        super().__init__(path=PATH, **kwargs)
        self.key = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None, info=CONTEXT,
        ).derive(self.key)


def validate_database(db: sqlite3.Connection) -> None:
    tables = {r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    if not REQUIRED <= tables:
        raise VaultError("Incomplete reaction snapshot")
    if [row[0] for row in db.execute("PRAGMA quick_check").fetchall()] != ["ok"]:
        raise VaultError("Reaction snapshot integrity check failed")
    if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise VaultError("Reaction snapshot has orphaned jobs")


def pack(db: sqlite3.Connection, *, observer_offset: int | None = None) -> dict:
    validate_database(db)
    if observer_offset is not None and (type(observer_offset) is not int or observer_offset < 0):
        raise VaultError("Invalid observer cursor")
    raw = db.serialize()
    compressed = zlib.compress(raw, level=9)
    if len(raw) > MAX_DB_BYTES or len(compressed) > MAX_COMPRESSED_BYTES:
        raise VaultError("Reaction state exceeds encrypted GitHub file budget; shard before activation")
    return {
        "version": 1, "format": FORMAT,
        "sqlite_zlib_b64": base64.b64encode(compressed).decode("ascii"),
        "observer_offset": observer_offset,
    }


def unpack(document: dict) -> tuple[sqlite3.Connection, int | None]:
    if document.get("version") != 1 or document.get("format") != FORMAT:
        raise VaultError("Invalid CineRadar state format")
    try:
        compressed = base64.b64decode(document["sqlite_zlib_b64"], validate=True)
        if len(compressed) > MAX_COMPRESSED_BYTES:
            raise VaultError("Invalid compressed reaction database size")
        raw = safe_decompress(compressed)
        offset = document["observer_offset"]
    except (KeyError, ValueError, TypeError, binascii.Error) as exc:
        raise VaultError("Invalid CineRadar state encoding") from exc
    if len(raw) > MAX_DB_BYTES or not raw.startswith(b"SQLite format 3\x00"):
        raise VaultError("Invalid reaction database bytes")
    if offset is not None and (type(offset) is not int or offset < 0):
        raise VaultError("Invalid observer cursor")
    db = sqlite3.connect(":memory:")
    try:
        db.deserialize(raw)
        validate_database(db)
        db.execute("PRAGMA foreign_keys=ON")
        return db, offset
    except Exception:
        db.close()
        raise


class LocalReactionDB:
    """Local SQL adapter for the existing queue logic; nothing accesses D1."""
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row

    def query(self, sql, params=()):
        with self.connection:
            cursor = self.connection.execute(sql, params)
            results = [dict(row) for row in cursor.fetchall()] if cursor.description else []
        return {"success": True, "results": results}

    def batch(self, updates):
        with self.connection:
            for sql, params in updates:
                self.connection.execute(sql, params)


def load(vault: ReactionVault):
    snapshot = vault.read(allow_new=False)
    connection, offset = unpack(snapshot.data)
    return LocalReactionDB(connection), offset, snapshot.sha


def save(vault: ReactionVault, db: LocalReactionDB, offset: int | None, expected_sha: str):
    if not expected_sha:
        raise VaultError("Missing snapshot version; refusing implicit initialization")
    return vault.write(
        pack(db.connection, observer_offset=offset),
        expected_sha=expected_sha, message="data(cineradar): encrypted reaction state",
    )
