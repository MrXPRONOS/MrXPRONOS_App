-- T04: list of bots VERIFIED and actually authorised for private stock.
-- Contains no bot tokens, no private channel or film message references.
-- Adding bots is an explicit one-time owner-session GitHub Actions operation.
CREATE TABLE IF NOT EXISTS cine_private_stock_bots (
 bot_id INTEGER PRIMARY KEY CHECK(bot_id>0),
 username TEXT NOT NULL,
 secret_label TEXT NOT NULL,
 can_post INTEGER NOT NULL CHECK(can_post IN(0,1)),
 verified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
