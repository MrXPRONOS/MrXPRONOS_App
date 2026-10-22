# Progression migration — 2026-10-22

## Destination Neon
- Projet `withered-tooth-71931108`, base `mrxpronos`, PostgreSQL 17 à Francfort, organisation Free
- 85 tables du schéma `public` recréées (colonnes, types et nullabilité, colonnes identity).
- Les contraintes PRIMARY KEY, UNIQUE, FOREIGN KEY, CHECK, les DEFAULT séquentiels, les séquences, index, vues, fonctions SQL, triggers et politiques RLS ne sont **pas encore** restaurés. En aucun cas exposer cette base directement à des utilisateurs.
- Extensions vector, pgcrypto, uuid-ossp activées.

## Premiers transferts de données confirmés
| table | lignes destination |
|---|---:|
| faq | 40 |
| bookmakers | 6 |
| espn_match_map | 4 |
| league_profiles_scrape | 1 |
| live_refresh_control | 1 |
| pronostics_cache | 1 |
| **Total** | **53** |

Ces données sont une copie de test ponctuelle. Les changements intervenant ensuite sur Supabase ne sont pas automatiquement synchronisés. Les tables à fort volume et les données sensibles n'ont pas encore été copiées.

## Risques et prochains travaux
1. Compléter l'export de la base par un véritable `pg_dump` dans un environnement sécurisé, idéalement via GitHub Actions avec secrets, **sans imprimer les identifiants ni publier le dump**. Vérifier les capacités du connecteur et du pooler avant de commencer.
2. Restaurer contraintes/index/fonctions/RLS sécurisées après le chargement initial ; adapter références à `auth.*`, Supabase Vault, stockage et secrets.
3. Refaire une synchronisation différentielle (tables actives) avant bascule ; vérifier nombre de lignes, sommes de contrôle, séquences et conflits.
4. Migrer les 19 fonctions applicatives, média/stockage et accès serveur.
5. Valider chaque parcours et basculer progressivement, rollback testé.


## Mise à jour : restauration supplémentaire contrôlée (22/10/2026)
- Activé RLS sur les **85 tables** destinataires, sans ajouter de politiques publiques permissives.
- Restauré **290** valeurs par défaut ordinaires et **22** valeurs par défaut liées à des séquences. **1** valeur par défaut dépendante de `auth.uid()` volontairement différée.
- Créé les **30 séquences**, sans encore synchroniser les valeurs `setval` avec la production ; à réconcilier après la copie complète des données.
- Restauré **85 clés primaires**, **18 contraintes UNIQUE**, **44 contraintes CHECK** sur Neon.
- Vérification Neon : **103 index** induits par les 85 PK + 18 UNIQUE. Les **124 index autonomes** restent à traiter après les données (et les dépendances de fonctions).
- Les **13 clés étrangères** restent différées, pour ne pas bloquer l'importation des tables liées.
- Aucune politique RLS n'a été copiée : les **55 politiques d'origine** exigent une revue `auth.*`/rôles et de la Data API. **Ne pas mettre les clients en relation directe avec cette base à ce stade**.
- Données copiées et confirmées à date : les 53 lignes des 6 tables mentionnées ci-dessus. Les données changent encore sur Supabase.
- Aucun changement dans `main`, aucun changement sur la production.


## Mise à jour (suite) — 22/10/2026
- Relecture comparative des définitions des 124 index autonomes de Supabase.
- **124/124** index autonomes restaurés sur Neon et noms vérifiés ; total **227/227** index.
- Données supplémentaires copiées vers Neon et présence comptabilisée : `actu_foot_provider_health` (4), `counters` (1), `actu_foot_news_snapshot` (1), `telegram_channel_official_stats` (10), `live_provider_probe_cache` (14), `matches_live_cache` (7). Total nouveau **37** enregistrements ; **90** enregistrements copiés sur 12 tables au total.
- Aucun déploiement en production ni changement des secrets / endpoints.
- **Toujours manquants** : la majorité des enregistrements et les données sensibles, 13 clés étrangères, 10 triggers, routines SQL applicatives, 55 politiques RLS, adaptation de l'authentification et des appels client, 19 Edge Functions, objets Storage.
- Les 90 enregistrements copiés ne constituent **pas une sauvegarde complète**, ni une synchronisation temps réel. Relancer un export/restauration cohérent et vérifier les séquences après le transfert intégral, avant toute bascule.


## Suite : nouveaux lots et contrôle d'intégrité (22/10/2026)
- Copie effectuée de `matches_scheduled` : 93 lignes source / 93 cible ; empreinte globale `md5(jsonb_agg(...))` égale.
- Copie effectuée de `telegram_channel_metrics_daily` : 67 lignes source / 67 cible ; empreinte complète différente. Une seconde comparaison en supprimant temporairement du calcul les champs horodatés `last_post_at`, `collected_at` et `official_stats_checked_at` produit des empreintes égales. Les valeurs temporelles exactes doivent être comparées au niveau microseconde avant validation intégrale ; aucune modification corrective à l'aveugle.
- Volume total de données présentes et comptées dans les tables déjà vérifiées : **250 lignes sur 14 tables** (90 précédemment + 160 transférées dans ces deux tables).
- La tentative d'import de `live_predictions_scrape` a été bloquée par les contrôles de l'environnement d'exécution ; ne pas prétendre que cette table a été transférée.
- Production et branche `main` de GitHub inchangées.
- Prochaine opération prioritaire : un export PostgreSQL client-serveur sécurisé (pg_dump/pg_restore) avec secrets, puis checksum stable par clés métiers et réglage de séquences.
