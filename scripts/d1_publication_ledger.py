"""Cloudflare D1 publication ledger via its authenticated REST API.

Uses the historical migrated telegram_sent table and unique(kind,ref_id,ref_date).
For GitHub production jobs until the common OIDC Worker supports every kind.
All writes fail closed on uncertain HTTP results; never switch databases.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta

import requests

ACCOUNT = "9c86118191b804d91b5f5b2c89114999"
DATABASE = "ff88b45f-9c3b-4592-a2d6-e32ed7e75fe6"
ENDPOINT = "https://api.cloudflare.com/client/v4/accounts/" + ACCOUNT + "/d1/database/" + DATABASE + "/query"

class D1LedgerError(RuntimeError):
    pass

class D1Ledger:
    def __init__(self, token=None, session=None):
        self.token = (token if token is not None else os.getenv("CLOUDFLARE_API_TOKEN", "")).strip()
        if not self.token:
            raise D1LedgerError("Cloudflare D1 API token missing; cannot publish safely")
        self.session = session or requests.Session()

    def query(self, sql, params=()):
        try:
            response = self.session.post(
                ENDPOINT,
                headers={"Authorization": "Bearer " + self.token,
                         "Content-Type": "application/json"},
                json={"sql": sql, "params": list(params)}, timeout=25)
            if response.status_code != 200:
                raise D1LedgerError("D1 request rejected HTTP " + str(response.status_code))
            body = response.json()
            if not isinstance(body, dict) or body.get("success") is not True:
                raise D1LedgerError("D1 API did not confirm success")
            result = body.get("result")
            if not isinstance(result, list) or len(result) != 1 or not result[0].get("success"):
                raise D1LedgerError("D1 query failed or returned unexpected status")
            return result[0]
        except requests.RequestException as exc:
            raise D1LedgerError("Uncertain D1 write/read: no automatic cross-database retry") from exc
        except (ValueError, TypeError) as exc:
            raise D1LedgerError("Invalid D1 response") from exc

    def rows(self, kind, day, *, ref_id=None, limit=1000):
        if ref_id is None:
            return self.query(
                "SELECT ref_id,ref_date,delivery_status,telegram_message_id,sent_at FROM telegram_sent "
                "WHERE kind=? AND ref_date=? LIMIT ?",
                (kind, day, min(1000, int(limit))))["results"]
        return self.query(
            "SELECT ref_id,ref_date,delivery_status FROM telegram_sent "
            "WHERE kind=? AND ref_id=? AND ref_date=? LIMIT 1",
            (kind, ref_id, day))["results"]

    def claim(self, kind, ref_id, day):
        if not all(isinstance(v, str) and v.strip() for v in (kind, ref_id, day)):
            raise D1LedgerError("Empty publication identity")
        # Idempotency is enforced by SQLite's UNIQUE(kind,ref_id,ref_date).
        # The decision MUST use meta.changes from this INSERT response.
        result = self.query(
            "INSERT OR IGNORE INTO telegram_sent "
            "(id,kind,ref_id,ref_date,sent_at,validation_sent,delivery_status) "
            "VALUES (?,?,?,?,?,0,'reserved')",
            (str(uuid.uuid4()), kind, ref_id, day,
             datetime.now(timezone.utc).isoformat()))
        changes = (result.get("meta") or {}).get("changes")
        if changes not in (0, 1):
            raise D1LedgerError("Invalid atomic insert result; delivery blocked")
        return changes == 1

    def mark(self, kind, ref_id, day, *, message_id=None):
        if message_id is None:
            result = self.query(
                "UPDATE telegram_sent SET delivery_status='sent',published_at=? "
                "WHERE kind=? AND ref_id=? AND ref_date=? AND delivery_status='reserved'",
                (datetime.now(timezone.utc).isoformat(),kind,ref_id,day))
        else:
            result = self.query(
                "UPDATE telegram_sent SET delivery_status='sent',published_at=?,telegram_message_id=? "
                "WHERE kind=? AND ref_id=? AND ref_date=? AND delivery_status='reserved'",
                (datetime.now(timezone.utc).isoformat(),int(message_id),kind,ref_id,day))
        if (result.get("meta") or {}).get("changes") != 1:
            raise D1LedgerError("Confirmation of published content not committed")
        return True

    def release(self, kind, ref_id, day):
        # Only safe when external service explicitly REJECTED publication.
        result = self.query(
            "DELETE FROM telegram_sent WHERE kind=? AND ref_id=? AND ref_date=? "
            "AND delivery_status='reserved'",
            (kind,ref_id,day))
        return (result.get("meta") or {}).get("changes") == 1


    def set_status(self, kind, ref_id, day, status):
        """Close a pending claim without permitting an automatic resend.

        failed: no Telegram request was attempted (local rendering/preflight error).
        rejected: Telegram explicitly rejected the request.
        uncertain: the request may have reached Telegram; quarantine until reviewed.
        """
        if status not in ("failed", "rejected", "uncertain"):
            raise D1LedgerError("Invalid delivery terminal state")
        result = self.query(
            "UPDATE telegram_sent SET delivery_status=? "
            "WHERE kind=? AND ref_id=? AND ref_date=? AND delivery_status='reserved'",
            (status, kind, ref_id, day))
        return (result.get("meta") or {}).get("changes") == 1

    def reconcile(self, kind, ref_id, day, *, now=None, max_pending_minutes=10):
        """Resolve only provable deliveries; quarantine old unconfirmed claims.

        Telegram Bot API does not offer a reliable arbitrary channel message
        lookup. Never infer delivery from elapsed time, and never resend an
        uncertain event. A stored Telegram message_id is positive evidence.
        """
        rows = self.rows(kind, day, ref_id=ref_id)
        if not rows:
            return "missing"
        row = rows[0]
        status = str(row.get("delivery_status") or "")
        if status == "sent":
            return "sent"
        identifier = row.get("telegram_message_id")
        if identifier is not None:
            try:
                msg_id = int(identifier)
            except (ValueError, TypeError):
                raise D1LedgerError("Invalid stored Telegram message_id")
            if msg_id <= 0:
                raise D1LedgerError("Invalid stored Telegram message_id")
            if status in ("reserved", "uncertain"):
                result = self.query(
                    "UPDATE telegram_sent SET delivery_status='sent', "
                    "published_at=COALESCE(published_at,?) "
                    "WHERE kind=? AND ref_id=? AND ref_date=? "
                    "AND delivery_status IN ('reserved','uncertain') AND telegram_message_id=?",
                    ((now or datetime.now(timezone.utc)).isoformat(),
                     kind, ref_id, day, msg_id))
                if (result.get("meta") or {}).get("changes") == 1:
                    return "sent"
                # Concurrent update: re-read rather than assuming success.
                return str((self.rows(kind, day, ref_id=ref_id) or [{}])[0].get("delivery_status") or "")
        if status == "reserved":
            timestamp = row.get("sent_at")
            try:
                claimed_at = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                if claimed_at.tzinfo is None:
                    claimed_at = claimed_at.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                raise D1LedgerError("Missing/invalid reservation timestamp; manual review required")
            current = now or datetime.now(timezone.utc)
            if current - claimed_at >= timedelta(minutes=max_pending_minutes):
                if self.set_status(kind, ref_id, day, "uncertain"):
                    return "uncertain"
                return str((self.rows(kind, day, ref_id=ref_id) or [{}])[0].get("delivery_status") or "")
        return status

    def confirm_manual(self, kind, ref_id, day, message_id):
        """Operator verified the exact post in Telegram; never guesses a send."""
        mid = int(message_id)
        if mid <= 0:
            raise D1LedgerError("A positive verified message id is required")
        result = self.query(
            "UPDATE telegram_sent SET delivery_status='sent',telegram_message_id=?,"
            "published_at=COALESCE(published_at,?) "
            "WHERE kind=? AND ref_id=? AND ref_date=? "
            "AND delivery_status IN ('reserved','uncertain') "
            "AND telegram_message_id IS NULL",
            (mid, datetime.now(timezone.utc).isoformat(), kind, ref_id, day))
        if (result.get("meta") or {}).get("changes") != 1:
            raise D1LedgerError("Manual reconciliation refused: unexpected ledger status")
        return True

    def status_counts(self, kind, day):
        return self.query(
            "SELECT delivery_status,COUNT(*) AS total FROM telegram_sent "
            "WHERE kind=? AND ref_date=? GROUP BY delivery_status",
            (kind, day)).get("results") or []
