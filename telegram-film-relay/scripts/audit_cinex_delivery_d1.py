"""Read-only aggregated CineX delivery audit. Never prints Telegram IDs or secrets."""
from __future__ import annotations
import json
import os
import urllib.request
import urllib.error

API = ("https://api.cloudflare.com/client/v4/accounts/"
       "9c86118191b804d91b5f5b2c89114999/d1/database/"
       "fa8b5009-bc1a-4a6e-b143-7a487c7297a5/query")
SQL = {
    "owner_count": "SELECT COUNT(*) AS n FROM admin_users WHERE role='owner'",
    "owner_vault_totals": "SELECT status,media_kind,COUNT(*) AS n FROM cine_owner_vault GROUP BY status,media_kind",
    "owner_misroute": (
        "SELECT COUNT(*) AS n FROM cine_owner_vault v WHERE v.owner_chat_id IS NOT NULL "
        "AND NOT EXISTS(SELECT 1 FROM admin_users a WHERE a.user_id=v.owner_chat_id AND a.role='owner')"
    ),
    "owner_unique_destinations": (
        "SELECT COUNT(DISTINCT owner_chat_id) AS n FROM cine_owner_vault WHERE status='stored'"
    ),
    "owner_same_source": (
        "SELECT COUNT(*) AS n FROM (SELECT source_chat_id,source_message_id "
        "FROM cine_owner_vault GROUP BY source_chat_id,source_message_id HAVING COUNT(*)>1)"
    ),
    "classic_deliveries": "SELECT status,COUNT(*) AS n FROM cine_classic_deliveries GROUP BY status",
    "classic_recent_same_movie": (
        "SELECT COUNT(*) AS n FROM (SELECT telegram_chat_id,token "
        "FROM cine_classic_deliveries WHERE created_at>=datetime('now','-1 hour') "
        "AND status IN ('queued','sending','sent','needs_review') "
        "GROUP BY telegram_chat_id,token HAVING COUNT(*)>1)"
    ),
    "catalog_recent_same_movie": (
        "SELECT COUNT(*) AS n FROM (SELECT telegram_chat_id,token "
        "FROM cine_delivery_jobs WHERE created_at>=datetime('now','-1 hour') "
        "AND status IN ('queued','sending','complete','needs_review') "
        "GROUP BY telegram_chat_id,token HAVING COUNT(*)>1)"
    ),
    "series_recent_same_show": (
        "SELECT COUNT(*) AS n FROM (SELECT telegram_chat_id,token "
        "FROM cine_series_jobs WHERE created_at>=datetime('now','-1 hour') "
        "AND status IN ('queued','sending','complete','needs_review') "
        "GROUP BY telegram_chat_id,token HAVING COUNT(*)>1)"
    ),
    "franchise_recent_same_show": (
        "SELECT COUNT(*) AS n FROM (SELECT telegram_chat_id,slug "
        "FROM cine_franchise_jobs WHERE created_at>=datetime('now','-1 hour') "
        "AND status IN ('queued','sending','complete','needs_review') "
        "GROUP BY telegram_chat_id,slug HAVING COUNT(*)>1)"
    ),
    "central_stock": "SELECT state,source_family,COUNT(*) AS n FROM cine_private_stock_items GROUP BY state,source_family",
    "central_stock_ready": "SELECT COUNT(*) AS n FROM cine_private_stock_config WHERE singleton=1 AND ready=1",
    "classic_link_count": "SELECT COUNT(*) AS n FROM cine_classic_links WHERE status='published'",
    "status_gate": "SELECT value FROM bot_settings WHERE setting_key='cine_delivery_enabled'",
}


def query(token: str, sql: str):
    request = urllib.request.Request(
        API, data=json.dumps({"sql": sql}).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        obj = json.load(response)
    if not obj.get("success") or not obj.get("result") or not obj["result"][0].get("success"):
        raise ValueError("query_rejected")
    return obj["result"][0].get("results") or []


def main():
    token = os.getenv("CLOUDFLARE_API_TOKEN") or os.getenv("CF_API_TOKEN") or ""
    if not token:
        print("AUDIT_UNAVAILABLE missing_cloudflare_token")
        return 2
    failed = []
    for name, sql in SQL.items():
        try:
            data = query(token, sql)
            # Queries are strict aggregates; never log SQL/IDs/captions.
            print("AUDIT_SUMMARY " + json.dumps({"name": name, "rows": data}))
        except Exception as exc:
            failed.append(name)
            print("AUDIT_QUERY_FAILED " + json.dumps({"name": name, "reason": type(exc).__name__}))
    print("AUDIT_COMPLETED " + json.dumps({"checks": len(SQL), "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
