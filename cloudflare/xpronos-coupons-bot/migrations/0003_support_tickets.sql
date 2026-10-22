-- Free Pronos : centre d'aide avec tickets isolés dans D1.
CREATE TABLE IF NOT EXISTS support_tickets (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id),
 message TEXT NOT NULL CHECK(length(message)>0 AND length(message)<=800),
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','replied','closed')),
 admin_reply TEXT,
 replied_at TEXT,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_support_user ON support_tickets(user_id,created_at);
CREATE INDEX IF NOT EXISTS idx_support_pending ON support_tickets(status,created_at);
