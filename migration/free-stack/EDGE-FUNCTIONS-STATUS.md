# Portage Supabase Edge Functions → Neon, 22 octobre 2026

Les 19 fonctions sont recensées ci-dessous. **Ne pas changer les endpoints de production sur la seule base du statut deployed** : les secrets et les tests HTTP réels restent à réaliser.

## Déployées sur Neon (Node.js 24, statut completed)
- `vapid-public-key` → `vapidpublickey`. Source : `migration/free-stack/neon-functions/vapid-public-key/index.mjs`. Secret requis `VAPID_PUBLIC_KEY` (clé publique, absent pour l'instant) ; retourne 503 s'il est absent.
- `quick-action` → `quickaction`. Nécessite `QUICK_ACTION_TOKEN` dans l'environnement Neon ; **pas encore équivalent à l'ancienne vérification de JWT Supabase**, conserver hors production jusqu'au changement d'authentification du client.
- `generate-embedding` → `generateembedding`. Nécessite `MISTRAL_API_KEY` et `EMBEDDING_API_TOKEN`, requêtes POST authentifiées, limite d'entrée. Le nouveau token protège contre la consommation gratuite non autorisée.
- `telegram-membership` → `telegrammembership`. Nécessite `TELEGRAM_BOT_TOKEN` ou `FOOTBALL_NEWS_BOT_TOKEN`. Secret de webhook dérivé SHA-256 comme l'original. **Webhook Telegram non redirigé tant que le token n'est pas configuré et les tests webhook non validés**.

Les fonctions sont en ligne selon le contrôleur Neon, mais ne sont pas intégrées au site. Aucun secret de production n'a été révélé ou inventé.

## Portage SQL complémentaire
- `clean-cache` → `mrx_internal.clean_cache()` sur Neon, inaccessible aux rôles `anonymous` et `authenticated` (privileges testés). Fonction de suppression équivalente (FAQ >30 jours, conversations >7 jours). Non exécutée, scheduler non activé. Source SQL : `migration/free-stack/neon-functions/clean-cache/internal-clean-cache.sql`.

## Autres fonctions encore à adapter, non déployées
- `assistant` : accès DB Supabase, modèle Mistral/HF/Groq et protections API
- `live` : moteur LIVE très volumineux, multiples sources football, DB et Telegram, environnement Deno
- `push-subscribe` : upsert des abonnements dans PostgreSQL
- `push-notifications` : web-push + VAPID et lecture/gestion des abonnements
- `publish` : GitHub CMS avec authentification forte et contrôles de publication
- `telegram_webhook` : assistant bot + tables SQL/Telegram
- `admin-push` : droits admin/cron et Web Push
- `admin-list-subscribers` : liste des abonnements protégée admin
- `live-scrape-test` : moteur de scraping et rendu très volumineux, dépendances propres à Deno
- `telegram-live` : notifications LIVE, images et deux canaux, PostgreSQL
- `daily-pronos` : récupération BSD, persistance et validation des pronostics
- `threads-uninstall` : vérification Meta/HMAC, enregistrement des demandes de confidentialité
- `threads-data-deletion` : vérification Meta/HMAC, confirmation et suivi de suppression
- `xpronos-coupons-bot` : workflow coupons, permissions et DB transactionnelle

## Critères de mise en production
1. Transfert complet des tables et données + restauration des fonctions SQL/triggers/RLS/permissions.
2. Ajout protégé des secrets côté Neon. Aucun secret dans le dépôt public, le frontend ni dans les réponses HTTP.
3. Tests de chaque fonction : succès nominal + refus d'un appel non autorisé + cas secrets manquants.
4. Pour Telegram : configurer le nouveau webhook uniquement après tests, ne pas dupliquer les anciens déclencheurs.
5. Réécrire les routes/frontend/GitHub Actions/Cron-job.org puis vérifier en production et conserver une procédure de retour arrière.

## Cloudflare Worker stage, 22 octobre 2026
- `threads-uninstall` et `threads-data-deletion` : Worker `mrxpronos-threads-privacy-staging` déployé, liaison D1 contrôlée. Variable `THREADS_APP_SECRET` non configurée ; URL Meta non basculée.
- `push-subscribe` : Worker `mrxpronos-push-staging` déployé, liaison D1 contrôlée. 57 abonnements copiés, 57 endpoints distincts ; empreinte stable sur la liste triée des endpoints concordante avec Supabase. Route publique du site encore sur Supabase.
- **7 fonctions métier avec code de remplacement déployé** : 4 via Neon Functions + 3 via les deux Workers Cloudflare. `clean-cache` restaurée comme routine SQL non planifiée, interdite aux rôles anonymes.
- Les 12 autres Edge Functions nécessitent encore réécriture, secrets et tests. Aucun callback Telegram ou Meta de production n'a été déplacé.
