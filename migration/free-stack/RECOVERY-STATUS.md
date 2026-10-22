# Recovery progress 2026-10-22

Confirmed on Neon project withered-tooth-71931108, database mrxpronos:

- pronostics: 4037 rows copied; source/destination complete row-content digest matches.
- predictions: 2011 rows copied; complete row-content digest matches.
- live_predictions: 6230 rows copied; complete row-content digest matches.
- 12278 copied rows across these three tables; previously copied small tables are separate.
- Neon Auth better_auth provisioned on main branch.
- Neon Data API active on mrxpronos. Anonymous SELECT GRANT + RLS policy on pronostics and predictions only.
- Transactional SET LOCAL ROLE anonymous verified reading pronostics (4037) and predictions (2011), but no SELECT privileges on vip_users or admin_users.
- 10 public-to-public foreign keys in the staging database exist NOT VALID; three auth.users relations must be adapted.
- External HTTP test of Neon Data API has not been verified. No production site switch yet.
- Full 85-table data migration, triggers, SQL functions, policy adaptation, media and functional endpoints remain incomplete.

Keep database URL/password server-only, never in GitHub Pages.


## Reprise après interruption du connecteur — 22 octobre 2026
- Vérifié directement sur Neon : 85 tables, 227 index, 4037 pronostics, 2011 prédictions, 6230 prédictions LIVE.
- Vérifié Neon Data API active.
- Vérifié Cloudflare : script `mrxpronos-neon-staging` bien déployé. Son sous-domaine workers.dev était désactivé ; **activé avec succès** par API Cloudflare. La requête HTTP externe au Worker n'a pas pu être confirmée par les outils web, le Worker reste donc **non validé pour la production**.
- Vérifié Neon Functions : **0 déploiement** sur la branche. Les 19 fonctions Supabase ne sont pas migrées.
- Vérifié Neon Object Storage `videos` : **0 objet**. Les 113 médias ne sont pas transférés.
- Aucune bascule GitHub Pages, aucun webhook Telegram/cron modifié. La migration complète ne peut pas être annoncée comme terminée.


## Contrôle de préparation à la production (2026-10-22)
- Vérification directe Neon : 85 tables, 227 index, 2 politiques RLS seulement ; 4037 pronostics, 2011 predictions et 6230 live_predictions.
- Data API Neon active pour mrxpronos.
- La vérification Cloudflare Workers est bloquée par le contrôle de l'intégration lors de cette session. Impossible de confirmer une requête HTTP publique au nouveau Worker.
- Le nouveau site ne doit pas être pointé vers Neon tant que les 83 autres tables, leurs règles d'accès, les Edge Functions, et le webhook Telegram ne sont pas adaptés et testés.
- Tests nécessaires avant production : endpoints publics GET et erreurs, lecture/écriture authentifiée, refus accès VIP/admin anonyme, Live refresh, callbacks Telegram, publications, médias et rollback.


## Reprise du 22 octobre, fonctions et Telegram
- Neon Functions verifies `quickaction`, `vapidpublickey`, `generateembedding`, `telegrammembership`, `mxhealthprobe`, `mediaimport` as deployed `completed`. Deployment completion is not an HTTP end-to-end assertion. `vapidpublickey` needs VAPID_PUBLIC_KEY, `generateembedding` needs MISTRAL_API_KEY and an authorization gate, `telegrammembership` needs bot token and tested webhook routing.
- The old Cloudflare `xpronos-coupons-bot` Worker is deployed and has a `*/10 * * * *` schedule, bindings including Telegram secrets, and D1-based code with no apparent Supabase URL usage. Actual Telegram delivery was not verified.
- D1 databases `mrxpronos-push-subscriptions` and `mrxpronos-threads-privacy` exist, with application tables `push_subscriptions` and `privacy_requests`.
- Cloudflare deployment of `mrxpronos-privacy-staging` and `mrxpronos-push-staging` via direct connector was blocked; they are not confirmed deployed.
- Sources recovered to migration GitHub branch: `quick-action`, `clean-cache`, `generate-embedding`, `push-notifications`, `telegram_webhook`, `admin-list-subscribers`, `admin-push`. Other original functions reside in `supabase/functions/`. Some source recovery calls were blocked.
- The migration status remains INCOMPLETE: original 19 functions not all migrated; Telegram workflows `bsd-v2-telegram-hourly`, `bsd-v2-telegram-wins`, `telegram-daily-xpvip-promo`, `telegram-channel-monitor-daily` still refer to Supabase secrets; workflow `editorial-telegram` does not. Cron-job.org remote tasks were not inspected in this operation.
- Videos source inventory is 113 files and 215013480 bytes; latest Neon Storage listing has 0 objects. GitHub media copier is staged and uses service role authentication, but no confirmed executed transfer.
- **Production cutover is not verified**. Avoid changing live Telegram webhook, website main branch or granting broad anonymous SQL access until replacement endpoints and media checks pass.
