-- Ciné Radar: journal privé des suggestions envoyées au propriétaire.
-- Aucun secret, contenu média ou identifiant de spectateur.
CREATE TABLE IF NOT EXISTS radar_notice_log (
  owner_id INTEGER NOT NULL,
  title_id TEXT NOT NULL REFERENCES radar_titles(id) ON DELETE CASCADE,
  sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(owner_id,title_id)
);
CREATE INDEX IF NOT EXISTS radar_notice_recent ON radar_notice_log(sent_at);
