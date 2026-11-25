# Telegram Smart Scheduler V1 — lot 1 only

No publication or cron is activated by this module. Existing workflows remain unchanged.
Install the SQL once via a reviewed Supabase migration (not on each run). Telethon 1.45.0 matches the existing film relay requirements. Use only authorized content and destinations.

Backend environment: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, TG_API_ID, TG_API_HASH, TG_SESSION_STRING (existing aliases supported), TG_SCHEDULER_ACCOUNT_ID (numeric personal account), TG_SCHEDULER_ALLOWED_PEERS (comma-separated marked numeric peer IDs), TG_SCHEDULER_ENABLED=1 only after migration and controlled validation. Do not expose these secrets to public clients or logs. Existing TG_PERSONAL_COOLDOWN_UNTIL_UTC is honored.

Use `async with TelegramScheduler.from_env(hours=24) as scheduler:` (168 for weekly), and await scheduler.schedule(peer, slot, stable_key, text=..., file=..., kind=...). Slots are UTC aware, second precision, at least 60 seconds in future and strictly inside rolling horizon. window_slots computes daily clock slots in UTC; integrations must choose a suitable lead time, not silently skip due content. No inline bot keyboards, albums, forwarding, deletion, edits or live fallback in this first adapter. Future modules must explicitly support those formats before migrating affected workflows. Upload video queue conversion may yield a different date: treated as uncertain, never retried automatically.

Database lock is global, non-expiring, atomic. Release only after disconnect is confirmed; 1800 seconds minimum from database release, longer FloodWait plus 300 seconds. A crash/ambiguous disconnect leaves lock held: operator must confirm old runner is stopped, review Telegram queue, then use service-role RPC release with the recorded owner; never clear the lock directly or shorten the cooldown. An unavailable DB prevents opening a session. A failed release also blocks later runs. GitHub concurrency group mrx-telegram-personal-account remains an additional protection; legacy clients do not yet participate in the DB lock. Do not enable live scheduler while legacy clients can overlap.

Registry reserves peer/slot/logical key and payload fingerprint before any send. Pending/accepted/uncertain rows prevent automatic repeat after crashes or ambiguous network outcomes. Verified means queue ID and UTC date were confirmed, not that the eventual public message was delivered. Scheduled IDs are not published IDs. A duplicate verified row is a ledger result, not a fresh queue check. Operators must reconcile uncertain rows against Telegram's queue and published history; no auto-retry, no destructive cleanup or automatic takeover. A later adapter can add explicit reconciliation/cancel/edit after tests. No claim of exactly-once delivery across external services.

Offline CI uses fakes; no Telegram secrets needed. Real private test-channel smoke test, database RPC concurrency and full legacy migration are separate rollout gates. No public publication in lot 1.


## Renforcement après audit

La fonction `preflight_queue` contrôle la capacité par canal (garde conservatrice à 90 messages, limite variable côté Telegram). Le doublon confirmé est revérifié contre la file Telegram. Aucun « succès » n'est inféré d'une simple ligne Supabase si le message a été annulé manuellement. Le vérificateur télécharge la file de messages programmés : les arguments `ids` ne sont pas filtrants en mode `scheduled=True` dans Telethon.

### Manifests

Préparer un manifeste JSON, puis tester sans connexion :

```sh
python scripts/telegram_scheduler_manifest.py --manifest /tmp/approved_posts.json
```

Publication explicite, lorsque tous les prérequis sont en place : `python scripts/telegram_scheduler_manifest.py --manifest /tmp/approved_posts.json --execute`. Une publication comporte : `peer` (ID numérique marqué -100...), `at` (UTC ISO), `key` stable, `kind` (text/image/video/document), `text`, `file` chemin local sous la racine de travail (si média) et `parse_mode` (null/html). Aucune programmation n'est permise sans manifeste valide, autorisation des destinations et `TG_SCHEDULER_ENABLED=1`.

Les systèmes existants de publications ne sont PAS encore branchés à cet adaptateur. Le code de migration n'ajoute aucun vieux cron de publication et ne désactive aucun système sans relève. Un compte utilisateur MTProto n'est pas un bot et les claviers inline bot ne sont pas conservés automatiquement.


## Boutons obligatoires

Les promotions avec boutons ont été sorties de la programmation native. Le nouveau `telegram-bot-buttons-daily.yml` utilise les scripts de bots existants et conserve leurs `inline_keyboard`. Les workflows Cine Radar, e-book/dossier, vidéos de pronostics et CineX conservent leurs publications Bot API existantes, sans migration vers la file native. Voir `telegram_scheduler/BUTTONS.md`. Tout manifeste natif contenant des boutons doit être refusé plutôt que dégradé en liens texte.
