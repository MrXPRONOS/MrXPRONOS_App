Migration checkpoint 2026-10-22

Confirmed:
- Neon PostgreSQL has 85 tables, 227 indexes and copied prediction data.
- Neon Functions deployed: quickaction, generateembedding, vapidpublickey, telegrammembership, mxhealthprobe and mediaimport.
- HTTP tests: quickaction and mxhealthprobe return 200. telegrammembership has no configured bot token; vapidpublickey and generateembedding return 503 with missing configuration.
- 113 MP4 videos: 215013480 bytes inventoried, zero original videos migrated.
- GitHub OIDC to Neon mediaimport: successful test, 200 response, SHA256 reread verification, test file deleted.
- Supabase Storage authenticated download returns HTTP 402 Payment Required to GitHub Actions, including service-role credential. Requires restoring source access or alternate backups.
- Telegram webhook still points to Supabase; no endpoint switch performed.
- No production cutover.

Evidence:
https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/39731905359
https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/39731238869
https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/39731397235
https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/39730958558
