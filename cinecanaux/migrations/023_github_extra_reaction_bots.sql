-- Add ten optional, independently authenticated Telegram reaction bots.
-- Existing Cine Radar + Canal reaction jobs remain untouched.
-- Capture the current message sequence at installation: no retroactive reactions.
CREATE TABLE IF NOT EXISTS channel_reaction_extra_config (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  start_after_seq INTEGER NOT NULL,
  installed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO channel_reaction_extra_config(id,start_after_seq)
SELECT 1,COALESCE(MAX(seq),0) FROM channel_reaction_posts;

CREATE TABLE IF NOT EXISTS channel_reaction_extra_jobs (
  post_seq INTEGER NOT NULL REFERENCES channel_reaction_posts(seq),
  bot_slot INTEGER NOT NULL CHECK(bot_slot BETWEEN 3 AND 12),
  emoji TEXT NOT NULL CHECK(emoji IN ('❤️','👍')),
  state TEXT NOT NULL DEFAULT 'pending'
    CHECK(state IN ('pending','retry','sent','blocked')),
  attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
  next_try_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_error TEXT NOT NULL DEFAULT '',
  sent_at TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(post_seq,bot_slot)
);
CREATE INDEX IF NOT EXISTS idx_channel_reaction_extra_pending
  ON channel_reaction_extra_jobs(state,next_try_at,post_seq);
