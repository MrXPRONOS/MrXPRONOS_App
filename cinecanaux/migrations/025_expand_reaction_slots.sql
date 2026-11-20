-- Migration 025: extend additional Telegram reaction slots without deleting old jobs.
-- Compatible with existing GitHub processing and its per-slot activation watermarks.
-- All existing delivery states, attempt counts and activation dates are preserved.

CREATE TABLE channel_reaction_extra_jobs_expanded (
  post_seq INTEGER NOT NULL REFERENCES channel_reaction_posts(seq),
  bot_slot INTEGER NOT NULL CHECK(bot_slot BETWEEN 3 AND 9999),
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
INSERT INTO channel_reaction_extra_jobs_expanded (
  post_seq,bot_slot,emoji,state,attempts,next_try_at,last_error,sent_at,updated_at
)
SELECT post_seq,bot_slot,emoji,state,attempts,next_try_at,last_error,sent_at,updated_at
FROM channel_reaction_extra_jobs;
DROP TABLE channel_reaction_extra_jobs;
ALTER TABLE channel_reaction_extra_jobs_expanded RENAME TO channel_reaction_extra_jobs;
CREATE INDEX idx_channel_reaction_extra_pending
  ON channel_reaction_extra_jobs(state,next_try_at,post_seq);

CREATE TABLE channel_reaction_extra_bot_activation_expanded (
  bot_slot INTEGER PRIMARY KEY CHECK(bot_slot BETWEEN 3 AND 9999),
  start_after_seq INTEGER NOT NULL CHECK(start_after_seq >= 0),
  activated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO channel_reaction_extra_bot_activation_expanded (bot_slot,start_after_seq,activated_at)
SELECT bot_slot,start_after_seq,activated_at FROM channel_reaction_extra_bot_activation;
DROP TABLE channel_reaction_extra_bot_activation;
ALTER TABLE channel_reaction_extra_bot_activation_expanded
  RENAME TO channel_reaction_extra_bot_activation;
