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
