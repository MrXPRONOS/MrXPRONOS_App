# Actu Foot — audit des versions V1 à V4
*État examiné le 23 novembre 2026 — dépôt MrXPRONOS/MrXPRONOS_App.*

Ce document distingue **code présent**, **tests réussis**, **activation en production** et **preuve de publication réelle**. Un workflow vert ne signifie pas qu'un message a été envoyé.

## Synthèse par version

| Version | Développement déjà présent | Reste à terminer / prouver |
| --- | --- | --- |
| V1 | RSS réel, publication principale et 10 canaux, édition source, quotas et reçus D1 | Valider les rendus visuellement et vérifier les publications de chaque rôle |
| V1.1 | ESPN live, buts confirmés, corrections de score distinctes, cartons/remplacements, TAB, tableau éditable, idempotence | Recevoir un vrai but et une correction réelle avec preuve visuelle Telegram |
| V1.2 | Débriefs après-match, stats source-confirmées, classements de 5 ligues, tendances sourcées, nouveau workflow dans PR #634 | Vérifier les classements ESPN réels, tests, fusion, publication dans Débrief et Scores |
| V1.3 | Observabilité générique existante | Tableau par canal Telegram, alertes quotas/publications/erreurs, essais réels |
| V2 | Coffre chiffré, validation, journal audit, sauvegarde Cloudflare KV, tests | Secrets et environnement protégés, restauration de vraie sauvegarde non vide, audit externe durable |
| V3 | Index, recherche, cache, mutations Git atomiques, archives chiffrées, tests simulés | Ordonnanceur, volumes réels, droits Git distants, politique de rétention, reprise |
| V4 | Feuille de route identifiée dans les documents internes | Réconcilier tous les historiques et IDs, outbox durable, tests canal Telegram, bascule progressive |

Aucune V2.1 officielle n'a été trouvée. La V3 de ce système n'est pas la V3 du moteur de pronostics Hybride.

## Preuves et limites

- PR #630 : format BUUUT en première ligne, tests RSS/V1/V1.1/D1 réussis ; vrai but Telegram non observé lors de cet audit.
- Workflow RSS 45092883242 : 60 actualités valides, 2 messages principaux, 4 routages spécialisés (2 Ligue 1 et 2 Scores), aucune erreur.
- Workflow V1.1 45093084383 : 10 rôles Telegram acceptés, aucune erreur, mais zéro nouveau message ; ce n'est pas une preuve de but réel.
- PR #631 : rapport de santé non bloquant, repli de lecture Neon public, suite générale de 345 tests réussis. Le secret GitHub NEON_DATABASE_URL manque pour tester l'accès à la base réelle.
- Docs actus V2 : V2 n'est pas encore le stockage de production et la restauration à distance vérifiée manque.
- Docs actus V3 : la maintenance n'est pas activée et le bot n'a pas basculé. V4 est explicitement prévu pour le basculement.

## V1.2 — spécification réellement codée

- Débriefs : état final ESPN, équipes/ID conformes, observation V1.1 déjà existante, score et événements vérifiés. Débuter par le score final, puis buts, cartons, possession, tirs, corners, fautes et TAB uniquement si disponibles.
- Classements : API ESPN des cinq ligues, saison vérifiée, équipes/rangs/points/matchs joués obligatoires, pas de fusion de groupes, pas d'invention de valeur nulle. Évolution indiquée seulement quand le précédent relevé D1 possède un rang vérifié.
- Protection : canal Débrief ou Scores vérifié, limites, réservation atomique D1, contrôle interjournées contre les doublons, aucun lien commercial ni secret dans le rendu.
- Exécution : workflow actufoot-v12 toutes les 30 minutes, classement vers 22 h Lomé, simulation par défaut en manuel, PR/push toujours en simulation.
- Clôture : valider schéma ESPN réel, tests hors ligne, envois vérifiés dans les deux canaux, idempotence, absence de score/buteur/statistique inventés.

## Ordre de poursuite

1. Terminer et activer V1.2 après confirmation des tests et du schéma ESPN.
2. Développer V1.3 : supervision et alertes de chacun des dix canaux.
3. Activer V2/V3 seulement après approbation et tests de sauvegarde/restauration.
4. Construire V4 : migration de l'historique et bascule progressive sous plan de retour arrière.

Ne jamais inventer un secret, lancer une restauration de production non testée, ni présenter une simulation comme preuve de publication.
