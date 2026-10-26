#!/usr/bin/env python3
"""Encrypted GitHub-backed JSON vault for small Actu Foot state.

The public repository stores only AES-256-GCM ciphertext. Read/write is restricted
to GitHub Actions with contents:write and ML_V2_HISTORY_KEY_B64. Every write uses
GitHub's blob SHA as an optimistic-concurrency precondition. Never log secrets.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

VAULT_PATH = "assets/data/private/actu_foot_state.aes.json"
AAD = b"mrxpronos:actu-foot:github-vault:v1"
KEY_CONTEXT = b"MrXPRONOS/ActuFoot/GitHubState/v1"
MAX_PLAINTEXT = 4_000_000


class VaultError(RuntimeError):
    pass


class VaultConflict(VaultError):
    pass


def derive_key(encoded: str | None = None) -> bytes:
    raw = (encoded if encoded is not None else os.getenv("ML_V2_HISTORY_KEY_B64", "")).strip()
    try:
        material = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise VaultError("Invalid encryption secret encoding") from exc
    if len(material) != 32:
        raise VaultError("History encryption secret must decode to 32 bytes")
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=KEY_CONTEXT
    ).derive(material)


def seal(document: dict[str, Any], key: bytes) -> str:
    if not isinstance(document, dict):
        raise VaultError("Only JSON objects are supported")
    clear = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(clear) > MAX_PLAINTEXT:
        raise VaultError("Encrypted GitHub state exceeds size budget")
    nonce = secrets.token_bytes(12)
    encrypted = AESGCM(key).encrypt(nonce, clear, AAD)
    return json.dumps({
        "format": "mrxpronos.aes256gcm.hkdf.v1",
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_b64": base64.b64encode(encrypted).decode("ascii"),
    }, sort_keys=True, separators=(",", ":")) + "\n"


def unseal(envelope: str, key: bytes) -> dict[str, Any]:
    try:
        record = json.loads(envelope)
        if record["format"] != "mrxpronos.aes256gcm.hkdf.v1":
            raise VaultError("Unsupported encrypted state format")
        nonce = base64.b64decode(record["nonce_b64"], validate=True)
        ciphertext = base64.b64decode(record["ciphertext_b64"], validate=True)
        if len(nonce) != 12 or len(ciphertext) > MAX_PLAINTEXT + 16:
            raise VaultError("Malformed encrypted state")
        clear = AESGCM(key).decrypt(nonce, ciphertext, AAD)
        document = json.loads(clear)
        if not isinstance(document, dict):
            raise VaultError("Encrypted state is not a JSON object")
        return document
    except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
        raise VaultError("Unreadable encrypted state") from exc
    except Exception as exc:
        if isinstance(exc, VaultError):
            raise
        raise VaultError("Failed to authenticate encrypted state") from exc


@dataclass(frozen=True)
class VaultSnapshot:
    data: dict[str, Any]
    sha: str | None


class GitHubVault:
    def __init__(self, *, repo: str | None = None, branch: str | None = None, token: str | None = None,
                 path: str = VAULT_PATH, session: requests.Session | None = None):
        self.repo = repo or os.getenv("GITHUB_REPOSITORY", "")
        self.branch = branch or os.getenv("GITHUB_REF_NAME", "main")
        self.token = token or os.getenv("GH_VAULT_TOKEN") or os.getenv("GITHUB_TOKEN", "")
        self.path = path
        self.session = session or requests.Session()
        self.key = derive_key()
        if not self.token or len(self.repo.split("/")) != 2 or not self.branch:
            raise VaultError("GitHub Actions repository/token/branch unavailable")
        if not self.path.startswith("assets/data/private/") or ".." in self.path:
            raise VaultError("Unsafe vault path")
        self.url = "https://api.github.com/repos/" + self.repo + "/contents/" + quote(self.path, safe="/")
        self.headers = {
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def read(self, *, allow_new: bool = False) -> VaultSnapshot:
        response = self.session.get(self.url, headers=self.headers, params={"ref": self.branch}, timeout=20)
        if response.status_code == 404 and allow_new:
            return VaultSnapshot({"version": 1, "publications": {}, "history": {}}, None)
        response.raise_for_status()
        meta = response.json()
        if meta.get("type") != "file" or meta.get("encoding") != "base64":
            raise VaultError("Unexpected GitHub contents response")
        envelope = base64.b64decode(meta["content"]).decode("utf-8")
        return VaultSnapshot(unseal(envelope, self.key), meta["sha"])

    def write(self, document: dict[str, Any], *, expected_sha: str | None, message: str) -> str:
        if not message:
            raise VaultError("Commit message required")
        envelope = seal(document, self.key)
        body = {"message": message, "branch": self.branch,
                "content": base64.b64encode(envelope.encode("utf-8")).decode("ascii")}
        if expected_sha:
            body["sha"] = expected_sha
        response = self.session.put(self.url, headers=self.headers, json=body, timeout=30)
        if response.status_code in (409, 422):
            raise VaultConflict("Encrypted state changed concurrently; re-read and retry")
        response.raise_for_status()
        return response.json()["content"]["sha"]

    def change(self, callback, *, message: str, allow_new: bool = False, max_attempts: int = 3):
        """Transactional compare-and-swap. Callback must be deterministic, without side effects."""
        for i in range(max_attempts):
            snap = self.read(allow_new=allow_new)
            updated = callback(json.loads(json.dumps(snap.data)))
            if not isinstance(updated, dict):
                raise VaultError("Update callback must return JSON object")
            if updated == snap.data:
                return snap
            try:
                sha = self.write(updated, expected_sha=snap.sha, message=message)
                return VaultSnapshot(updated, sha)
            except VaultConflict:
                if i == max_attempts - 1:
                    raise
        raise VaultConflict("Unable to save encrypted state")
