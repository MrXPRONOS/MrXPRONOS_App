# Manifeste de progression — Actu Foot Mr XPRONOS (23 novembre 2026)

Ce manifeste décrit le périmètre **Actu Foot / Telegram**, distinct du moteur de pronostics Hybride V3 et de ses versions. Il ne constitue pas à lui seul une preuve de publication Telegram.

## Règle éditoriale commune

- Pour un but **confirmé**, commencer par **⚽ BUUUT ! Le score est désormais de X–Y.** afin que la notification soit identifiable dans l’aperçu Telegram.
- Ensuite, citer dans un **blockquote HTML** les équipes et le score (avec minute vérifiée), le championnat connu et le buteur **si ESPN donne explicitement son nom**. Ne jamais inventer un buteur, une minute ni un score.
- Pour une correction de score sans événement de but confirmé, utiliser « NOUVEAU SCORE CONFIRMÉ », **jamais BUUUT**.
- Pour un article RSS : **véritable titre du journaliste en haut**, contenu cité en blockquote ; en bas, rubrique éditoriale **en gras**, puis source **en italique**.
- Format sans URL publique, avec échappement HTML. Pas de doublons Telegram créés volontairement : conserver les preuves D1, les clés d'idempotence et les quarantaines en cas d'envoi incertain.

## Historique et état vérifiable

| Étape | Périmètre | État |
| --- | --- | --- |
| V1 | Collecte RSS, diffusion principale et routage vers 10 canaux, filtrage, quotas et réservations D1 | **Implémentée**, déjà observée en production ; couverture réelle de chaque canal à mesurer |
| V1.1 | Scores LIVE ESPN, événements vérifiés, édition du tableau des scores, déduplication D1 | **Implémentée**, quelques envois observés ; valider en production buts, cartons, temps additionnel et routage par rôle |
| Correctif de présentation V1/V1.1 | BUUUT en premier, détails sourcés, footer RSS cohérent | **Fusionné**, PR #630, commit `c93128a4` ; rendu Telegram réel toujours à observer |
| V1.2 | Débriefs enrichis et classements avancés selon `docs/ACTU_FOOT_V1_MULTICANAL.md` | **À spécifier / valider**, ne pas déclarer achevée |
| V1.3 | Tableau de supervision et alertes par canal selon ce même document | **À spécifier / valider**, ne pas déclarer achevée |
| V2 | Coffre chiffré, validation, audit, sauvegarde et restauration encadrée | **Code + tests déjà présents** ; clés, protection d'environnement, données, restauration réelle et audit externe à valider avant activation |
| V3 | Index/requêtes, cache, archives chiffrées, mutations atomiques Git | **Code + tests déjà présents** ; ordonnanceur, validation des volumes et déploiement opérationnel non achevés |
| V4 | Réconciliation de l'historique, réservation/ack Telegram, bascule progressive depuis les anciens stockages | **Prévue**, non terminée |

**V2.1 n'est pas une étape explicitement définie dans les documents de référence inspectés.** Ne pas en inventer une.

## Conditions pour déclarer V1/V1.1 closes

1. **Acquis :** tests ciblés et fusion de la PR #630 sur `main`.
2. Contrôler le rendu réel d'au moins un article RSS sur le canal principal et un canal spécialisé (ou un test canal réel pour éviter de publier un faux événement).
3. Vérifier un but réel : accroche BUUUT en premier, score exact, équipe, minute, compétition et buteur lorsqu'il est connu.
4. Vérifier une correction de score réelle : aucune fausse annonce de but.
5. Vérifier plusieurs cycles en production : l'absence de doublons, les erreurs D1 / Telegram, les droits sur les 10 canaux et les compteurs par rôle.
6. Documenter clairement les cas impossibles à observer faute d'événements authentiques (p. ex. tirs au but ou carton rouge). Ne jamais envoyer de fausse actualité en production pour valider l'UI.

## Contrôle de production après PR #630 (23/11/2026)

- L'exécution V1.1 `45093084383` a réussi. Contrôle Telegram : **10 rôles sur 10 acceptés**, aucun rôle refusé.
- Cette exécution affiche `mode=production`, `errors=0`, `mismatched=0`, `sent=0` sur 5 matchs sélectionnés : **cela ne valide pas un but réellement publié**.
- Le passage du canal principal `45092982476` a réussi avec `ACTUFOOT_LIVE_MONITORED 0` : aucun événement de suivi à vérifier durant ce passage.
- PR #631 : ajout du repli **public anonyme et optionnel** pour les actualités du site quand `footnews.json` est vide ; ajout d'un rapport de santé **informatif et non bloquant** ; correction des dépendances de la CI de validation Actu Foot.
- Tests PR #631 : **345 tests de CI générale** et **345 tests hors ligne Neon/Actu Foot** réussis ; navigation Infos et contrôle de confidentialité réussis.
- **Bloquant externe distinct :** le job de lecture réelle Neon `45093266168` ne peut pas vérifier la base, car le secret GitHub Actions `NEON_DATABASE_URL` est absent. Ne pas marquer la connexion Neon comme validée ni publier une valeur de connexion dans les logs.
- Pour fermer V1.1 : un événement ESPN réel avec un buteur identifié, un score corrigé réel et les exemples Telegram rendus dans leurs canaux respectifs doivent être constatés ; la seule réussite des tests ne les remplace pas.

## Prochain lot V1.2 (périmètre minimal)

1. Sur le canal `debrief` : synthèse après-match issue de faits vérifiés (score final, compétition, acteurs confirmés, cartons et statistiques présentes), sans analyse inventée.
2. Sur le canal `scores` : classement et évolution sourcés, avec horodatage, fraîcheur et impossibilité de publier un classement inexistant.
3. Maintenir les réservations D1, les quotas, les contrôles de rôles et la compatibilité V1/V1.1 ; tests hors ligne et recette Telegram.
4. Les alertes/supervision des 10 canaux constituent la **V1.3**, distincte de cette V1.2.

## Sources internes consultées

- `docs/ACTU_FOOT_V1_MULTICANAL.md` : V1 et prévisions V1.1, V1.2 et V1.3.
- `docs/actu-foot-v2-foundations.md` et `docs/actu-foot-v2-cloudflare-backups.md` : V2 et prérequis opérationnels.
- `docs/actu-foot-v3-data-engine.md` et `docs/actu-foot-v3-completion.md` : V3 et limites ; V4 en backlog.
