"""Encrypted, versioned GitHub Contents store for Actu Foot.

All state bytes committed to the public repository are encrypted with AES-256-GCM.
A domain-separated subkey is derived from the existing ML_V2_HISTORY_KEY_B64.
The store uses GitHub's blob SHA optimistic concurrency (409 -> re-read/retry).
Do not use it for low-latency / high-write-volume workloads.
"""
from __future__ import annotations

import base64
import copy
import json
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests

FORMAT = "mrxp-actu-foot-encrypted-v1"
DEFAULT_PATH = ".github-data/actu-foot-v1.enc.json"
TABLES = {
    "actu_foot_publications", "actu_foot_live_events",
    "actu_foot_run_metrics", "actu_foot_provider_health",
    "actu_foot_source_snapshots", "actu_foot_news_snapshot",
    "live_stats_merged", "matches_live",
}
KEYS = {
    "actu_foot_publications": "event_key",
    "actu_foot_live_events": "event_key",
    "actu_foot_provider_health": "provider",
    "actu_foot_source_snapshots": "snapshot_key",
    "actu_foot_news_snapshot": "id",
}
_ALLOWED_RPC = {
    "actu_foot_claim_publication", "actu_foot_retryable_publications",
    "actu_foot_store_live_events",
}


def utc_now():
    return datetime.now(timezone.utc)


def moment(value):
    if not value:
        return None
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)
        return result.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def derive_key(encoded):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    try:
        raw = base64.b64decode(encoded.strip(), validate=True)
    except Exception as exc:
        raise ValueError("Invalid encrypted GitHub database key format") from exc
    if len(raw) != 32:
        raise ValueError("Encrypted GitHub database key must decode to 32 bytes")
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"MrXPRONOS:separate-github-store:v1",
        info=b"ActuFoot:github-contents:encrypted-json:v1",
    ).derive(raw)


def _empty():
    return {"version": 1, "tables": {}, "runtime_history": {}}


