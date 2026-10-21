# Déploiement Mr XPRONOS LIVE sur Render

Service Render (test isolé) : https://dashboard.render.com/web/srv-dbcg606i0phs73aa3ld0

Code GitHub : branche `migration/render-live-engine`, dossier `render/live/`.
**Ne pas fusionner ni remplacer les crons de production avant la recette.**

## Qu'est-ce qui est réellement porté ?

Le code `supabase/functions/live/index.ts` est exécuté par Deno dans Render.
Son texte est identique au fichier `main`, **à une exception** : `LIVE_BATCH_ENDPOINT` redirige les invocations `/refresh/batch` vers `localhost:8000` (elles ne repartent plus vers Supabase Edge). Tous les calculs, probabilités, seuils, sources et règles ont été conservés.

Le module indépendant `supabase/functions/telegram-live/index.ts` est exécuté dans un second processus Deno ; la seule différence est le port local 8001. Sa route reste `/telegram-live`.

Le serveur HTTP Render expose le port 10000. Il fait uniquement proxy vers les processus 8000 (moteur) et 8001 (Telegram indépendant). Le `engine_bootstrap.ts` reproduit `EdgeRuntime.waitUntil` afin que `POST /refresh` rende un HTTP 202 rapidement, sans interrompre le travail asynchrone du moteur.

La base PostgreSQL et les stockages historiques **restent chez Supabase**. Cette migration ne déplace que l'exécution, pas les tables ou les données.

## Environnement et sécurité

Dans Render > service `mrxpronos-live-engine-migration` > **Environment**, configurez les valeurs secrètes directement dans le tableau Render, **jamais dans GitHub ni dans une conversation**.

Variables **requises** pour activer le moteur :
- `SUPABASE_URL` : URL actuelle du projet Supabase (publique).
- `SUPABASE_SERVICE_ROLE_KEY` : vraie clé de serveur (pas une clé `anon`/publishable de test). Réservée à Render, jamais aux clients.
- `CRON_SECRET` : même secret que les appels cron de production (renouveler soigneusement si nécessaire).
- `BSD_API_TOKEN` : jeton du fournisseur de données principal.

Variables à **reproduire** pour conserver les fonctionnalités : `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_CHAT_ID_SECONDARY`, `SITE_URL`, `DEBUG_KEY`, `BSD_TZ`, `ENABLE_ESPN_MERGE`, `LIVE_PROP_ODDS_URL`, `LIVE_PROP_ODDS_TOKEN`, `LIVE_REQUIRE_BOOKMAKER_LINE`, `MOVIODDS_API_KEY`, `LIVE_ODDS_*`, `LIVE_REFRESH_BATCH_SIZE`, `LIVE_REFRESH_MAX_BATCHES`, `BSD_STATS_MAX_CALLS_PER_REFRESH`, `BSD_STATS_REFRESH_SECONDS`, `SPORTSCORE_STATS_REFRESH_SECONDS`, `BSD_STATS_QUOTA_RESERVE`.

Contrôles Render :
- `RENDER_LIVE_ENABLED=0` : standby, n'importe quel appel métier reçoit 503 ; **aucune prédiction/aucun message**.
- `RENDER_LIVE_ENABLED=1` : démarre les deux moteurs Deno uniquement si les quatre variables obligatoires existent.
- `RENDER_LIVE_READONLY=1` (par défaut) : les GET restent possibles mais les POST publics sont bloqués (403). **Pas de refresh, ni publication Telegram.**
- `RENDER_LIVE_READONLY=0` : ouvre les POST métiers quand les tests et la bascule des crons sont autorisés.
- `RENDER_DEDICATED_TELEGRAM=1` (par défaut en mode actif) : exécute le second handler Telegram LIVE.
- `LIVE_BATCH_ENDPOINT` : fixé automatiquement dans le processus moteur à `http://127.0.0.1:8000/refresh/batch`; ne pas le modifier côté Render.

### Routes

- Santé : `GET https://mrxpronos-live-engine-migration.onrender.com/healthz`
- Audit du code : `GET https://mrxpronos-live-engine-migration.onrender.com/audit`
- Lecture LIVE : `GET /matches`, `GET /opportunities`, `GET /today`, `GET /daily/today`, `GET /predictions/history`, `GET /predictions/by-id?id=...`.
- Maintenance sécurisée : `POST /refresh` (chaque minute), `POST /validate` (existant), `POST /telegram/process-one`, `POST /daily/generate`, `POST /daily/validate` ; en-tête `x-cron-secret` requis.
- Telegram indépendant : `GET /telegram-live/status` et `POST /telegram-live` avec le même secret.

## Checklist de recette pour activation

1. Build Docker et `LIVE_SOURCE_PARITY_PASS` + `TELEGRAM_SOURCE_PARITY_PASS` validés, sans déviation des modèles.
2. Render `/healthz` indique moteur démarré, les routes GET de lecture répondent correctement.
3. Installer les **vraies** variables Supabase / BSD / Telegram sur Render sans les publier.
4. Tester un cycle réel avec base et canaux de test **isolés**, en vérifiant 100+ rencontres, le respect du plafond de quota BSD et les chiffres `processed_matches`, `matches_missing_minute`, `market_diagnostics`, `predictions_created`.
5. Comparer plusieurs prévisions identiques (même snapshot minute, score, statistiques) entre le moteur Supabase Edge de référence et Render : `threshold`, `probability`, `reliability`, `data_quality_score`, `signal_tier`, `baseline_threshold`, `selected_uplift`, `model_version`.
6. Tester `savePrediction` et ses contraintes idempotentes, les verrous `claim/renew/release_live_refresh`, validation instantanée/finale et historiques.
7. Tester les coupons image et texte fallback, puis confirmer une seule livraison par canal et par signal; valider la fonction Telegram séparée.
8. Tester `/daily/today`, `/daily/generate`, `/daily/validate` et la compatibilité du site GitHub Pages.
9. **Basculer les crons seulement après validation des huit points précédents**. Mettre à jour cron-job.org (et tout failover GitHub) afin que `POST /refresh` pointe vers Render à une minute, `POST /validate` vers Render à l'intervalle conservé. Ne jamais conserver deux déclencheurs primaires concurrents ; conserver un failover contrôlé par le verrou DB.
10. Retirer le blocage `RENDER_LIVE_READONLY=1` uniquement pendant une bascule contrôlée, surveiller `cron_runs`, logs Render, qualité des statistiques et livraison Telegram. Rollback : rétablir les crons Supabase Edge d'origine et mettre `RENDER_LIVE_ENABLED=0`.

## Restrictions du plan gratuit

Render Free se met en veille après 15 minutes sans requête externe. La remise en route peut prendre près d'une minute. Render accorde **750 heures gratuites par mois et par workspace**, partagées entre tous les services Free ; un seul service sollicité toutes les minutes pendant 30 jours consommerait environ 720 heures. La limite de mémoire et de CPU (512 Mio et faible CPU) et les quotas/fournisseurs football ne permettent pas de **garantir** toutes les statistiques de 100 matchs chaque minute.

**Ne jamais considérer le déploiement comme une migration opérationnelle complète avant les tests avec les véritables variables et une surveillance sur plusieurs cycles.**

## Rapport d'audit détaillé

Voir `render/live/MIGRATION_AUDIT.md` : inventaire des techniques de calcul, filtres, qualité, sources, Telegram, validation, modes et états de recette.
