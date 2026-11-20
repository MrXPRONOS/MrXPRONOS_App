-- Restore old access-denied jobs for slots 03..16 after the new retry policy is deployed.
-- No publication is sent by this migration; only the reaction queue is updated.
-- The new worker will retry at most once per 15-60 minutes after Telegram
-- reports that the bot cannot currently access a chat.
UPDATE channel_reaction_extra_jobs
SET state='retry',
    next_try_at=CURRENT_TIMESTAMP,
    updated_at=CURRENT_TIMESTAMP
WHERE state='blocked'
  AND bot_slot BETWEEN 3 AND 16
  AND last_error='telegram_http_400:chat_not_found';
