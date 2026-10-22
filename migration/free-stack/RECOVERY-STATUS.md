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
