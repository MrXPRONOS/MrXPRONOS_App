# Mr XPRONOS – Inventory of Supabase dependencies and Neon transition

Audit date: 2026-10-23. Source: GitHub main at 83f72e97 plus direct Neon and Cloudflare read-only inspections.
This is a migration progress register, not a certificate that all 206 workflows are migrated.

## Migrated source files (code complete; runtime still needs validation)
| File | Previous source | New backend | Check |
|---|---|---|---|
| scripts/api_football_scheduled_fixtures.py | Supabase `live_scheduled_fixtures` PostgREST | Neon PostgreSQL upsert | no old HTTP client reference; Neon table/unique index verified |
| .github/workflows/api-football-scheduled-fixtures.yml | SUPABASE_URL and service key | NEON_DATABASE_URL GitHub secret | read back from branch |
| scripts/api_football_live_stats.py | Supabase `live_stats_merged`, `live_stats_sources`, `live_provider_probe_cache` | Neon PostgreSQL select/upsert | table layouts/unique indexes verified |
| .github/workflows/enrich-live-market-statistics.yml | SUPABASE_URL and service key | NEON_DATABASE_URL GitHub secret | read back from branch |

Do not merge until the GitHub secret is configured, the offline test workflow passes, and a guarded live execution is reviewed. Do not expose NEON_DATABASE_URL to GitHub Pages/public JS.

## Still connected to Supabase: publication and betting-coupon systems
| Files | Old dependency | Destination | Status |
|---|---|---|---|
| bsd/bsd_v2_telegram.py; bsd/bsd_v2_verify_telegram.py | telegram_sent | Cloudflare D1 ledger (history already migrated); optionally Neon after controlled cutover | Unchanged |
| .github/workflows/bsd-v2-telegram-hourly.yml; bsd-v2-telegram-wins.yml | Supabase credentials | Cloudflare D1 worker adapter | Unchanged on main |
| bsd/bsd_v2_bluesky.py; .github/workflows/bsd-v2-bluesky.yml | telegram_sent | Cloudflare D1 | Unchanged |
| scripts/create_short_from_telegram_coupons.py; scripts/send_short_production_telegram.py; scripts/distribute_short_telegram.py | telegram_sent | Cloudflare D1 | Unchanged |
| scripts/settle_short_production_batches.py; scripts/share_latest_video_bluesky.py | telegram_sent | Cloudflare D1 | Unchanged |
| scripts/post_shorts_video.py; scripts/post_accumulator_social.py | Supabase videos Storage and ledger | Neon Object Storage for new media + Cloudflare D1 for ledger | Unchanged on main; partial changes in migration/coupons-neon-cloudflare-20261023 |
| scripts/read_accumulator_video_ledger.py; scripts/send_accumulator_production.py | telegram_sent | Cloudflare D1 | Unchanged |
| .github/workflows/shorts-coupons-production.yml; shorts-coupons-production-validation.yml; accumulator-photo-production.yml | secrets and Supabase ledger/media | Neon media + Cloudflare ledger | Unchanged on main |

## Still connected to Supabase: site, admin, football and secondary systems
| File(s) | Dependency | Status |
|---|---|---|
| assets/js/main.js | users,counters,analytics,presence,push,actu_foot_news_snapshot | Not migrated; requires secure public API |
| assets/js/admin-real.js; assets/js/admin-supervision.js | Supabase Auth, CMS, analytics, VIP, SQL RPCs | Not migrated; verify auth and privileges first |
| assets/js/web-vitals-monitor.js | Supabase telemetry API | Not migrated |
| assets/js/cms-media-library.mjs; assets/js/cms-revisions.mjs | Supabase Storage and CMS DB | Not migrated |
| assets/js/assistant.js; prono-live/assets/app.js | Supabase edge functions and analytics | Not migrated |
| assets/js/config.js; config.template.js; .github/workflows/deploy.yml | Supabase public config | Not migrated |
| scripts/football_channel.py; scripts/football_match_lifecycle.py | Actu Foot publication/outbox/live RPC and caches | Not migrated |
| scripts/actu_foot_observability.py; scripts/actu_foot_provider_health.py; scripts/actu_foot_source_cache.py; scripts/actu_foot_health_report.py | Actu Foot state and health tables | Not migrated |
| scripts/telegram_channel_monitor_v2.py | Supabase monitor RPCs and state tables | Not migrated |
| scripts/editorial_attribution.py | analytics history | Not migrated; Neon analytics has zero rows |
| scripts/telegram_research/discover_foot_channels.py | Supabase private RPC | Not migrated |
| .github/workflows/football-production.yml; deploy-supabase-functions.yml; telegram-membership-setup.yml | Supabase credentials/deploys | Not migrated |
| .github/workflows/push-notifications.yml; clean-cache.yml; validate_predictions.yml; apply-supabase-migrations.yml | Supabase Edge Functions | Not migrated |
| .github/workflows/telegram-channel-monitor-daily.yml; editorial-analytics.yml; telegram-foot-discovery.yml | Supabase credentials | Not migrated |

## Leave retired jobs untouched unless specifically reactivated
daily-update.yml (if false), daily-pronos.yml (if false), telegram-simple-coupons.yml (if false), create-video.yml (if false), live-refresh-failover.yml (manual rollback only).

