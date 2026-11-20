-- Reactions by two owner-controlled Telegram bots on newly observed channel posts.
-- Applied to Cine Radar D1 before activating its Worker code.
CREATE TABLE IF NOT EXISTS channel_reaction_posts (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id TEXT NOT NULL,
  message_id INTEGER NOT NULL CHECK(message_id > 0),
  media_group_id TEXT,
  observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(chat_id,message_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_channel_reaction_album
  ON channel_reaction_posts(chat_id,media_group_id)
  WHERE media_group_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS channel_reaction_jobs (
  post_seq INTEGER NOT NULL REFERENCES channel_reaction_posts(seq),
  bot_role TEXT NOT NULL CHECK(bot_role IN ('radar','canal')),
  emoji TEXT NOT NULL CHECK(emoji IN ('❤️','👍')),
  state TEXT NOT NULL DEFAULT 'pending'
    CHECK(state IN ('pending','sending','retry','sent')),
  attempts INTEGER NOT NULL DEFAULT 0,
  next_try_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  sent_at TEXT,
  last_error TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(post_seq,bot_role)
);
CREATE INDEX IF NOT EXISTS idx_channel_reaction_queue
  ON channel_reaction_jobs(state,next_try_at,post_seq);
