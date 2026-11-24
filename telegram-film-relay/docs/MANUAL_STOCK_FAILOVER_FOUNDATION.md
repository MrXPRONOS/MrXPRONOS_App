# Telegram manual vault fallback — design and operational preflight (24 November 2026)

## Status: foundation only — NO live fallback and NO Telegram channels created

This branch provides an offline decision engine and tests. It is not deployed,
publishing or verified end-to-end. No production workflow calls this module yet.

### Existing architecture

- Classic film relay: Telethon owner session, private video library, bot public
  posters and central CineRadar D1 stock; cap two films/run.
- Series/Anime: season catalogs, batch/episode receipts, private indexes,
  CineRadar download links and V4 public/private button contracts.
- Comedy/Action/Desir: category caps of two items/cycle.
- Formation: one distinct course/category/cycle, five destinations,
  technical private stage and durable HMAC receipts.
- Existing Secours channels are audience-facing backup channels, NOT necessarily
  suitable as owner-only upload vaults.
- Anime Bot V2 polling is not production enabled and must not compete for
  getUpdates on an existing shared bot.

### Controlled rollout plan

1. Inventory actual existing private libraries, stage and owner stock using a
   functioning authorized session. Confirm exact chat IDs and bot permissions.
2. Provision only missing owner-only channel(s) after explicit approval, at
   most one new channel per cycle; do not create channels when user session is
   unavailable, on a name collision, or where rights cannot be checked.
3. The owner uploads authorized posters/videos, numbered episodes or courses.
   A single exclusive channel_post consumer captures updates to a private
   durable registry with exact message and file identities. History before bot
   membership requires a separate authorized one-time import.
4. Pair real poster and media conservatively; ambiguous titles, duplicate
   variants, missing season/episode or course boundaries go to review.
5. Reconcile receipts from the existing normal-mode publishers. Store private
   Telegram identifiers only in protected durable state, never public GitHub.
   file_unique_id is a comparison hint, not a sendable file_id.
6. Personal session is primary. Only missing/revoked credentials permit fallback;
   FloodWait, PeerFlood, uncertain sends and timeouts STOP, not bypass.
7. Use one common publication lock, same quotas including normal-mode usage,
   and write-ahead inflight/uncertain/complete receipts.
8. Reuse existing V4 publication contracts and CineRadar registration; do not
   create another publisher bypassing buttons, TTL or active season batches.
   Formation preserves its course/group semantics, quotas and attribution.
9. Require authorized content, verified bot admin rights and owner-configured
   channel mapping. No automatic channel or source authorization from discovery.
10. Validate offline tests, Telegram preflights and one licensed real item for
    every category before enabling live mode; feature flag defaults OFF.

### Alerts and unresolved integration requirements

Show counts per category: stored, eligible, duplicates, quarantined, pending,
delivered, remaining quota, session health and uncertain operations. Keep
tokens/invite links/private IDs out of public logs.

The existing main film GitHub workflow unconditionally demands the personal
credentials before publication. A production fallback will need to restructure
that preflight; adding a late fallback step alone cannot work. The existing bot
may already have a webhook or getUpdates consumer; do not steal its updates.
Protected messages, non-transferable data and copyright restrictions must
remain enforced in every mode.

This PR deliberately contains no automatic posting, new Telegram channel,
permission grant, secret manipulation or switch to production.
