# Shared Telegram queue

All personal-session workflows use the same lock mrx-telegram-personal-account, queue: max, cancel-in-progress: false. No concurrent personal logins.

The 2026-11-24 queue incident was caused by a bulk YAML safety edit (PR #664) triggering operational jobs on push. The eleven affected workflows now use explicit trigger files under .github/telegram-triggers/<workflow-name>.txt instead of their own YAML path. Existing manual dispatch, schedules and substantive script-change triggers remain unchanged. A workflow-only configuration change no longer opens the Telegram session for those jobs. To explicitly trigger a job, use workflow_dispatch with its normal inputs, or update its dedicated marker when an authorized operational push is intended.

Already queued jobs are not cancelled. Formation runs at 08:00 and 20:00 UTC; a queued run is not proof of a publication. Inspect the relay job and durable receipts. Never remove the shared lock or bypass FloodWait.
