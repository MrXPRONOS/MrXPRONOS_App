#!/usr/bin/env python3
"""Rapport privé de santé Actu Foot pour GitHub Actions."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import requests
try:
    from scripts.neon_rest_compat import NeonRestSession
except ModuleNotFoundError:
    from neon_rest_compat import NeonRestSession

from actu_foot_observability import _actionable_outbox_count


def _config() -> tuple[str, str]:
    base = "neon://private" if os.getenv("NEON_DATABASE_URL") else ""
    key = "server" if os.getenv("NEON_DATABASE_URL") else ""
    if not base or not key:
        raise SystemExit("NEON_DATABASE_URL manquants")
    return base, key


def _get(session: requests.Session, table: str, params: dict) -> list[dict]:
    base, key = _config()
    response = NeonRestSession(session).get(
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
        "select": "event_key,status,category,updated_at,next_retry_at,attempts,max_attempts,expires_at",
        "status": "in.(failed,claimed,uncertain)",
        "order": "updated_at.asc",
        "limit": "100",
    })
    recent_events = _get(session, "actu_foot_live_events", {
        "select": "event_key,kind,home_team,away_team,last_seen_at,confirmed",
        "order": "last_seen_at.desc",
        "limit": "10",
    })
    news_rows = _get(session, "actu_foot_news_snapshot", {
        "select": "generated_at,payload",
        "id": "eq.latest",
        "limit": "1",
    })

    actionable_outbox = _actionable_outbox_count(outbox)
    degraded = [
        row for row in providers
        if int(row.get("effective_quality") or 0) < int(row.get("base_quality") or 0)
    ]
    latest_full = next((row for row in runs if row.get("mode") == "full"), {})
    latest_lifecycle = next((row for row in runs if row.get("mode") == "lifecycle"), {})
    news_payload = news_rows[0].get("payload") if news_rows and isinstance(news_rows[0], dict) else []
    news_count = len(news_payload) if isinstance(news_payload, list) else 0
    news_generated = (
        str(news_rows[0].get("generated_at") or "")[:19]
        if news_rows and isinstance(news_rows[0], dict) else ""
    )

    lines = [
        "# Actu Foot — état de santé",
        "",
        "Généré : " + datetime.now(timezone.utc).isoformat(),
        "",
        f"- Dernier FULL : **{str(latest_full.get('finished_at') or '')[:19]}** · erreurs **{int(latest_full.get('errors') or 0)}**",
        f"- Dernier LIFECYCLE : **{str(latest_lifecycle.get('finished_at') or '')[:19]}** · erreurs **{int(latest_lifecycle.get('errors') or 0)}**",
        f"- Outbox actionnable : **{actionable_outbox}**",
        f"- Fournisseurs dégradés : **{len(degraded)} / {len(providers)}**",
        f"- Infos Foot : **{news_count}** éléments · snapshot **{news_generated}**",
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

    actionable_rows = [
        row for row in outbox
        if isinstance(row, dict) and row.get("status") in {"failed", "claimed"}
    ]
    if actionable_rows:
        lines += ["", "## Outbox à surveiller", ""]
        for row in actionable_rows[:15]:
            lines.append(
                f"- {row.get('status')} · {row.get('category')} · "
                f"{str(row.get('event_key') or '')[:90]}"
            )
    return "\n".join(lines) + "\n"


def main() -> None:
    print(build_report(requests.Session()), end="")


if __name__ == "__main__":
    main()
