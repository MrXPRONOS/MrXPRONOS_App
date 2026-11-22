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
    "owner_vault_switch": "SELECT setting_value FROM cine_series_config WHERE setting_key='owner_chat_vault_enabled'",
    "owner_pending_older_1h": "SELECT COUNT(*) AS n FROM cine_owner_vault WHERE status='queued' AND created_at<datetime('now','-1 hour')",
    "owner_pending_older_24h": "SELECT COUNT(*) AS n FROM cine_owner_vault WHERE status='queued' AND created_at<datetime('now','-24 hours')",
    "owner_pending_older_6h": "SELECT COUNT(*) AS n FROM cine_owner_vault WHERE status='queued' AND created_at<datetime('now','-6 hours')",
    "series_recent_duplicate_10m": (
        "SELECT COUNT(*) AS n FROM (SELECT telegram_chat_id,token FROM cine_series_jobs "
        "WHERE created_at>=datetime('now','-10 minutes') AND status IN ('queued','sending','complete','needs_review') "
        "GROUP BY telegram_chat_id,token HAVING COUNT(*)>1)"
    ),
    "series_repeat_statuses": (
        "SELECT COUNT(*) AS attempts,MIN(created_at) AS oldest,MAX(created_at) AS newest, "
        "GROUP_CONCAT(status) AS states FROM cine_series_jobs "
        "WHERE created_at>=datetime('now','-1 hour') "
        "GROUP BY telegram_chat_id,token HAVING COUNT(*)>1"
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
    "central_stock_pending_older_1h": "SELECT COUNT(*) AS n FROM cine_private_stock_items WHERE state='queued' AND created_at<datetime('now','-1 hour')",
    "central_stock_pending_older_24h": "SELECT COUNT(*) AS n FROM cine_private_stock_items WHERE state='queued' AND created_at<datetime('now','-24 hours')",
    "central_stock_needs_review": "SELECT COUNT(*) AS n FROM cine_private_stock_items WHERE state='needs_review'",
    "classic_link_count": "SELECT COUNT(*) AS n FROM cine_classic_links WHERE status='published'",
    "classic_queue_old_24h": "SELECT COUNT(*) AS n FROM cine_classic_deliveries WHERE status='queued' AND created_at<datetime('now','-24 hours')",
    "catalog_queue_old_24h": "SELECT COUNT(*) AS n FROM cine_delivery_jobs WHERE status='queued' AND created_at<datetime('now','-24 hours')",
    "series_queue_old_24h": "SELECT COUNT(*) AS n FROM cine_series_jobs WHERE status='queued' AND created_at<datetime('now','-24 hours')",
    "franchise_queue_old_24h": "SELECT COUNT(*) AS n FROM cine_franchise_jobs WHERE status='queued' AND created_at<datetime('now','-24 hours')",
    "classic_review": "SELECT COUNT(*) AS n FROM cine_classic_deliveries WHERE status='needs_review'",
    "catalog_review": "SELECT COUNT(*) AS n FROM cine_delivery_jobs WHERE status='needs_review'",
    "series_review": "SELECT COUNT(*) AS n FROM cine_series_jobs WHERE status='needs_review'",
    "series_review_older_1h": "SELECT COUNT(*) AS n FROM cine_series_jobs WHERE status='needs_review' AND updated_at<datetime('now','-1 hour')",
    "series_review_older_24h": "SELECT COUNT(*) AS n FROM cine_series_jobs WHERE status='needs_review' AND updated_at<datetime('now','-24 hours')",
    "series_review_item_states": (
        "SELECT i.state,COUNT(*) AS n FROM cine_series_job_items i "
        "JOIN cine_series_jobs j ON j.id=i.job_id "
        "WHERE j.status='needs_review' GROUP BY i.state"
    ),
    "franchise_review": "SELECT COUNT(*) AS n FROM cine_franchise_jobs WHERE status='needs_review'",
    "classic_duplicates_10m": (
        "SELECT COUNT(*) AS n FROM (SELECT telegram_chat_id,token FROM cine_classic_deliveries "
        "WHERE created_at>=datetime('now','-10 minutes') AND status IN ('queued','sending','sent','needs_review') "
        "GROUP BY telegram_chat_id,token HAVING COUNT(*)>1)"
    ),
    "catalog_duplicates_10m": (
        "SELECT COUNT(*) AS n FROM (SELECT telegram_chat_id,token FROM cine_delivery_jobs "
        "WHERE created_at>=datetime('now','-10 minutes') AND status IN ('queued','sending','complete','needs_review') "
        "GROUP BY telegram_chat_id,token HAVING COUNT(*)>1)"
    ),
    "franchise_duplicates_10m": (
        "SELECT COUNT(*) AS n FROM (SELECT telegram_chat_id,slug FROM cine_franchise_jobs "
        "WHERE created_at>=datetime('now','-10 minutes') AND status IN ('queued','sending','complete','needs_review') "
        "GROUP BY telegram_chat_id,slug HAVING COUNT(*)>1)"
    ),
    "classic_latency_24h": (
        "SELECT COUNT(*) AS n, ROUND(AVG((julianday(sent_at)-julianday(created_at))*86400),1) AS average_seconds, "
        "ROUND(MAX((julianday(sent_at)-julianday(created_at))*86400),1) AS max_seconds "
        "FROM cine_classic_deliveries WHERE sent_at>=datetime('now','-24 hours')"
    ),
    "catalog_latency_24h": (
        "SELECT COUNT(*) AS n, ROUND(AVG((julianday(i.sent_at)-julianday(j.created_at))*86400),1) AS average_seconds, "
        "ROUND(MAX((julianday(i.sent_at)-julianday(j.created_at))*86400),1) AS max_seconds "
        "FROM cine_delivery_jobs j JOIN cine_delivery_job_items i ON i.job_id=j.id "
        "WHERE i.ordinal=1 AND i.sent_at>=datetime('now','-24 hours')"
    ),
    "series_latency_24h": (
        "SELECT COUNT(*) AS n, ROUND(AVG((julianday(i.sent_at)-julianday(j.created_at))*86400),1) AS average_seconds, "
        "ROUND(MAX((julianday(i.sent_at)-julianday(j.created_at))*86400),1) AS max_seconds "
        "FROM cine_series_jobs j JOIN cine_series_job_items i ON i.job_id=j.id "
        "WHERE i.ordinal=1 AND i.sent_at>=datetime('now','-24 hours')"
    ),
    "franchise_latency_24h": (
        "SELECT COUNT(*) AS n, ROUND(AVG(seconds),1) AS average_seconds, "
        "ROUND(MAX(seconds),1) AS max_seconds FROM ("
        "SELECT (julianday(MIN(i.sent_at))-julianday(j.created_at))*86400 AS seconds "
        "FROM cine_franchise_jobs j JOIN cine_franchise_job_items i ON i.job_id=j.id "
        "WHERE i.sent_at>=datetime('now','-24 hours') GROUP BY j.id)"
    ),
    "status_gate": "SELECT value FROM bot_settings WHERE setting_key='cine_delivery_enabled'",
}

