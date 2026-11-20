-- Tracks bot /start -> verified Telegram Mini App opens without storing raw Telegram IDs.
-- Existing anonymous analytics cannot be retrospectively linked across services.
CREATE TABLE IF NOT EXISTS cine_bot_launch_funnel (
 visitor_hash TEXT PRIMARY KEY,
 first_start_at TEXT,
 last_start_at TEXT,
 starts INTEGER NOT NULL DEFAULT 0,
 first_launch_at TEXT,
 last_launch_at TEXT,
 launches INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_cine_bot_launch_start ON cine_bot_launch_funnel(first_start_at);
CREATE INDEX IF NOT EXISTS idx_cine_bot_launch_app ON cine_bot_launch_funnel(first_launch_at);
