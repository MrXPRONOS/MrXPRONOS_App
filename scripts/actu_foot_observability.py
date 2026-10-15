#!/usr/bin/env python3
"""Observabilité privée Actu Foot.

Ce module est volontairement best-effort : aucun échec de métriques ne doit
bloquer la diffusion Telegram ou le lifecycle.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import requests


def _moment(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _outbox_pending(session: requests.Session) -> int:
    """Compte seulement la file réellement active/rejouable.

    Les statuts uncertain sont mis en quarantaine pour éviter un double envoi.
    Un failed ayant épuisé ses tentatives est terminal et ne doit pas gonfler
    la métrique outbox_pending.
    """
    base = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not base or not key:
        return 0
    try:
        response = session.get(
            base + "/rest/v1/actu_foot_publications",
            params={
                "select": "event_key,status,attempts,max_attempts,expires_at,next_retry_at,locked_at",
                "status": "in.(failed,claimed,uncertain)",
                "limit": "100",
            },
            headers={"apikey": key, "Authorization": "Bearer " + key},
            timeout=(5, 10),
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            return 0
        now = datetime.now(timezone.utc)
        active = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            status = str(row.get("status") or "")
            if status == "uncertain":
                continue
            attempts = max(0, int(row.get("attempts") or 0))
            max_attempts = max(1, int(row.get("max_attempts") or 5))
            if attempts >= max_attempts:
                continue
            expires_at = _moment(row.get("expires_at"))
            if expires_at is not None and expires_at <= now:
                continue
            if status in {"failed", "claimed"}:
                active += 1
        return active
    except (requests.RequestException, ValueError, TypeError):
        return 0


def persist_run_metrics(
    session: requests.Session,
    *,
    mode: str,
    started_at: datetime,
    dry_run: bool,
    counter: dict[str, int],
    tracked_pending: int,
    ranking: dict,
) -> None:
    """Persiste une métrique privée sans jamais lever d'erreur vers le canal."""
    if os.getenv("FOOTBALL_RUN_METRICS", "0") != "1":
        return
    base = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not base or not key:
        return

    finished_at = datetime.now(timezone.utc)
    payload = {
        "run_id": str(os.getenv("GITHUB_RUN_ID") or ""),
        "mode": mode,
        "dry_run": bool(dry_run),
        "started_at": started_at.astimezone(timezone.utc).isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_ms": max(0, int((finished_at - started_at).total_seconds() * 1000)),
        "sent": int(counter.get("sent") or 0),
        "skipped": int(counter.get("skipped") or 0),
        "errors": int(counter.get("errors") or 0),
        "tracked_pending": max(0, int(tracked_pending)),
        "ranking_eligible": int(ranking.get("eligible") or 0),
        "ranking_selected": int(ranking.get("selected") or 0),
        "outbox_pending": _outbox_pending(session),
        "ranking_snapshot": ranking,
    }
    try:
        response = session.post(
            base + "/rest/v1/actu_foot_run_metrics",
            headers={
                "apikey": key,
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=payload,
            timeout=(5, 10),
        )
        response.raise_for_status()
        print("ACTU_FOOT_METRICS_OK", mode, json.dumps({
            "sent": payload["sent"],
            "errors": payload["errors"],
            "tracked": payload["tracked_pending"],
            "selected": payload["ranking_selected"],
            "outbox": payload["outbox_pending"],
            "duration_ms": payload["duration_ms"],
        }))
    except requests.RequestException as exc:
        print("ACTU_FOOT_METRICS_SKIPPED", type(exc).__name__, str(exc)[:120])
