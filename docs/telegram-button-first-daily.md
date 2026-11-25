# Telegram button-first daily publishing

Telegram Bot API cannot put posts into the native scheduled-message queue. A user MTProto session can native-schedule, **but it cannot create the bot's inline-keyboard URL buttons on channel posts**. Do not silently replace required buttons with plain text links.

The dedicated `telegram-bot-buttons-daily.yml` handles only the four unchanged, approved promotional publishers:
- 06:00 UTC: weekly day-specific bookmaker promotions (`send_day_based_bookmaker_promos.py`)
- 06:30 UTC: XPVIP common image (`send_daily_partner_promo.py`)
- 07:00 UTC: rotating bonus (`send_daily_bookmaker_bonus_ads.py`)
- 07:30 UTC: rotating guide (`send_daily_bookmaker_guide.py`)

One GitHub workflow file, four short daily cron triggers. No long-running runner and no personal Telegram connection. These are Bot API posts made at actual publication times; **there is no genuine week-long bot-side scheduled queue**. The per-day content may be based on a weekly rotation, but publishing still needs one bot API request on each publication day.

Feature gate `TG_BOT_BUTTONS_DAILY_ENABLED=true` must be explicitly set after private-channel tests and a review of cron-job.org jobs; otherwise no scheduled publication from the new workflow. The same feature gate skips the four old workflows, including external dispatches. Existing atomic `telegram_promo_deliveries` campaign/day/chat reservations continue preventing duplicate posts during switchovers. Manual previews work on the new workflow without credentials; manual execution also requires the feature gate.

Actual inline keyboards are built by the original `telegram_rich.post_photo` pipeline: first rich buttons, then a legacy `sendPhoto` with the **same `reply_markup.inline_keyboard`** when the rich format is unsupported. The original sender codes, captions, approvals, image files, bot identity and target channels are unchanged. If bot identity or permissions fail, the posting run fails; no replacement with a message lacking buttons.

Other essential-button publishers already in production remain unchanged: `scripts/cineradar_daily_promo.py` (Ciné Radar button via Bot API, after inventory in discovery workflow), `scripts/send_cinema_ebook_and_folder.py` (ebook/folder buttons), `scripts/send_short_production_telegram.py` and `scripts/distribute_short_telegram.py` (video buttons), and promotions attached to CineX film delivery. They must **never** be migrated to native user-scheduled messages without preserving buttons and prerequisites. Live/late-breaking football, coupons and crypto also must remain event-driven where data did not exist in advance.

No daily buttons workflow should be enabled until all applicable legacy schedules (including cron-job.org) are audited. This migration does not edit cron-job.org directly: the four old workflow runs are skipped when the gate switches, but cron-job.org may still cause no-op GitHub dispatches. The bot-only workflow uses a separate concurrency group; the 30-minute personal account cooldown applies only to MTProto account sessions, not Telegram Bot API calls. The four publication slots themselves have 30-minute start separation.

All native Telegram manifest scheduling remains for **button-free posts only**. The draft weekly native promotional workflow and its text-link substitutions have been removed to enforce this policy.


## Production activation 2026-11-25

After the read-only preflight succeeds with the current production bot and both explicitly configured channels, the new daily workflow becomes active by default on `main`. The four legacy promotion jobs stop at their job-level gate, even if cron-job.org keeps dispatching their old workflow files. No promo is sent without a live preflight (bot identity, two channel admin rights, Supabase ledger, complete button templates).

Emergency rollback without a code change: create/update GitHub Actions repository variable `TG_BOT_BUTTONS_DAILY_ENABLED=false`. That stops the centralized daily workflow and re-enables the four legacy workflows. To restore new production system set it to `true` or remove the variable. **Don't set it to false casually** since cron-job.org legacy schedules would resume. The database campaign/day/channel ledger remains shared in either mode.

Approval allowlists are authoritative: `TELEGRAM_APPROVED_DAY_PROMOS`, `TELEGRAM_APPROVED_BONUS_BOOKMAKERS`, `TELEGRAM_APPROVED_GUIDE_BOOKMAKERS`. Non-approved campaigns are skipped rather than sent. Saturday/Sunday have no day-specific promo and Sunday has no separate guide. GitHub scheduled triggers can be delayed; monitor runs for missing hours and inspect recipient channel content. Do not manually retry an ambiguous Telegram network send without ledger reconciliation.
