# Ciné Radar V2 — registre d'implémentation

## Architecture conservée

- Déploiement : `cinecanaux/worker.mjs` avec `wrangler.jsonc`.
- Interface Mini App : `cinecanaux/app-page.mjs`.
- Bot Telegram : `cinecanaux/radar-lean.mjs`.
- Métadonnées publiques : `cinecanaux/channel-preview.mjs`.
- Recherche, avis et suggestions : `cinecanaux/v2.mjs`.
- Contrôles de liens : `cinecanaux/maintenance-v2.mjs`.
- API de modération : `cinecanaux/admin-v2.mjs`.
- Interface privée : `cinecanaux/admin-page.mjs`.
- `cinecanaux/src/` contient une copie des modules de la V2 pour archivage/inspection ; le déploiement pointe vers la racine du répertoire `cinecanaux/`.

## Fonctionnalités

| Fonction | État du code | Vérifications |
|---|---|---|
| Annuaire sans republication de médias | Intégré | Aucune route d'upload de médias |
| Découverte sans approbation manuelle | Intégré | Nouveau lien public vérifié avant insertion |
| Dédoublonnage et liste d'exclusion | Intégré | Index uniques et requêtes de garde |
| Recherche par nom, catégories et mots-clés | Intégré | Tests unitaires + D1 de test |
| Recherche multicatégorie et groupes avec `; ` | Intégré | Tests unitaires |
| Tri par pertinence, avis, date | Intégré | Tests unitaires |
| Avis 1–5 étoiles et conformité de description | Intégré | Authentification Mini App signée + test |
| Signalements et suggestions | Intégré | API validées, contrôles anti-abus |
| Tableau de bord privé | Intégré | Accès protégé par compte Telegram et `admin_users` |
| Modération et exclusion | Intégré | Actions non destructives |
| Contrôle quotidien de 10 liens | Intégré | Cron `0 3 * * *` et test de non-suppression |
| Mise à jour des noms/descriptions | Intégré | Source : métadonnées publiques Telegram |
| Changement automatique de lien | **Partiel** | Un ancien @username ne prouve pas l'identité du nouveau canal ; changement uniquement avec preuve fiable |
| Recherche dans tous les messages Telegram | **Non implémenté** | Hors périmètre de l'annuaire de liens publics |
| Statistiques sans historique personnel | Intégré | Agrégats journaliers par catégorie |
| Interface mobile à peu de texte | Intégrée | Vérification syntaxique et tests ; recette visuelle sur téléphone nécessaire |
| Publication en production | À valider | Ne pas appliquer avant migration, tests et sauvegarde |

## Migrations D1 (ordre impératif)

1. `cinecanaux/migrations/001_v2.sql`
2. `cinecanaux/migrations/002_discovery_attempts.sql`
3. `cinecanaux/migrations/003_anonymous_search_stats.sql`

Ces migrations sont additives et préservent les 40 fiches existantes. Les déclencheurs de production ne doivent pas être modifiés avant qu'elles aient toutes été appliquées et vérifiées.

## Tests et contrôles de livraison

- `.github/workflows/cine-radar-v2-ci.yml` : suite principale de tests d'intégration.
- `.github/workflows/cine-radar-v2-check.yml` : validation supplémentaire sans déploiement.
- `cinecanaux/tests/v2.test.mjs` : recherche, multi-catégories, avis signés, administration et sécurité des contrôles de liens.
- Préproduction Cloudflare : Worker `cinecanaux-v2-staging` et D1 `cinecanaux-v2-staging`, sans identifiants Telegram réels.
- Pour revenir en arrière, revenir à la version précédente du Worker ; une restauration D1 destructive ne devrait pas être nécessaire car les migrations sont additives.

## Règles de fonctionnement

1. Le service référence des liens publics Telegram et des métadonnées publiques ; il ne copie pas les films ni les publications.
2. L'ajout d'un canal est automatique après vérification technique de son URL ; cela ne constitue **pas** une certification de son contenu.
3. Les échecs passagers de Telegram ne suppriment jamais une fiche. Deux contrôles négatifs espacés d'au moins 23 heures masquent la fiche.
4. Les canaux masqués gardent leurs avis et leur historique pour réexamen.
5. Le changement automatique d'un lien requiert une preuve de continuité d'identité, pas seulement une ressemblance de nom.
6. L'accès aux API de participation exige des données d'authentification Telegram valides. Les API administratives exigent en plus un rôle autorisé.
7. Les statistiques de recherche sont agrégées et ne stockent ni identité, ni terme saisi.
