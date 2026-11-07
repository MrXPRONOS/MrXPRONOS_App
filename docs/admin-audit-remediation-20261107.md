# Mr XPRONOS — suivi des améliorations de l'administration

Audit du 7 novembre 2026. Cette feuille de route distingue **implémentation dans la PR** et **mise en production**. Une modification de code n'est pas considérée comme déployée tant que son environnement d'hébergement n'a pas été confirmé.

Légende : **C** = correction implémentée sur la branche avec contrôle automatique ; **P** = correction partielle ; **À faire** = non implémentée ; **Bloqué** = condition préalable nécessaire.

## Points critiques transversaux

| Réf. | Amélioration | Statut | Justification ou suite |
|---|---|---|---|
| A0 | Hébergement protégé de la console principale | À faire | Les fichiers admin sont volontairement absents de gh-pages. Un hôte avec contrôle d'accès en amont doit être choisi et testé. Ne pas publier la console sans garde d'accès. |
| A1 | Réconcilier le CMS et le flux d'articles automatiques | P | Les articles `bsd-match-*` sont conservés par la publication et les suppressions sont confirmées. Les cinq tables CMS ne sont pas encore importées/synchronisées. |
| S1 | MFA obligatoire avant toute opération sensible | Bloqué | La base indique 1 admin actif et aucun facteur MFA vérifié. Imposer AAL2 maintenant verrouillerait la publication. |
| S2 | Rôles administrateur séparés | À faire | Les droits sont encore principalement fondés sur `is_admin()`. Migration des rôles et politiques requise. |
| S3 | Protection Supabase contre les mots de passe compromis | À faire | Réglage du fournisseur Auth à activer dans le tableau de bord Supabase. |
| S4 | Revue exhaustive des fonctions SECURITY DEFINER | P | Fonctions administratives principales examinées ; contrôle individuel des autres fonctions et de leurs arguments restant. |
| S5 | Déduplication des politiques RLS identiques | À faire | Ne retirer les politiques qu'après une migration et des tests RLS sur comptes non administrateurs. |

## 27 améliorations fonctionnelles

| N° | Amélioration | Statut | Vérification / limite |
|---:|---|---|---|
| 1 | Supprimer `Simple` des pronostics admin | C | Les filtres admin ne proposent que Pro/VIP. |
| 2 | Enrichir la liste pronostics (logos, marchés, score, état, date) | C | Tableau de consultation adapté ; données non présentes affichées par tiret. |
| 3 | Ajouter des diagnostics sans réécrire les résultats | P | Rafraîchissement et diagnostic de chargement ; pas de nouvelle validation de moteur. |
| 4 | Distinguer échec du flux et absence de matchs | C | États explicites dans la vue Pronostics. |
| 5 | Clarifier la portée de l'ancien registre VIP | C | Message visible : codes d'accès distincts des catégories Pro/VIP. |
| 6 | Sécuriser les confirmations VIP | C | Vérification durée, confirmation utilisateur, désactivation du bouton pendant l'action. |
| 7 | Supprimer la limite silencieuse de 50 contenus CMS | P | Lecture par pages Supabase de 200, plafonnée à 2 000 ; recherche serveur globale ultérieure. |
| 8 | Localiser les statuts CMS | C | Brouillon, Publié, Actif, Désactivé dans les formulaires. |
| 9 | Conserver la date initiale de publication | C | Fonction commune de préservation appliquée aux cinq formulaires CMS. |
| 10 | Séparer formulaires et listes | C | Éditeurs rétractables pour Articles, Conseils et Infos. |
| 11 | Prévisualisation fidèle du site public | P | Aperçu de blocs déjà présent ; rendu public mobile/desktop à créer. |
| 12 | Contrôles qualité avant publication | P | Prévisualisation de différences et confirmation des suppressions renforcées ; validation SEO/liens plus complète à ajouter. |
| 13 | Brouillons synchronisés côté serveur | À faire | L'éditeur conserve pour l'instant un brouillon dans localStorage. |
| 14 | Bucket privé pour les médias non publiés | À faire | Les médias sont stockés dans un bucket public, modèle privé/public restant à concevoir. |
| 15 | Sélection explicite des destinataires Push | C | Aucune audience présélectionnée. |
| 16 | Prévisualisation et envoi Push de test | P | Prévisualisation ajoutée, compte de test dédié encore absent. |
| 17 | Planification des notifications Push | À faire | Requiert un orchestrateur serveur, une file durable et le suivi des horaires. |
| 18 | Bilan clair d'envoi Push | P | États envoyés/échecs/ignorés visibles ; reprise et enquête par appareil à ajouter. |
| 19 | Pagination des abonnements Push au-delà de 5 000 | À faire | L'Edge Function de liste conserve un plafond de 5 000 lignes. |
| 20 | Protection contre les doubles envois Push | P | Verrouillage de l'interface pendant l'envoi ; clé d'idempotence serveur à ajouter. |
| 21 | Réduire la double supervision imbriquée | C | Vue d'ensemble native ; ancienne iframe chargée uniquement sur demande. |
| 22 | Tableau de bord unifié | P | KPI de pilotage intégrés ; détails Telegram/Audience encore sur leurs pages spécialisées. |
| 23 | Registre central des workflows | P | Rubrique distingue clairement cron_runs de GitHub ; consolidation cron-job.org à faire. |
| 24 | Détection plus fiable des workflows doublés | P | Heuristique affinée par workflow, événement et SHA ; preuves d'exécution indépendantes à corréler. |
| 25 | Centre d'incidents avec actions proposées | P | Échecs et retards affichés ; acquittement, escalade et historique d'incident à concevoir. |
| 26 | Rechercher, paginer et exporter le journal d'audit | C | Pagination par 100, filtres locaux, détails et CSV des données chargées. |
| 27 | Distinguer temps réel et actualisation périodique | P | Libellé Présence connectée, indicateurs rafraîchis à la demande ; autres pages à harmoniser. |

## Contrôles

- Tests unitaires Node : comparaison et sûreté des publications, prévention des suppressions involontaires et conservation des analyses automatiques.
- Tests de structure : navigation, formulaires, sécurité de l'édition et journal d'audit.
- Test navigateur Playwright : desktop et mobile, authentification fictive non privilégiée, ouverture de la supervision, audience Push et édition.
- Aucun test ne réalise une écriture sur les données CMS de production.
- Les points **À faire** et **Bloqué** ne sont pas assimilés à des réalisations. La disponibilité publique de l'administration exige encore un déploiement protégé.
