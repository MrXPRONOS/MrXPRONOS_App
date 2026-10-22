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
