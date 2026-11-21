#!/usr/bin/env python3
"""CinéX T04: GitHub-first encrypted backup of existing CinéX catalogues & files.

This never fetches Telegram videos or starts a Telegram personal session.
The source repository may be public: do NOT add private/copyrighted media to
Git history. Only existing, explicitly selected project files are included.
The offline private recovery key is NEVER needed to produce the archive.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b"CINEX-T04-GITHUB-FILES-V1\x00"
INFO = b"cinex/t04/github-files/v1"
MAX_TOTAL = 128 * 1024 * 1024  # 128 MiB of original files; refuse oversized archives
MAX_ONE = 48 * 1024 * 1024  # per item
MAX_FILES = 4000
MEDIA = frozenset((".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi"))
IMAGE = frozenset((".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"))
ROOTS = (
    "telegram-film-relay/state",
    "telegram-film-relay/config",
    "telegram-film-relay/assets",
    "cinecanaux/assets",
)
JSON = frozenset((".json",))


def load_public(path):
    value = Path(path).read_text(encoding="utf-8").strip()
    if not value.startswith("x25519:"):
        raise ValueError("invalid_public_key")
    raw_text = value.split(":", 1)[1]
    raw = base64.urlsafe_b64decode(raw_text + "=" * (-len(raw_text) % 4))
    if len(raw) != 32:
        raise ValueError("invalid_public_key")
    return X25519PublicKey.from_public_bytes(raw)


def safe_name(name):
    path = PurePosixPath(name)
    return bool(name and "\\" not in name and not name.startswith("/") and
                all(p not in (".", "..") for p in name.split("/")) and
                len(path.parts) >= 2 and not any(x.startswith(".") for x in path.parts))


def selected_path(relative):
    if not safe_name(relative):
        return False
    if relative.startswith("telegram-film-relay/state/"):
        return PurePosixPath(relative).suffix.lower() in JSON
    if relative.startswith("telegram-film-relay/config/"):
        return PurePosixPath(relative).suffix.lower() in JSON
    if relative.startswith("telegram-film-relay/assets/"):
        return PurePosixPath(relative).suffix.lower() in IMAGE
    if relative.startswith("cinecanaux/assets/"):
        return PurePosixPath(relative).suffix.lower() in IMAGE | JSON
    return False


def discover(root):
    root = Path(root).resolve()
    found = []
    total = 0
    for folder in ROOTS:
        source = root / folder
        if not source.exists():
            continue
        if not source.is_dir() or source.is_symlink():
            raise ValueError("invalid_catalog_folder")
        for item in sorted(source.rglob("*")):
            if item.is_symlink():
                raise ValueError("symlink_in_backup_source")
            if not item.is_file():
                continue
            rel = item.relative_to(root).as_posix()
            if not selected_path(rel):
                continue
            size = item.stat().st_size
            if size > MAX_ONE:
                raise ValueError("individual_file_exceeds_policy")
            total += size
            if total > MAX_TOTAL or len(found) + 1 > MAX_FILES:
                raise ValueError("backup_size_or_file_count_exceeded")
            found.append((rel, item))
    if not found:
        raise ValueError("no_cinex_files_found")
    return sorted(found)


def seal(root, public):
    entries = discover(root)
    data = io.BytesIO()
    manifest = {
        "format": "cinex-github-files-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": "github-checked-out-project",
        "items": [],
    }
    with zipfile.ZipFile(data, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as out:
        for rel, path in entries:
            content = path.read_bytes()
            manifest["items"].append({
                "path": rel, "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
            })
            out.writestr(rel, content)
        out.writestr("manifest.json", json.dumps(manifest, sort_keys=True, separators=(",", ":")))
    plaintext = data.getvalue()
    if len(plaintext) > MAX_TOTAL + MAX_FILES * 1024:
        raise ValueError("zip_archive_exceeds_policy")
    eph = X25519PrivateKey.generate()
    ephemeral = eph.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    salt, nonce = os.urandom(16), os.urandom(12)
    header = MAGIC + ephemeral + salt + nonce
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=INFO).derive(eph.exchange(public))
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, header)
    return header + ciphertext, manifest


def inspect_archive(plaintext):
    with zipfile.ZipFile(io.BytesIO(plaintext)) as bundle:
        entries = bundle.infolist()
        if len(entries) > MAX_FILES + 1:
            raise ValueError("excess_files")
        if any(z.is_dir() or z.file_size > MAX_ONE or z.flag_bits & 1 for z in entries):
            raise ValueError("invalid_archived_file")
        if len(set(z.filename for z in entries)) != len(entries):
            raise ValueError("duplicate_archive_path")
        if "manifest.json" not in bundle.namelist():
            raise ValueError("missing_manifest")
        if bundle.getinfo("manifest.json").file_size > MAX_FILES * 256:
            raise ValueError("oversized_manifest")
        manifest = json.loads(bundle.read("manifest.json"))
        if manifest.get("format") != "cinex-github-files-v1":
            raise ValueError("wrong_backup_format")
        items = manifest.get("items")
        if not isinstance(items, list) or not 1 <= len(items) <= MAX_FILES:
            raise ValueError("empty_or_invalid_manifest")
        paths = set()
        total = 0
        for item in items:
            rel = item.get("path")
            if not isinstance(rel, str) or not selected_path(rel) or rel in paths:
                raise ValueError("unsafe_or_duplicate_path")
            paths.add(rel)
            content = bundle.read(rel)
            total += len(content)
            if total > MAX_TOTAL or len(content) != item.get("bytes") or (
                hashlib.sha256(content).hexdigest() != item.get("sha256")
            ):
                raise ValueError("file_integrity_error")
        if set(bundle.namelist()) != paths | {"manifest.json"}:
            raise ValueError("unexpected_archive_member")
        return manifest


def unseal(encrypted, private):
    if not encrypted.startswith(MAGIC) or len(encrypted) < len(MAGIC) + 32 + 16 + 12 + 16:
        raise ValueError("invalid_archive")
    pos = len(MAGIC)
    remote_pub = X25519PublicKey.from_public_bytes(encrypted[pos:pos + 32])
    salt, nonce = encrypted[pos + 32:pos + 48], encrypted[pos + 48:pos + 60]
    header = encrypted[:pos + 60]
    secret = private.exchange(remote_pub)
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=INFO).derive(secret)
    try:
        plaintext = AESGCM(key).decrypt(nonce, encrypted[pos + 60:], header)
    except InvalidTag as exc:
        raise ValueError("archive_signature_or_key_invalid") from exc
    inspect_archive(plaintext)
    return plaintext


def write_private_file(target, data):
    target = Path(target)
    if target.exists():
        raise ValueError("backup_destination_exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = os.open(target, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def restore_private(archive, target):
    target = Path(target)
    if target.exists():
        raise ValueError("restore_destination_exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".cinex-github-restore-", dir=target.parent))
    os.chmod(temp, 0o700)
    try:
        manifest = inspect_archive(archive)
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            for row in manifest["items"]:
                path = temp.joinpath(*PurePosixPath(row["path"]).parts)
                path.parent.mkdir(parents=True, exist_ok=True)
                write_private_file(path, bundle.read(row["path"]))
        if target.exists():
            raise ValueError("restore_destination_exists")
        temp.rename(target)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return manifest


def summary(manifest):
    files = manifest["items"]
    videos = [x for x in files if PurePosixPath(x["path"]).suffix.lower() in MEDIA]
    return {
        "files": len(files),
        "video_files": len(videos),
        "video_bytes": sum(x["bytes"] for x in videos),
        "total_original_bytes": sum(x["bytes"] for x in files),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="action", required=True)
    pack = subs.add_parser("pack", help="package project files into encrypted GitHub artifact")
    pack.add_argument("--root", required=True)
    pack.add_argument("--public-key", required=True)
    pack.add_argument("--out", required=True)
    for name in ("verify-local", "restore-local"):
        cmd = subs.add_parser(name)
        cmd.add_argument("--archive", required=True)
        cmd.add_argument("--private-key", required=True)
        if name == "restore-local":
            cmd.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.action == "pack":
        encrypted, manifest = seal(args.root, load_public(args.public_key))
        write_private_file(args.out, encrypted)
        print("CINEX_GITHUB_FILES_BACKUP_ENCRYPTED", json.dumps(summary(manifest)))
        return 0
    private = serialization.load_pem_private_key(Path(args.private_key).read_bytes(), password=None)
    if not isinstance(private, X25519PrivateKey):
        raise ValueError("invalid_private_key_type")
    archive = unseal(Path(args.archive).read_bytes(), private)
    if args.action == "verify-local":
        info = inspect_archive(archive)
    else:
        info = restore_private(archive, args.out)
    print("CINEX_GITHUB_FILES_RESTORE_OK", json.dumps(summary(info)))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, RuntimeError, zipfile.BadZipFile) as error:
        # Never expose recovered file contents, token values or chat identifiers.
        print("CINEX_GITHUB_FILES_BACKUP_ERROR", type(error).__name__, file=sys.stderr)
        sys.exit(1)
