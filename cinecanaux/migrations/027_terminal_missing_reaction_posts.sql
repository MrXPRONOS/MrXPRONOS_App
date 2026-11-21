-- Mark Telegram posts as terminal only after Telegram has explicitly
-- rejected them with "message to react not found". These references can no
-- longer receive reactions. Retain the original ledger for auditability.
-- The enqueue paths for new posts and the two existing bot tokens are unchanged.
CREATE TABLE IF NOT EXISTS channel_reaction_terminal_posts (
  post_seq INTEGER PRIMARY KEY REFERENCES channel_reaction_posts(seq),
  reason TEXT NOT NULL CHECK(reason IN ('telegram_message_not_found')),
  marked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO channel_reaction_terminal_posts(post_seq,reason)
SELECT DISTINCT post_seq,'telegram_message_not_found'
FROM channel_reaction_jobs
WHERE LOWER(last_error) LIKE '%message to react not found%';
