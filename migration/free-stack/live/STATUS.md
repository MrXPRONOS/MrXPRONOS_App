# Fonction live : état vérifié (22 octobre 2026)

Ce dossier porte **uniquement** sur `live`. Les 18 autres fonctions et les vidéos ne sont pas touchées dans ce lot.

## Source à préserver
- Supabase `live` v276 : `supabase/functions/live/index.ts` (354661 caractères) + modules partagés ESPN/football/Telegram et polices pour la capture image.
- Routes historiques : GET `/matches`, `/opportunities`, `/today`, `/predictions/history`, `/predictions/by-id`, `/daily/today`; POST `/refresh`, `/refresh/batch`, `/validate`, `/telegram/process-one`, `/daily/generate`, `/daily/validate`, entre autres.
- Le moteur original utilise BSD, ESPN, contrôles de qualité corners/tirs/fautes, anti-doublon Telegram, génération et validation de signaux.

## Neon vérifié
- Fonction Neon `live` actuellement **déployée** avec source `index.bundle.mjs` compilée et `index.mjs` de référence. Version de déploiement contrôlée dans Neon; **service actuellement en lecture seule**, pas de POST effectif.
- `live_predictions` : 6230 lignes.
- `matches_live` : 80 fiches historiques importées. Aucune fiche actualisée durant les 240 dernières secondes lors du contrôle.
- 15 historiques de prédiction dans la fenêtre des 48 h vérifiés via `SET LOCAL ROLE anonymous`.
- `live_public_api(text,text)` : RPC lecture publique avec vérification de rôle; définition versionnée dans `live_public_api.sql`.
- `live_ingest_espn(text,jsonb)` : RPC d'ingestion restreint par secret, définition versionnée dans `live_ingest_espn.sql`. **Aucun secret valide configuré** ; un jeton erroné est rejeté. Cette RPC ne peut pas être considérée active.
- Le rôle anonymous ne peut pas lire `vip_users` ni `admin_users`.

## Fonctionnalités non portées
1. Refresh BSD complet, agrégation multi-source, fiabilité des statistiques et génération de signaux corners/tirs/fautes. NE PAS générer des pronostics avec de simples scores ESPN.
2. Validation des signaux et historique issu du nouveau rafraîchissement.
3. Envoi de coupons Telegram en image, statut et anti-doublon.
4. Tâche périodique valide, stockage de secrets côté Neon, tests HTTP réels et test de non-régression de l'application LIVE.
5. Remplacement des appels à l'ancienne Edge Function dans le frontend et les six workflows.

## Bloquants objectifs
- L'environnement Supabase utilise Deno et `supabase-js`, Neon Functions utilise Node.js 24/PostgreSQL; le simple recopiage des sources ne fonctionne pas.
- Les identifiants BSD et Telegram ne sont pas disponibles en clair via les intégrations actuelles.
- Les tentatives d'initialiser un secret et de publier une nouvelle fonction d'ingestion ont été bloquées par les contrôles de connexion; aucun secret n'a été exposé.
- Il est indispensable de valider le fonctionnement des nouvelles sources et le cron avant toute bascule en production.

**Statut réel : LIVE lecture préparée et déployée, migration complète non terminée. Aucun basculement public.**
