"""Safely retrieve and verify a pinned GitHub Actions ciphertext backup.

Restore callers must supply an explicit artifact ID and an exact target file SHA.
Never extract untrusted ZIP paths; reject truncated, oversized and unexpected data.
"""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import re
import zipfile

import requests

from scripts.actu_foot_github_vault import VaultError
from scripts.actu_foot_v2_operations import verify_directory

API = "https://api.github.com"
MAX_ARCHIVE = 24_000_000
MAX_UNZIPPED = 18_000_000
MAX_FILES = 9
ARTIFACT_PREFIX = "actufoot-v2-encrypted-backup-"


def _headers(token: str) -> dict:
    if not token:
        raise VaultError("GitHub workflow token unavailable")
    return {"Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def fetch_artifact(artifact_id: int, target: Path, *, repo: str | None = None,
                   token: str | None = None, session=None) -> dict:
    repo = repo or os.getenv("GITHUB_REPOSITORY", "")
    token = token or os.getenv("GITHUB_TOKEN", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise VaultError("Invalid GitHub repository")
    if type(artifact_id) is not int or artifact_id < 1:
        raise VaultError("Explicit positive backup artifact ID required")
    http = session or requests.Session()
    path = f"{API}/repos/{repo}/actions/artifacts/{artifact_id}"
    response = http.get(path, headers=_headers(token), timeout=(8, 30))
    response.raise_for_status()
    meta = response.json()
    run = meta.get("workflow_run") or {}
    run_id = run.get("id")
    if (meta.get("expired") is not False or not isinstance(run_id, int)
            or meta.get("name") != ARTIFACT_PREFIX + str(run_id)
            or run.get("head_branch") != "main"
            or meta.get("size_in_bytes", 0) > MAX_ARCHIVE):
        raise VaultError("Artifact provenance, age or size rejected")

    # Only accept a confirmed successful run of the expected workflow.
    resp = http.get(f"{API}/repos/{repo}/actions/runs/{run_id}",
                    headers=_headers(token), timeout=(8, 30))
    resp.raise_for_status()
    run_meta = resp.json()
    if (run_meta.get("conclusion") != "success"
            or run_meta.get("head_branch") != "main"
            or run_meta.get("path") not in {
                ".github/workflows/actu-foot-v2-backup.yml",
                "actu-foot-v2-backup.yml",
            }
            or run_meta.get("event") not in {"workflow_dispatch", "schedule"}):
        raise VaultError("Backup was not produced by successful scheduled/approved workflow")

    resp = http.get(f"{path}/zip", headers=_headers(token), timeout=(8, 60),
                    stream=True)
    resp.raise_for_status()
    buf = io.BytesIO()
    for block in resp.iter_content(chunk_size=65536):
        if block:
            if buf.tell() + len(block) > MAX_ARCHIVE:
                raise VaultError("Backup archive exceeds limit")
            buf.write(block)
    buf.seek(0)
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(buf) as archive:
        files = archive.infolist()
        if not files or len(files) > MAX_FILES:
            raise VaultError("Unexpected number of backup members")
        total = 0
        names = set()
        for file in files:
            if (file.is_dir() or file.filename in names
                    or "/" in file.filename or "\\" in file.filename
                    or file.filename not in {"manifest.json",
                                            "matches.aes.json", "live_events.aes.json",
                                            "publications.aes.json", "news.aes.json",
                                            "statistics.aes.json", "settings.aes.json",
                                            "audit.aes.json"}
                    or (file.external_attr >> 16) & 0o170000 == 0o120000):
                raise VaultError("Unexpected backup member name or file type")
            total += file.file_size
            if total > MAX_UNZIPPED or file.file_size > 4_000_000:
                raise VaultError("Uncompressed backup exceeds safety limit")
            names.add(file.filename)
        if "manifest.json" not in names or len(names) < 2:
            raise VaultError("Backup missing data or manifest")
        for file in files:
            payload = archive.read(file.filename)
            if len(payload) != file.file_size:
                raise VaultError("Truncated backup member")
            destination = target / file.filename
            destination.write_bytes(payload)
            destination.chmod(0o600)
    manifest = verify_directory(target)
    # Avoid reuse of a plaintext or unrelated artifact.
    return {"artifact_id": artifact_id, "run_id": run_id,
            "collections": sorted(manifest["collections"])}
