#!/usr/bin/env python3
"""Rapport privé de santé Actu Foot pour GitHub Actions."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import requests


def _config() -> tuple[str, str]:
    base = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not base or not key:
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY manquants")
    return base, key


def _get(session: requests.Session, table: str, params: dict) -> list[dict]:
    base, key = _config()
    response = session.get(
        base + "/rest/v1/" + table,
        params=params,
        headers={"apikey": key, "Authorization": "Bearer " + key},
        timeout=(6, 12),
    )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, list) else []


def build_report(session: requests.Session) -> str:
    runs = _get(session, "actu_foot_run_metrics", {
        "select": "mode,finished_at,duration_ms,sent,skipped,errors,tracked_pending,ranking_selected,outbox_pending",
        "order": "finished_at.desc",
        "limit": "12",
    })
    providers = _get(session, "actu_foot_provider_health", {
        "select": "provider,base_quality,effective_quality,consecutive_failures,last_success_at,last_failure_at,last_error",
        "order": "provider.asc",
    })
    outbox = _get(session, "actu_foot_publications", {
        "select": "event_key,status,category,updated_at,next_retry_at",
        "status": "in.(failed,claimed,uncertain)",
        "order": "updated_at.asc",
        "limit": "50",
    })
    recent_events = _get(session, "actu_foot_live_events", {
        "select": "event_key,kind,home_team,away_team,last_seen_at,confirmed",
        "order": "last_seen_at.desc",
        "limit": "10",
    })

    lines = [
        "# Actu Foot — état de santé",
        "",
        "Généré : " + datetime.now(timezone.utc).isoformat(),
        "",
        f"- Outbox en attente/incertaine : **{len(outbox)}**",
        f"- Événements LIVE récents visibles : **{len(recent_events)}**",
        "",
        "## Derniers runs",
        "",
        "| Mode | Fin | Durée | Envoyés | Erreurs | Suivis | Ranking | Outbox |",
        "|:--|:--|--:|--:|--:|--:|--:|--:|",
    ]
    for row in runs:
        lines.append(
            "| {mode} | {finished} | {duration} ms | {sent} | {errors} | {tracked} | {selected} | {outbox} |".format(
                mode=row.get("mode") or "?",
                finished=str(row.get("finished_at") or "")[:19],
                duration=int(row.get("duration_ms") or 0),
                sent=int(row.get("sent") or 0),
                errors=int(row.get("errors") or 0),
                tracked=int(row.get("tracked_pending") or 0),
                selected=int(row.get("ranking_selected") or 0),
                outbox=int(row.get("outbox_pending") or 0),
            )
        )

    lines += [
        "",
        "## Fournisseurs",
        "",
        "| Source | Base | Effectif | Échecs consécutifs | Dernier succès |",
        "|:--|--:|--:|--:|:--|",
    ]
    for row in providers:
        lines.append(
            f"| {row.get('provider') or '?'} | {int(row.get('base_quality') or 0)} | "
            f"{int(row.get('effective_quality') or 0)} | "
            f"{int(row.get('consecutive_failures') or 0)} | "
            f"{str(row.get('last_success_at') or '')[:19]} |"
        )

    if outbox:
        lines += ["", "## Outbox à surveiller", ""]
        for row in outbox[:15]:
            lines.append(
                f"- {row.get('status')} · {row.get('category')} · "
                f"{str(row.get('event_key') or '')[:90]}"
            )
    return "\n".join(lines) + "\n"


def main() -> None:
    print(build_report(requests.Session()), end="")


if __name__ == "__main__":
    main()
