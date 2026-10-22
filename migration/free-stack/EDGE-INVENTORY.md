# Supabase Edge Functions — verified source inventory

Date: 2026-10-22. 19 functions currently deployed on Supabase. Source contents were retrieved through the Supabase connector. **None of these 19 functions is yet deployed to Neon.**

| Slug | Size | Migration note |
|---|---|---|
| `quick-action` | small | No direct database reference |
| `assistant` | large | Supabase client; AI dependencies |
| `live` | very large | 10 source files, data providers, Telegram logic |
| `clean-cache` | small | Supabase client |
| `generate-embedding` | small | Deno runtime and model dependency |
| `vapid-public-key` | small | VAPID env secret |
| `push-subscribe` | small | Supabase client |
| `push-notifications` | small | Supabase client and VAPID |
| `publish` | medium | Supabase client and CMS |
| `telegram_webhook` | large | Supabase client and bot state |
| `admin-push` | small | Supabase client, privileged access |
| `admin-list-subscribers` | small | Supabase client, privileged access |
| `live-scrape-test` | very large | 4 files, Supabase client |
| `telegram-live` | medium | 3 files, Supabase client |
| `daily-pronos` | medium | Supabase client |
| `telegram-membership` | small | Telegram permissions logic |
| `threads-uninstall` | small | Supabase client, deletion workflow |
| `threads-data-deletion` | small | Supabase client, deletion workflow |
| `xpronos-coupons-bot` | medium | 2 files, Supabase client |

## Blocking incompatibilities

Supabase Edge Functions are implemented in **Deno** and most use `supabase-js`. Neon Functions deploy **Node.js 24** and inject a PostgreSQL connection string; copying TypeScript verbatim does not reproduce their storage, auth, RPC, API, Realtime or Telegram behavior. Do not expose privileged database credentials or webhook tokens.

- Inventory source file counts: `live` 10, `live-scrape-test` 4, `telegram-live` 3, `publish` 2, `xpronos-coupons-bot` 2; remaining functions mainly a single entry.
- Before Telegram webhook cutover, migrate and test idempotency, secrets, bot access, channel IDs, signature checks, dedupe and state.
- Keep production webhook unchanged until replacement passes end-to-end tests.
- GitHub workflows in the migration branch are **not executed automatically**.
- Media workflow relies on `NEON_S3_ENDPOINT`, `NEON_S3_ACCESS_KEY_ID`, and `NEON_S3_SECRET_ACCESS_KEY` repository secrets. Script and 113-object inventory exist on this branch; no objects have been transferred by the tool session.