## Backends / blockers observed
- Neon already has target live tables and PostgreSQL indexes. This does not prove that the GitHub NEON_DATABASE_URL secret exists.
- Neon telegram_sent had zero rows at audit time, while Cloudflare D1 publication ledger had 737 including 733 migrated legacy rows and four new live entries. Avoid creating two active write authorities.
- Neon analytics and users also had zero rows. Migrate relevant data before switching those features.
- Cloudflare R2 was not enabled on the account; use approved Neon Object Storage for new media after confirming public delivery URL.
- Existing `migration/coupons-neon-cloudflare-20261023` branch is not equivalent to deployment; it includes workflows that checkout main, and its D1 PostgREST compatibility needs pagination and validation checks.
- New offline CI workflow: `.github/workflows/neon-migration-adapters-tests.yml`. Runtime integration and scheduler status have not been verified.

## Safe validation gate
1. Confirm private GitHub secret NEON_DATABASE_URL without revealing its value.
2. Pass new offline migration tests.
3. Run guarded fixture and live-enrichment jobs and compare provider quota, rows and payload schema.
4. Cut over one workflow group at a time; maintain production rollback.
5. Migrate dependent telemetry/auth/CMS functions before retiring Supabase; do not delete old storage objects still referenced.


## Implementation update — 2026-10-23, round 2

**Code migrated on this branch; do not equate with a tested production cutover:**
- Telegram singles/combinations: `bsd/bsd_v2_telegram.py`, `bsd/bsd_v2_verify_telegram.py`.
- Bluesky: `bsd/bsd_v2_bluesky.py`, `scripts/share_latest_video_bluesky.py`.
- Shorts and batch settlement: `scripts/create_short_from_telegram_coupons.py`,
  `scripts/send_short_production_telegram.py`, `scripts/distribute_short_telegram.py`,
  `scripts/settle_short_production_batches.py`, `scripts/post_shorts_video.py`.
- Daily accumulator: `scripts/read_accumulator_video_ledger.py`,
  `scripts/send_accumulator_production.py`, `scripts/post_accumulator_social.py`.
- Supporting modules: `scripts/neon_telegram_ledger.py` (private PostgreSQL, atomic unique claims)
  and `scripts/neon_public_media.py` (Neon S3 with externally verified public CDN URL).
- Configuration: `bsd-v2-telegram-hourly.yml`, `bsd-v2-telegram-wins.yml`,
  `bsd-v2-bluesky.yml`, `shorts-coupons-production.yml`,
  `shorts-coupons-production-validation.yml`, `accumulator-photo-production.yml`.
- API-Football scheduled and live market statistics files migrated in round 1.

**Data migration:** Cloudflare D1 publication-ledger history copied idempotently into Neon
`public.telegram_sent`; comparison showed 739 matching entries in both backends,
broken down by `kind` and unique `(kind,ref_id,ref_date)` on Neon at the time checked.
Since D1 remains live, perform one final differential sync and disable the OLD writers
atomically at cutover. Do not delete D1 history.

**Mandatory blockers to production:**
1. GitHub secrets `NEON_DATABASE_URL`, `NEON_S3_ENDPOINT`,
   `NEON_S3_ACCESS_KEY_ID`, `NEON_S3_SECRET_ACCESS_KEY`,
   `NEON_PUBLIC_MEDIA_BASE_URL` must be provisioned/tested by deployment environment;
   their existence is not confirmed.
2. Neon S3 public CDN URL for Instagram/Threads must be proven with GET and correct MIME;
   the uploader intentionally fails closed if unconfigured.
3. Offline compile/tests and real dry-runs for every migrated workflow are still not confirmed.
4. **Actu Foot is NOT migrated:** production scripts and RPCs still rely on Supabase.
5. **Administration and site interface are NOT migrated:** Neon `users`, `admin_users`
   and `analytics` are empty; Neon tables require RLS and have no anonymous SELECT grants.
   Do not expose privileged credentials in public JS and do not remove Supabase Auth
   without a tested Neon Auth account migration and role mapping.
6. Production `main` remains unchanged; this branch/PR is a draft.

**Non-functional constraints preserved:** no modifications to coupon rendering,
site CSS, video frames, football prediction calculations, banners or match selection algorithms.


## Reprise et contrôles — 23 octobre 2026

- Neon PostgreSQL `users`: **7 157 lignes** (historique utilisateur complet).
- Neon PostgreSQL `analytics`: **11 212 lignes** (historique analytics complet).
- Neon PostgreSQL `telegram_sent`: **739 lignes** conservant les garde-fous anti-doublons.
- Neon PostgreSQL `admin_users`: **1 administrateur**.
- Nouveau site public : Neon Data API avec `allowAnonymous: true` (jeton anonyme fourni par Neon Auth) au lieu d'accès REST sans JWT. Corrigé dans `assets/js/main.js`, `prono-live/assets/app.js`, `assets/js/assistant.js`, `assets/js/web-vitals-monitor.js`.
- `public.mx_site_counter` et `public.mx_site_event` créées avec paramètres contrôlés et droits d'exécution limités, puis raccordées dans `assets/js/main.js`. Les formulaires de l'administration utilisent Neon Auth.
- Tests Python adaptés pour simuler Neon plutôt que Supabase : routage Telegram, événements Actu Foot, photos BSD, combinés et batch nocturne. Les exécutions du dernier commit GitHub doivent encore terminer avant fusion.
- **Bascule en production NON effectuée.** Reste à confirmer GitHub Actions secrets et URL média publique, API Cloudflare pour push/admin, tests navigateur administrateur, scripts CMS média et workflows secondaires. Le référentiel `main` demeure inchangé.