# Alert on fresh duplicates, misroutes, or queues stuck for a day.
# A historic duplicate outside the last 10 minutes remains visible in summary
# but must not turn a healthy current run red.
ALERT_NONZERO = {
    "owner_misroute", "owner_same_source", "owner_pending_older_24h",
    "central_stock_pending_older_24h", "central_stock_needs_review",
    "series_recent_duplicate_10m", "classic_duplicates_10m",
    "catalog_duplicates_10m", "franchise_duplicates_10m",
    "classic_queue_old_24h", "catalog_queue_old_24h",
    "series_queue_old_24h", "franchise_queue_old_24h",
    "series_review_older_24h",
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
    alerts = []
    for name, sql in SQL.items():
        try:
            data = query(token, sql)
            # Queries are strict aggregates; never log SQL/IDs/captions.
            print("AUDIT_SUMMARY " + json.dumps({"name": name, "rows": data}))
            if name in ALERT_NONZERO and any(int(row.get("n", 0)) > 0 for row in data):
                alerts.append(name)
                print("AUDIT_ALERT " + json.dumps({"name": name, "issue": "nonzero_count"}))
        except Exception as exc:
            failed.append(name)
            print("AUDIT_QUERY_FAILED " + json.dumps({"name": name, "reason": type(exc).__name__}))
    print("AUDIT_COMPLETED " + json.dumps({"checks": len(SQL), "failed": failed, "alerts": alerts}))
    return 1 if (failed or alerts) else 0


if __name__ == "__main__":
    raise SystemExit(main())