class EncryptedGithubDB:
    def __init__(self, session=None, *, token=None, encoded_key=None, repo=None, path=DEFAULT_PATH, branch="main"):
        self.session = session or requests.Session()
        self.token = token if token is not None else os.getenv("GITHUB_TOKEN", "")
        self.repo = repo if repo is not None else os.getenv("GITHUB_REPOSITORY", "")
        self.path = path
        self.branch = branch
        encoded = encoded_key if encoded_key is not None else os.getenv("ML_V2_HISTORY_KEY_B64", "")
        if not self.token or not encoded:
            raise RuntimeError("GitHub database credentials missing")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repo):
            raise ValueError("GitHub database repository invalid")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", self.path):
            raise ValueError("GitHub database path invalid")
        self.key = derive_key(encoded)
        self.url = "https://api.github.com/repos/" + self.repo + "/contents/" + quote(self.path, safe="/")
        self.aad = (FORMAT + ":" + self.repo + ":" + self.path).encode("utf-8")
        self.headers = {
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _encrypt(self, database):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = secrets.token_bytes(12)
        plaintext = json.dumps(database, separators=(",", ":"), ensure_ascii=False, sort_keys=True).encode("utf-8")
        ciphertext = AESGCM(self.key).encrypt(nonce, plaintext, self.aad)
        envelope = {
            "format": FORMAT,
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }
        return json.dumps(envelope, separators=(",", ":"), sort_keys=True)

    def _decrypt(self, payload):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        envelope = json.loads(payload)
        if not isinstance(envelope, dict) or envelope.get("format") != FORMAT:
            raise ValueError("Encrypted GitHub database format mismatch; refusing overwrite")
        try:
            nonce = base64.b64decode(envelope["nonce"], validate=True)
            data = base64.b64decode(envelope["ciphertext"], validate=True)
            if len(nonce) != 12:
                raise ValueError("Invalid nonce length")
            plain = AESGCM(self.key).decrypt(nonce, data, self.aad)
            database = json.loads(plain)
        except Exception as exc:
            raise ValueError("GitHub database authentication/decryption failed; refusing overwrite") from exc
        if not isinstance(database, dict) or database.get("version") != 1 or not isinstance(database.get("tables"), dict):
            raise ValueError("Decrypted GitHub database invalid")
        return database

    def read(self):
        response = self.session.get(
            self.url,
            params={"ref": self.branch},
            headers=self.headers,
            timeout=(8, 20),
        )
        if response.status_code == 404:
            return _empty(), None
        response.raise_for_status()
        result = response.json()
        raw = base64.b64decode(result["content"].replace("\n", ""), validate=True)
        return self._decrypt(raw.decode("utf-8")), str(result["sha"])

    def transact(self, modifier, *, purpose="update", max_attempts=5):
        """modifier(state) -> (changed, result), safe under competing writers."""
        last_conflict = None
        for attempt in range(max_attempts):
            original, sha = self.read()
            database = copy.deepcopy(original)
            changed, result = modifier(database)
            if not changed:
                return result
            self._prune(database)
            encrypted = self._encrypt(database)
            data = {
                "message": "data(actu-foot): encrypted " + re.sub(r"[^a-z0-9-]", "-", purpose.lower())[:48],
                "branch": self.branch,
                "content": base64.b64encode(encrypted.encode("utf-8")).decode("ascii"),
            }
            if sha is not None:
                data["sha"] = sha
            response = self.session.put(self.url, headers=self.headers, json=data, timeout=(8, 25))
            if response.status_code in (200, 201):
                return result
            if response.status_code in (409, 422):
                last_conflict = response.status_code
                time.sleep(min(0.25 * (attempt + 1), 1.25))
                continue
            response.raise_for_status()
            raise RuntimeError("GitHub database commit failed")
        raise RuntimeError("GitHub database compare-and-swap exhausted (" + str(last_conflict) + ")")

    @staticmethod
    def _prune(database):
        tables = database["tables"]
        now = utc_now()
        cutoff_pub = now - timedelta(days=40)
        cutoff_live = now - timedelta(days=3)
        for table, cutoff, date_key in (
            ("actu_foot_publications", cutoff_pub, "updated_at"),
            ("actu_foot_live_events", cutoff_live, "last_seen_at"),
        ):
            rows = tables.get(table, [])
            if isinstance(rows, list):
                tables[table] = [
                    row for row in rows if not moment(row.get(date_key)) or moment(row.get(date_key)) >= cutoff
                ][-3000:]
        for table, size in (("actu_foot_run_metrics", 40), ("actu_foot_source_snapshots", 6)):
            rows = tables.get(table, [])
            if isinstance(rows, list):
                tables[table] = rows[-size:]

    def _rows(self, db, table):
        if table not in TABLES:
            raise ValueError("GitHub database unauthorized table")
        return db.setdefault("tables", {}).setdefault(table, [])

    @staticmethod
    def _match(row, params):
        for name, value in params.items():
            if name in {"select", "limit", "order", "offset", "on_conflict"}:
                continue
            if not isinstance(value, str) or "." not in value:
                raise ValueError("Unsupported GitHub filter")
            op, needle = value.split(".", 1)
            actual = row.get(name)
            if op == "eq":
                if needle == "null":
                    ok = actual is None
                else:
                    ok = str(actual).lower() == needle.lower()
            elif op == "in":
                ok = str(actual) in needle.strip("()").split(",")
            elif op in {"gt", "gte", "lt", "lte"}:
                a, b = moment(actual), moment(needle)
                if a is not None and b is not None:
                    comp = (a > b) - (a < b)
                else:
                    a_text, b_text = str(actual), needle
                    comp = (a_text > b_text) - (a_text < b_text)
                ok = {"gt": comp > 0, "gte": comp >= 0, "lt": comp < 0, "lte": comp <= 0}[op]
            elif op == "neq":
                ok = str(actual) != needle
            else:
                raise ValueError("Unsupported GitHub filter op")
            if not ok:
                return False
        return True

    @classmethod
    def _selected(cls, rows, params):
        rows = [copy.deepcopy(row) for row in rows if cls._match(row, params)]
        order = str(params.get("order") or "")
        for part in reversed(order.split(",")):
            if not part:
                continue
            bits = part.strip().split(".")
            if len(bits) > 2 or len(bits) == 2 and bits[1] not in ("asc", "desc"):
                raise ValueError("Invalid GitHub sort")
            col = bits[0]
            rows.sort(key=lambda row: (row.get(col) is None, str(row.get(col) or "")),
                      reverse=(len(bits) == 2 and bits[1] == "desc"))
        offset = max(0, int(params.get("offset") or 0))
        limit = max(1, min(2000, int(params.get("limit") or 500)))
        selected = str(params.get("select") or "*")
        rows = rows[offset:offset + limit]
        if selected != "*":
            columns = [value.strip() for value in selected.split(",")]
            rows = [{key: row.get(key) for key in columns} for row in rows]
        return rows

    @staticmethod
    def _claim(db, body):
        now = utc_now()
        iso = now.isoformat()
        rows = db.setdefault("tables", {}).setdefault("actu_foot_publications", [])
        key = str(body["p_event_key"])
        row = next((r for r in rows if r.get("event_key") == key), None)
        acquired = False
        if row is None:
            row = {
                "event_key": key, "category": body["p_category"], "status": "claimed",
                "payload_hash": body["p_payload_hash"], "payload": body["p_payload"],
                "delivery_phase": "pending", "attempts": 1,
                "max_attempts": max(1, int(body.get("p_max_attempts") or 5)),
                "claimed_at": iso, "locked_at": iso, "updated_at": iso,
                "expires_at": body["p_expires_at"], "next_retry_at": None,
                "media_message_id": None, "poll_message_id": None,
                "telegram_message_id": None,
            }
            rows.append(row)
            acquired = True
        elif (
            row.get("status") == "failed"
            and int(row.get("attempts") or 0) < int(row.get("max_attempts") or 5)
            and (not moment(row.get("next_retry_at")) or moment(row["next_retry_at"]) <= now)
            and (not moment(row.get("expires_at")) or moment(row["expires_at"]) > now)
        ):
            row.update(status="claimed", attempts=int(row.get("attempts") or 0) + 1,
                       updated_at=iso, locked_at=iso, next_retry_at=None)
            if not row.get("payload"):
                row["payload"] = body["p_payload"]
            acquired = True
        return acquired, {
            "can_send": acquired,
            **{key: row.get(key) for key in (
                "status", "delivery_phase", "attempts", "max_attempts",
                "media_message_id", "poll_message_id", "telegram_message_id",
                "payload", "expires_at",
            )},
        }

    def dispatch(self, method, url, params=None, body=None, headers=None):
        from scripts.neon_rest_compat import Response
        params = params or {}
        headers = headers or {}
        fragment = url.removeprefix("github://encrypted/rest/v1/").strip("/")
        if not fragment or "/" in fragment and not fragment.startswith("rpc/"):
            raise ValueError("Invalid GitHub database route")
        if fragment.startswith("rpc/"):
            name = fragment.removeprefix("rpc/")
            if name not in _ALLOWED_RPC or method != "POST" or not isinstance(body, dict):
                raise ValueError("GitHub database RPC forbidden")
            if name == "actu_foot_claim_publication":
                def claim(db):
                    acquired, result = self._claim(db, body)
                    return acquired, result
                return Response(self.transact(claim, purpose="claim"))
            if name == "actu_foot_retryable_publications":
                def retry(db):
                    rows = self._rows(db, "actu_foot_publications")
                    now = utc_now()
                    changed = False
                    for row in rows:
                        locked = moment(row.get("locked_at"))
                        if row.get("status") == "claimed" and locked and locked < now - timedelta(minutes=4):
                            row.update(status="uncertain", last_error="stale_claim_quarantined",
                                       updated_at=now.isoformat(), locked_at=None, next_retry_at=None)
                            changed = True
                    valid = [
                        row for row in rows if row.get("status") == "failed"
                        and int(row.get("attempts") or 0) < int(row.get("max_attempts") or 5)
                        and (not moment(row.get("next_retry_at")) or moment(row["next_retry_at"]) <= now)
                        and (not moment(row.get("expires_at")) or moment(row["expires_at"]) > now)
                    ]
                    priority = {"goal", "carton_rouge", "resultat", "tirs_au_but", "tir_au_but_marque", "tir_au_but_manque"}
                    valid.sort(key=lambda row: (row.get("category") not in priority, row.get("updated_at") or ""))
                    return changed, copy.deepcopy(valid[:max(1, min(50, int(body.get("p_limit", 20))))])
                return Response(self.transact(retry, purpose="retryable"))
            def store_live(db):
                rows = self._rows(db, "actu_foot_live_events")
                changed = False
                result = []
                for item in body.get("p_events", []):
                    if not isinstance(item, dict):
                        continue
                    if not all(item.get(key) for key in ("event_key", "fixture_key", "kind", "home_team", "away_team")):
                        continue
                    row = next((r for r in rows if r.get("event_key") == item["event_key"]), None)
                    if row is None:
                        row = dict(item, confirmed=False, first_seen_at=utc_now().isoformat())
                        rows.append(row)
                    else:
                        row.update({key: val for key, val in item.items() if val is not None})
                    changed = True
                    result.append(copy.deepcopy(row.get("payload", {})))
                return changed, result
            return Response(self.transact(store_live, purpose="live-events"))
        table = fragment
        if table not in TABLES:
            raise ValueError("GitHub database table forbidden")
        if method == "GET":
            db, _ = self.read()
            return Response(self._selected(self._rows(db, table), params))
        if method == "POST":
            items = body if isinstance(body, list) else [body]
            if not items or not all(isinstance(row, dict) for row in items):
                raise ValueError("Invalid insert body")
            def insert(db):
                rows = self._rows(db, table)
                conflict = str(params.get("on_conflict") or KEYS.get(table) or "")
                if conflict and ("," in conflict or not re.fullmatch(r"[a-z_]+", conflict)):
                    raise ValueError("Invalid conflict key")
                for item in items:
                    current = next((r for r in rows if conflict and r.get(conflict) == item.get(conflict)), None)
                    if current is None:
                        rows.append(copy.deepcopy(item))
                    else:
                        current.update(copy.deepcopy(item))
                return True, copy.deepcopy(items) if "return=representation" in str(headers.get("Prefer", "")) else []
            return Response(self.transact(insert, purpose="upsert-" + table), 201)
        if method == "PATCH":
            if not isinstance(body, dict):
                raise ValueError("Invalid patch")
            if not [key for key in params if key not in {"select", "limit", "offset", "order"}]:
                raise ValueError("Unfiltered patch forbidden")
            def patch(db):
                rows = self._rows(db, table)
                selected = [row for row in rows if self._match(row, params)]
                for row in selected:
                    row.update(copy.deepcopy(body))
                return bool(selected), (copy.deepcopy(selected) if "return=representation" in str(headers.get("Prefer", "")) else [])
            return Response(self.transact(patch, purpose="patch-" + table))
        raise ValueError("GitHub database unsupported method")

    def read_runtime_history(self):
        db, _ = self.read()
        value = db.get("runtime_history", {})
        return copy.deepcopy(value) if isinstance(value, dict) else {}

    def update_runtime_history(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("History snapshot must be a dictionary")
        def update(db):
            existing = db.get("runtime_history")
            if not isinstance(existing, dict):
                existing = {}
            # Preserve newer sent dedupe keys even when two workflow runs overlap.
            merged = copy.deepcopy(payload)
            sent = dict(existing.get("sent") or {})
            sent.update(payload.get("sent") or {})
            merged["sent"] = sent
            db["runtime_history"] = merged
            return merged != existing, True
        return self.transact(update, purpose="history")
