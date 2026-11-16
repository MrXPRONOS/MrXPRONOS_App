-- Anonymous aggregate search metrics. No user IDs, search phrases, IPs or click history.
CREATE TABLE IF NOT EXISTS search_daily_stats (
 date_utc TEXT NOT NULL,
 category TEXT NOT NULL,
 searches INTEGER NOT NULL DEFAULT 0,
 empty_results INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(date_utc,category)
);
CREATE INDEX IF NOT EXISTS idx_search_daily_stats_date ON search_daily_stats(date_utc);
