-- T01 — Shared atomic Telegram send quota.
-- Never stores raw subscriber Telegram IDs, message text or bot tokens.
-- All Worker queues (deliveries, archive, announcements, reactions) use the
-- same D1 row; the Worker also creates this table lazily during rollout.
CREATE TABLE IF NOT EXISTS cine_telegram_send_quota (
  scope TEXT PRIMARY KEY,
  window_start_ms INTEGER NOT NULL DEFAULT 0,
  used INTEGER NOT NULL DEFAULT 0,
  blocked_until_ms INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
