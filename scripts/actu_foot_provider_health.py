#!/usr/bin/env python3
"""Qualité dynamique des fournisseurs Actu Foot.

Une panne répétée réduit temporairement la priorité d'une source. Une source
récupère progressivement son score de base après des réponses valides.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests
try:
    from scripts.neon_rest_compat import NeonRestSession
except ModuleNotFoundError:
    from neon_rest_compat import NeonRestSession


def _config() -> tuple[str, str]:
    base = "neon://private" if os.getenv("NEON_DATABASE_URL") else ""
    key = "server" if os.getenv("NEON_DATABASE_URL") else ""
    return base, key


def _defaults(source_quality: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        provider: {
            "provider": provider,
            "base_quality": int(values.get("overall") or 60),
            "effective_quality": int(values.get("overall") or 60),
            "consecutive_failures": 0,
            "success_count": 0,
            "failure_count": 0,
            "last_success_at": None,
            "last_failure_at": None,
            "last_error": None,
        }
        for provider, values in source_quality.items()
    }


def load_provider_health(
    session: requests.Session,
    source_quality: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    session = NeonRestSession(session)
    state = _defaults(source_quality)
    base, key = _config()
    if not base or not key:
        return state
    try:
        response = session.get(
            base + "/rest/v1/actu_foot_provider_health",
            params={"select": "*"},
            headers={"apikey": key, "Authorization": "Bearer " + key},
            timeout=(4, 8),
        )
        response.raise_for_status()
        rows = response.json()
    except (requests.RequestException, ValueError):
        return state
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        provider = str(row.get("provider") or "")
        if provider not in state:
            continue
        base_quality = state[provider]["base_quality"]
        effective = max(35, min(base_quality, int(row.get("effective_quality") or base_quality)))
        state[provider].update({
            "effective_quality": effective,
            "consecutive_failures": max(0, int(row.get("consecutive_failures") or 0)),
            "success_count": max(0, int(row.get("success_count") or 0)),
            "failure_count": max(0, int(row.get("failure_count") or 0)),
            "last_success_at": row.get("last_success_at"),
            "last_failure_at": row.get("last_failure_at"),
            "last_error": row.get("last_error"),
        })
    return state


def record_provider_health(
    session: requests.Session,
    snapshots: dict[str, Any],
    source_quality: dict[str, dict[str, Any]],
    state: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    session = NeonRestSession(session)
    base, key = _config()
    now = datetime.now(timezone.utc).isoformat()
    changed: list[dict[str, Any]] = []

    for provider, snapshot in snapshots.items():
        if provider not in state:
            continue
        current = dict(state[provider])
        base_quality = int(current["base_quality"])
        error = str(getattr(snapshot, "error", "") or "").strip()
        rows = getattr(snapshot, "rows", []) or []

        if error:
            failures = int(current.get("consecutive_failures") or 0) + 1
            current["consecutive_failures"] = failures
            current["failure_count"] = int(current.get("failure_count") or 0) + 1
            current["effective_quality"] = max(35, base_quality - min(42, failures * 7))
            current["last_failure_at"] = now
            current["last_error"] = error[:240]
        elif rows:
            current["success_count"] = int(current.get("success_count") or 0) + 1
            current["consecutive_failures"] = 0
            current["effective_quality"] = min(
                base_quality,
                int(current.get("effective_quality") or base_quality) + 8,
            )
            current["last_success_at"] = now
            current["last_error"] = None
        else:
            continue

        state[provider] = current
        changed.append({
            "provider": provider,
            "base_quality": base_quality,
            "effective_quality": int(current["effective_quality"]),
            "consecutive_failures": int(current["consecutive_failures"]),
            "success_count": int(current["success_count"]),
            "failure_count": int(current["failure_count"]),
            "last_success_at": current.get("last_success_at"),
            "last_failure_at": current.get("last_failure_at"),
            "last_error": current.get("last_error"),
            "updated_at": now,
        })

    if not changed or not base or not key:
        return state

    try:
        response = session.post(
            base + "/rest/v1/actu_foot_provider_health",
            params={"on_conflict": "provider"},
            headers={
                "apikey": key,
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            json=changed,
            timeout=(4, 8),
        )
        response.raise_for_status()
        print(
            "ACTU_FOOT_PROVIDER_HEALTH",
            {row["provider"]: row["effective_quality"] for row in changed},
        )
    except requests.RequestException as exc:
        print("ACTU_FOOT_PROVIDER_HEALTH_SKIP", type(exc).__name__)
    return state


def effective_quality(
    provider: str,
    source_quality: dict[str, dict[str, Any]],
    state: dict[str, dict[str, Any]],
) -> int:
    base = int(source_quality.get(provider, {}).get("overall") or 60)
    row = state.get(provider) if isinstance(state, dict) else None
    if not isinstance(row, dict):
        return base
    return max(35, min(base, int(row.get("effective_quality") or base)))
