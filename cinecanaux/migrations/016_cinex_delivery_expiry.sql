-- CinéX stage 6: expiry of copies delivered in private chats by CineRadar only.
-- Never delete a source message or a public/library Telegram post.
-- A Telegram bot can normally delete its own outgoing private messages for 48h.
ALTER TABLE cine_delivery_job_items ADD COLUMN delete_after TEXT;
ALTER TABLE cine_delivery_job_items ADD COLUMN delete_retry_at TEXT;
ALTER TABLE cine_delivery_job_items ADD COLUMN delete_state TEXT NOT NULL DEFAULT 'pending'
 CHECK(delete_state IN('pending','deleting','retry','deleted','already_gone','failed','manual_review'));
ALTER TABLE cine_delivery_job_items ADD COLUMN delete_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE cine_delivery_job_items ADD COLUMN delete_lock_until TEXT;
ALTER TABLE cine_delivery_job_items ADD COLUMN deleted_at TEXT;
ALTER TABLE cine_delivery_job_items ADD COLUMN delete_last_error TEXT;
CREATE INDEX IF NOT EXISTS idx_cinex_due_expiry ON cine_delivery_job_items(delete_state,delete_after,delete_retry_at);
-- Backfill existing sent records using the actual delivery timestamp rather
-- than the original request time. No timestamp => no automatic deletion.
UPDATE cine_delivery_job_items
 SET delete_after=datetime(sent_at,'+24 hours'),
     delete_retry_at=datetime(sent_at,'+24 hours')
 WHERE state='sent' AND delivered_message_id IS NOT NULL
   AND sent_at IS NOT NULL AND delete_after IS NULL;
CREATE TABLE IF NOT EXISTS cine_delivery_cleanup_runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 run_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 claimed INTEGER NOT NULL DEFAULT 0,
 deleted INTEGER NOT NULL DEFAULT 0,
 already_gone INTEGER NOT NULL DEFAULT 0,
 retries INTEGER NOT NULL DEFAULT 0,
 failed INTEGER NOT NULL DEFAULT 0,
 manual_review INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_cinex_cleanup_runs_date ON cine_delivery_cleanup_runs(run_at);
