-- Ciné Radar: notifications privées propriétaire, sans messages publics ni médias.
-- Compatible avec les bases D1 déjà migrées (additif et réexécutable).
CREATE TABLE IF NOT EXISTS radar_notice_log (
  owner_id INTEGER NOT NULL,
  title_id TEXT NOT NULL REFERENCES radar_titles(id) ON DELETE CASCADE,
  sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(owner_id,title_id)
);
CREATE INDEX IF NOT EXISTS idx_radar_notice_log_sent_at ON radar_notice_log(sent_at);
