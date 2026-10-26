"""Atomic multi-collection GitHub transactions for the encrypted Actu Foot V3 vault.

Git's tree+commit and non-forced fast-forward ref update expose one complete
snapshot of all changed files or none. Rejected competing writers retry from
a NEW head and re-apply pure, side-effect-free mutation functions.
This is NOT a real-time message delivery coordinator.
"""
from __future__ import annotations

import base64
import copy
import re
from dataclasses import dataclass
from typing import Callable

import requests

from scripts.actu_foot_github_vault import VaultError, VaultConflict
from scripts.actu_foot_v2_store import (
    COLLECTIONS, collection_path, encrypt, decrypt, validate_records,
    verify_audit, append_audit,
)

SHA_RE = re.compile(r"^[a-f0-9]{40}$")


@dataclass
class FileState:
    data: dict
    generation: int
    key_version: int
    exists: bool


class GitAtomicStore:
    def __init__(self, *, repo: str, branch: str = "main", token: str,
                 session: requests.Session | None = None):
        if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
                or not re.fullmatch(r"[A-Za-z0-9_.\-/]{1,120}", branch)
                or not token or branch != "main"):
            raise VaultError("Invalid or unsupported GitHub atomic store credentials")
        self.repo, self.branch = repo, branch
        self.session = session or requests.Session()
        self.root = "https://api.github.com/repos/" + repo
        self.headers = {"Authorization": "Bearer " + token,
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28"}

    def _request(self, method: str, endpoint: str, *, json=None, params=None):
        response = self.session.request(
            method, self.root + endpoint, json=json, params=params,
            headers=self.headers, timeout=(8, 35),
        )
        if response.status_code in (409, 422):
            raise VaultConflict("GitHub branch/tree conflict")
        response.raise_for_status()
        return response.json()

    def head(self) -> tuple[str, str]:
        ref = self._request("GET", "/git/ref/heads/" + self.branch)
        commit_sha = ref["object"]["sha"]
        if not SHA_RE.fullmatch(commit_sha):
            raise VaultError("Unexpected GitHub head SHA")
        commit = self._request("GET", "/git/commits/" + commit_sha)
        tree_sha = commit["tree"]["sha"]
        if not SHA_RE.fullmatch(tree_sha):
            raise VaultError("Unexpected GitHub tree SHA")
        return commit_sha, tree_sha

    def read_envelope(self, path: str, head_sha: str) -> str | None:
        from urllib.parse import quote
        if not SHA_RE.fullmatch(head_sha):
            raise VaultError("Invalid snapshot SHA")
        response = self.session.request(
            "GET", self.root + "/contents/" + quote(path, safe="/"),
            params={"ref": head_sha}, headers=self.headers, timeout=(8, 35),
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        body = response.json()
        if body.get("type") != "file" or body.get("encoding") != "base64":
            raise VaultError("Unexpected repository file type")
        return base64.b64decode("".join(body["content"].split()), validate=True).decode("utf-8")

    def load_collection(self, collection: str, head_sha: str) -> FileState:
        if collection not in COLLECTIONS:
            raise VaultError("Unknown collection")
        blob = self.read_envelope(collection_path(collection), head_sha)
        if blob is None:
            return FileState({}, 0, 1, False)
        records, header = decrypt(collection, blob)
        if collection == "audit":
            verify_audit(records)
        return FileState(records, header["generation"], header["key_version"], True)

    def commit(self, parent: str, base_tree: str, changes: dict[str, str],
               *, message: str) -> str:
        """Commit only encrypted envelopes, never plaintext; no forced ref update."""
        if not changes or not isinstance(message, str) or not message.startswith("ops(actu-foot-v3):"):
            raise VaultError("Empty/unapproved encrypted transaction")
        if not SHA_RE.fullmatch(parent) or not SHA_RE.fullmatch(base_tree):
            raise VaultError("Invalid commit ancestry")
        tree_changes = []
        for path, value in sorted(changes.items()):
            if (not path.startswith("assets/data/private/actufoot_v2/")
                    or not path.endswith(".aes.json")
                    or ".." in path or "//" in path or not isinstance(value, str)):
                raise VaultError("Unsafe encrypted document path")
            # Only known collection paths or known V3 archive paths.
            if path not in {collection_path(n) for n in COLLECTIONS}:
                from scripts.actu_foot_v3_archive import validate_archive_path
                validate_archive_path(path)
            tree_changes.append({"path": path, "mode": "100644",
                                 "type": "blob", "content": value})
        tree = self._request("POST", "/git/trees", json={
            "base_tree": base_tree, "tree": tree_changes,
        })
        commit = self._request("POST", "/git/commits", json={
            "message": message, "tree": tree["sha"], "parents": [parent],
        })
        target = commit["sha"]
        if not SHA_RE.fullmatch(target):
            raise VaultError("Unexpected new commit SHA")
        self._request("PATCH", "/git/refs/heads/" + self.branch,
                      json={"sha": target, "force": False})
        return target

    def transact(self, changes: dict[str, list[dict]], *, attempts: int = 4,
                 add_audit: bool = True) -> str | None:
        from scripts.actu_foot_v3_engine import apply_batch
        if not changes or set(changes) - (set(COLLECTIONS) - {"audit"}):
            raise VaultError("Empty transaction or unauthorized audit mutations")
        if type(attempts) is not int or not 1 <= attempts <= 8:
            raise VaultError("Invalid retry bound")
        for attempt in range(attempts):
            parent, tree = self.head()
            proposed = {}
            for name, operations in sorted(changes.items()):
                old = self.load_collection(name, parent)
                new = apply_batch(name, old.data, operations)
                if old.data != new:
                    proposed[collection_path(name)] = encrypt(
                        name, new, generation=old.generation+1, key_version=old.key_version)
            if not proposed:
                return None
            if add_audit:
                audit = self.load_collection("audit", parent)
                info = {"collections": sorted(changes),
                        "count": sum(len(v) for v in changes.values())}
                entries = append_audit(audit.data, "v3_batch_commit", info)
                proposed[collection_path("audit")] = encrypt(
                    "audit", entries, generation=audit.generation+1,
                    key_version=audit.key_version)
            try:
                return self.commit(parent, tree, proposed, message="ops(actu-foot-v3): atomic batch")
            except VaultConflict:
                if attempt+1 == attempts:
                    raise
        raise VaultConflict("Retry budget exhausted")
