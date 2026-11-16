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
| Publication en production | Déployée | Code présent sur le Worker public ; tests fonctionnels complets à finaliser |

## Migrations D1 (ordre impératif)

1. `cinecanaux/migrations/001_v2.sql`
2. `cinecanaux/migrations/002_discovery_attempts.sql`
3. `cinecanaux/migrations/003_anonymous_search_stats.sql`
4. `cinecanaux/migrations/004_admin_hide.sql`
5. `cinecanaux/migrations/005_monitoring_and_identity.sql`

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

## État vérifié le 16 novembre 2026

- La V2 est réellement présente dans le Worker de production `cinecanaux-bot`.
- La migration additive `004_admin_hide.sql` est appliquée sur la D1 de production.
- La PR [#392](https://github.com/MrXPRONOS/MrXPRONOS_App/pull/392) a réussi la CI, puis a été fusionnée dans `main` (commit `f6a2492be90e336d6348c0e9041aa489d8f48718`).
- Le Worker a été redéployé via Cloudflare en héritant strictement de ses trois bindings : `DB`, `TELEGRAM_TOKEN` et `TELEGRAM_WEBHOOK_SECRET`. Leur présence a été contrôlée après le déploiement.
- L'existence des trois déclencheurs a été confirmée : `0 3 * * *` (10 contrôles de liens par passage), `0 */4 * * *` (découverte), `15 */6 * * *` (entretien).
- La base de production contient **40 canaux référencés**, **0 avis** et **0 contrôle enregistré** au moment du constat. Le fonctionnement de l'exécution quotidienne doit être vérifié après le prochain déclenchement réel.
- Les vérifications de code, la migration D1 de test, les tests GitHub Actions et l'acceptation du Worker par Cloudflare ont réussi. En revanche, la recette manuelle sur téléphone, la soumission d'un véritable avis Telegram et une exécution Cron complète en production restent non vérifiées.
- L'identification automatique du **nouveau lien d'un canal déplacé** demeure partielle : il faut une preuve de continuité d'identité. Le système masque une ancienne URL invalidée plutôt que de deviner une redirection.
- La recherche dans l'intégralité des publications de Telegram n'est pas incluse : Ciné Radar reste un annuaire de liens publics et de métadonnées.

## Complétion V2 — audit du 16 novembre 2026

Les PR [#393](https://github.com/MrXPRONOS/MrXPRONOS_App/pull/393) et [#394](https://github.com/MrXPRONOS/MrXPRONOS_App/pull/394) ont été fusionnées après réussite de la CI. Le Worker `cinecanaux-bot` a été redéployé avec dix modules. Ses secrets et bindings D1 ont été préservés et contrôlés.

### Fonctionnalités supplémentaires effectivement codées
- Récupération de l'identifiant stable d'un canal public via la méthode Telegram Bot API `getChat` lorsque celle-ci est accessible.
- Réconciliation des changements d'adresse `t.me/username` seulement si le nouvel identifiant correspond au canal enregistré ; jamais d'inférence sur les simples noms.
- Conservation des anciens noms en alias lors d'un changement vérifié ; prévention des collisions de liens.
- Exécution de vérifications des liens avec une limite de dix par cycle et trois contrôles concurrents maximum.
- Table `automated_job_runs` pour conserver les résultats des Cron : succès, partiel, erreur, éléments examinés, liens actualisés.
- Tableau d'administration privé : historique des exécutions et déclenchement contrôlé de 1 à 10 vérifications.
- Requêtes du bot Telegram cohérentes avec les fiches masquées/exclues sur le site.
- Les notes en attente de modération ne participent plus à la note publique.

### Preuves et limites de validation
- Les tests automatisés de la branche #393 ont réussi, y compris les tests de l'identité stable et de sécurité, les contrôles d'interface et les smoke tests en lecture de production.
- La migration SQL 005 a réussi sur D1 de test, puis en production (sauvegarde de type bookmark D1 vérifiée avant migration).
- Le Worker de production contient le nouveau code et les trois bindings requis ; les horaires Cron restent `0 3 * * *`, `0 */4 * * *`, `15 */6 * * *`.
- Au moment de la dernière lecture, la base de production contient **40 canaux**, **0 avis**, **0 exécution enregistrée dans automated_job_runs**, **0 contrôle de lien**, **0 identifiant Telegram stable enregistré**. Le nouveau suivi ne peut prouver le fonctionnement d'un Cron tant qu'il n'a pas été déclenché.
- Les avis réels et les autorisations Telegram de l'administrateur ne peuvent être testés qu'avec un compte Telegram authentifié. Aucun faux utilisateur ni faux avis n'a été ajouté à la base publique.
- La réparation d'une ancienne URL n'est possible que si le stable ID avait été capturé et reste récupérable : ce cas est techniquement implémenté mais dépend de l'API Telegram ; les changements impossibles à prouver sont laissés en attente, sans redirection inventée.
- L'interface mobile a fait l'objet de tests de syntaxe et d'intégration, mais pas encore d'une validation visuelle manuelle sur chaque téléphone réel.
