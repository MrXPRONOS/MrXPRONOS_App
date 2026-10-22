# Migration Supabase -> infrastructure gratuite (staging)

Date audit : 2026-10-22. **Aucune modification en production dans cette branche.**

## État source observé
- Projet Supabase actif : nhwafcpndlufzzxexikh (eu-central-1).
- 85 tables du schéma public ; base PostgreSQL 17, environ 170 Mo.
- 158 fonctions SQL publiques, 10 triggers applicatifs, 55 politiques RLS, 227 index.
- Extensions : pgcrypto, uuid-ossp, vector (pgvector 0.8), pg_stat_statements, supabase_vault, plpgsql.
- 19 Edge Functions déployées ; source GitHub sous supabase/functions/ et certaines fonctions présentes seulement sur Supabase.
- 2 buckets publics (cms-media et videos), 113 objets, taille déclarée cumulée ~215 Mo.
- 1 utilisateur Supabase Auth ; comptes VIP et identités applicatives stockés dans plusieurs tables.
- Cloudflare connecté : Workers/D1 disponibles mais aucune ressource déployée ; R2 désactivé sur le compte (HTTP 403, activation Dashboard nécessaire).
- GitHub Pages et de nombreux GitHub Actions déjà en production.

## Architecture choisie : préserver PostgreSQL
1. **Neon Free** : conserver PostgreSQL et pgvector, migrer les tables, les données, les routines et politiques RLS compatibles. Offre annoncée au 2026-10-02 : 1 Go par projet, 100 CU-hours/mois/projet, 5 Go Object Storage et jusqu'à 1 M invocations Functions/mois. Vérifier la disponibilité/compatibilité de chaque produit après connexion.
2. **Cloudflare Workers Free** : endpoints HTTP légers, proxy/cache, webhooks et quelques événements programmés, **pas** les calculs complexes de live directement. Vérifier quotas 100k requêtes/jour et CPU 10 ms/invocation.
3. **Cloudflare D1 Free (optionnel)** : télémétrie/cache ou données de fortes lectures à découpler si Neon atteint le quota compute ; conversion PostgreSQL -> SQLite explicite, jamais en remplacement de toutes les tables SQL par défaut. Limites : 5 Go total, 500 Mo par base gratuite, 5 M lignes lues/jour, 100k lignes écrites/jour ; quotas stricts.
4. **GitHub Pages + Actions** : garder site et automatisations. Migrer les URLs/secrets seulement après tests. Ne jamais publier un jeton privilégié dans GitHub Pages.
5. **Stockage** : Neon Object Storage (si l'offre gratuite est disponible sur le projet) en préférence ; envisager R2 seulement après activation explicite, vérification du coût et du mode de paiement.

## Séquence sécurisée
- [x] Confirmer les accès Supabase, Cloudflare et GitHub ; inventaire initial en lecture seule.
- [ ] Connecter et créer un projet **Neon Free** (à faire depuis le compte utilisateur ; aucun déploiement à facturation active).
- [ ] Inventorier toutes les fonctions SQL et leurs dépendances supabase/auth/storage/vault/cron ; identifier les réécritures nécessaires.
- [ ] Exporter la base source avec sauvegarde intègre (schema, données, séquences, fonctions, triggers, contraintes, RLS), sans exposer les secrets.
- [ ] Restaurer sur Neon staging ; adapter les dépendances propres à Supabase et vérifier pgvector et la Data API.
- [ ] Migrer les objets des deux buckets et contrôler tailles + hachages + droits.
- [ ] Migrer les fonctions (LIVE, assistant, VIP, notifications, admin, Telegram, etc.) et les appels GitHub Actions sans interrompre la production.
- [ ] Adapter authentification, contrôle d'accès admin et identités VIP. Vérifier tests de non-régression et CORS.
- [ ] Tester le parcours complet sur staging : pronostics, scores, live, Telegram, notifications push, articles, VIP, dashboard, assistant et médias.
- [ ] Bascule progressive uniquement après comparaison de données, tests de charge/quotas, sauvegarde et mécanisme de retour arrière.

## Attention
- Connexion Neon non encore fournie au moment de cet audit. **Pas de migration de données démarrée.**
- Les limites commerciales peuvent changer. Le quota restant Supabase exact n'est pas directement fourni par cet inventaire ; comparer aux factures/usage avant la bascule.
- Ne supprimer ni Supabase ni les secrets de production avant validation du rollback.
