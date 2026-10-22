# Neon staging — 22 octobre 2026

## Projet créé et vérifié
- Organisation : `MrXPRONOS` (plan **Free**)
- Projet Neon : `withered-tooth-71931108` (`MrXPRONOS-Migration`)
- Branche principale : `br-winter-truth-b9of9tss` (`main`)
- Base : `mrxpronos`; moteur PostgreSQL **17.11** ; région `aws-eu-central-1`
- Compute : **0.25 CU**, sans modification des paramètres de suspend propres au plan Free
- PostgreSQL extensions activées et revérifiées : `vector 0.8.0`, `pgcrypto 1.3`, `uuid-ossp 1.1`
- **Aucun changement côté production Supabase/GitHub Pages** ; Neon n'est pas encore relié aux applications

## Source et contraintes
- Supabase : 85 tables publiques, ~170 Mo base, 158 routines publiques (154 fonctions + autres), 10 triggers, 55 politiques RLS, 227 index.
- **Ne pas copier les schémas internes Supabase tels quels** : `auth`, `storage`, `vault`, `realtime` et fonctions qui s'y réfèrent requièrent des adaptateurs ; on a relevé au moins 6 fonctions publiques faisant référence à `auth.`.
- Bucket `cms-media` public et `videos` public : 113 objets, ~215 Mo au total.
- Neon Free : PostgreSQL 1 Go/projet, 100 CU-hours/projet/mois, 5 Go egress/mois. Objet Storage 5 Go/projet ; aucune garantie d'absence de limites par requête.
- Neon est une **base PostgreSQL**, ce n'est pas un serveur PostgREST Supabase prêt à l'emploi : remplacer les appels `supabase.from()`, `supabase.rpc()`, `supabase.functions.invoke()`, les subscriptions Realtime et l'auth de manière contrôlée via API/Workers ou Neon Data API si approprié.
- Les URL privilégiées et clés de connexion doivent rester dans les secrets, jamais dans le dépôt ou dans un fichier frontend public.

## Prochain lot technique
1. Schéma et données : export fiable de Supabase (schéma + données + dépendances + séquences), import Neon en transaction contrôlée et réconciliation par table.
2. Migration fonctions : classifier les 19 fonctions déployées, confronter aux sources réelles du dépôt ; définir remplacement Neon Functions vs Cloudflare Workers vs GitHub Actions.
3. Média : utiliser Neon Object Storage et valider la migration des 113 objets avec métadonnées/empreintes.
4. Client : préparer en staging un adaptateur API et des URL stables, puis tests E2E (LIVE, assistant, publications, VIP, notifications, Telegram, CMS).
5. Canary + rollback : garder Supabase actif pendant bascule, monitorer les quotas et la précision des données, ne changer `main` que lorsque prêt.

**Statut : destination opérationnelle, extensions installées, transfert de données non commencé.**
