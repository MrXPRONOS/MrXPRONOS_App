-- Progressive activation: only a bot whose token has been verified gets new jobs.
-- Slots 03..07 were confirmed configured before the initial Github runner check;
-- preserve the existing deployment start watermark for those five slots.
-- Later-added slots 08..12 are registered at the current highest post sequence.
CREATE TABLE IF NOT EXISTS channel_reaction_extra_bot_activation (
  bot_slot INTEGER PRIMARY KEY CHECK(bot_slot BETWEEN 3 AND 12),
  start_after_seq INTEGER NOT NULL CHECK(start_after_seq >= 0),
  activated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO channel_reaction_extra_bot_activation (bot_slot,start_after_seq)
SELECT b.column1, c.start_after_seq
FROM (VALUES(3),(4),(5),(6),(7)) AS b
CROSS JOIN channel_reaction_extra_config AS c
WHERE c.id=1;
