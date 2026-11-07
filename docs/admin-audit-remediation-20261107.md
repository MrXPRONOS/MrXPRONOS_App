# Mr XPRONOS — suivi des améliorations de l'administration

Audit du 7 novembre 2026. Cette feuille de route distingue **correction dans le code**, **déploiement des services** et **accès protégé à la console**. La PR #332 a été fusionnée (04f8e1abc), et les déploiements GitHub Pages / Supabase ont réussi le 7 novembre 2026. La console privée n'est toutefois pas hébergée dans un environnement sécurisé accessible aux administrateurs.

Légende : **C** = correction implémentée sur la branche avec contrôle automatique ; **P** = correction partielle ; **À faire** = non implémentée ; **Bloqué** = condition préalable nécessaire.

## Points critiques transversaux

| Réf. | Amélioration | Statut | Justification ou suite |
|---|---|---|---|
| A0 | Hébergement protégé de la console principale | À faire | Les fichiers admin sont volontairement absents de gh-pages. Un hôte avec contrôle d'accès en amont doit être choisi et testé. Ne pas publier la console sans garde d'accès. |
| A1 | Réconcilier le CMS et le flux d'articles automatiques | P | Les articles `bsd-match-*` sont conservés par la publication et les suppressions sont confirmées. Les cinq tables CMS ne sont pas encore importées/synchronisées. |
| S1 | MFA obligatoire avant toute opération sensible | Bloqué | La base indique 1 admin actif et aucun facteur MFA vérifié. Imposer AAL2 maintenant verrouillerait la publication. |
| S2 | Rôles administrateur séparés | C | Rôles propriétaire/éditeur/communication/lecture et RLS serveur ; dernier propriétaire protégé contre suppression. |
| S3 | Protection Supabase contre les mots de passe compromis | À faire | Réglage du fournisseur Auth à activer dans le tableau de bord Supabase. |
| S4 | Revue exhaustive des fonctions SECURITY DEFINER | P | Fonctions VIP renforcées ; conseiller Supabase signale encore plusieurs SECURITY DEFINER accessibles, dont des fonctions publiques intentionnelles. |
| S5 | Déduplication des politiques RLS identiques | C | Politiques ciblées sur les tables admin et CMS touchées ; autres tables hors de ce périmètre. |

## Lot 3 — finalisation des 8 points partiels

PR #335 : corrections développées et vérifiées par CI ; ces statuts **C** mesurent
l'implémentation logicielle, pas l'envoi réel d'une notification ni une activation externe implicite.

**Bilan dans le code : 26/27 corrections complètes, une intégration partielle (clé API cron-job.org).**

- Cron : données en lecture seule, cache côté serveur, domaines uniquement et empreintes HMAC des URL complètes.
- Croisements GitHub/cron : les déclenchements proches restent qualifiés de possibles, sans arrêt automatique.
- Push : bilan par appareil anonymisé et réessai unique contrôlé, jamais de rediffusion générale automatique.
- Incidents : détection/rétablissement automatiques et escalades par GitHub Actions signé.
- CMS : contrôle d'URL externe et rendu de lecture fondé sur le même moteur Markdown que le site.
- **Toujours externes :** aucune zone Cloudflare pour héberger l'administration derrière Access, aucune inscription MFA vérifiée,
  protection Supabase Auth des mots de passe compromis à activer et clé cron-job.org à connecter.
- Les tests ne publient aucun contenu client et n'envoient aucune vraie notification.

## Lot 2 — 7 novembre 2026

Ces statuts décrivent le **code implémenté et testé dans la PR #332**, pas une validation automatique de son fonctionnement en production. Les nouveaux modules nécessitent la migration et le déploiement Supabase ainsi que des vérifications après mise en ligne. Les tests n'envoient aucune véritable notification Push et ne modifient aucun contenu client.

## 27 améliorations fonctionnelles

| N° | Amélioration | Statut | Vérification / limite |
|---:|---|---|---|
| 1 | Supprimer `Simple` des pronostics admin | C | Les filtres admin ne proposent que Pro/VIP. |
| 2 | Enrichir la liste pronostics (logos, marchés, score, état, date) | C | Tableau de consultation adapté ; données non présentes affichées par tiret. |
| 3 | Ajouter des diagnostics sans réécrire les résultats | C | Diagnostics de fraîcheur, catégories et erreurs du flux ajoutés. |
| 4 | Distinguer échec du flux et absence de matchs | C | États explicites dans la vue Pronostics. |
| 5 | Clarifier la portée de l'ancien registre VIP | C | Message visible : codes d'accès distincts des catégories Pro/VIP. |
| 6 | Sécuriser les confirmations VIP | C | Vérification durée, confirmation utilisateur, désactivation du bouton pendant l'action. |
| 7 | Supprimer la limite silencieuse de 50 contenus CMS | C | Recherche serveur paginée sur les cinq modules CMS ; le plafond des 2 000 contenus ne bloque plus l'accès aux archives. |
| 8 | Localiser les statuts CMS | C | Brouillon, Publié, Actif, Désactivé dans les formulaires. |
| 9 | Conserver la date initiale de publication | C | Fonction commune de préservation appliquée aux cinq formulaires CMS. |
| 10 | Séparer formulaires et listes | C | Éditeurs rétractables pour Articles, Conseils et Infos. |
| 11 | Prévisualisation fidèle du site public | C | Même moteur Marked, sanitizer HTML et classes CSS que la page publique, aperçu isolé mobile/ordinateur ; tests navigateur du DOM. |
| 12 | Contrôles qualité avant publication | C | SEO, slugs, liens, médias privés et vérification réseau authentifiée ; réponses 404/410 bloquantes, autres anomalies signalées. |
| 13 | Brouillons synchronisés côté serveur | C | Brouillons privés synchronisés avec Supabase, sauvegarde locale de secours et révisions anti-écrasement. |
| 14 | Bucket privé pour les médias non publiés | C | Nouveaux médias dans cms-drafts privé ; publication explicite vers cms-media. Anciens médias publics conservés. |
| 15 | Sélection explicite des destinataires Push | C | Aucune audience présélectionnée. |
| 16 | Prévisualisation et envoi Push de test | C | Prévisualisation et envoi de test ciblé vers un abonné choisi. |
| 17 | Planification des notifications Push | C | Campagnes programmées, annulation et déclenchement GitHub OIDC toutes les cinq minutes. |
| 18 | Bilan clair d'envoi Push | C | Journaux anonymisés par appareil, statut HTTP et réessai ciblé explicite unique, limité aux refus 429/502/503/504 confirmés. |
| 19 | Pagination des abonnements Push au-delà de 5 000 | C | Liste paginée par 750, moteur Web Push par 1 000 ; plafond de sécurité de 50 000 appareils clairement signalé. |
| 20 | Protection contre les doubles envois Push | C | Clé UUID d'idempotence, verrou atomique et même clé sur clics répétés, sans renvoi automatique sur échec incertain. |
| 21 | Réduire la double supervision imbriquée | C | Vue d'ensemble native ; ancienne iframe chargée uniquement sur demande. |
| 22 | Tableau de bord unifié | C | Audience, installations, erreurs, incidents et campagnes Push désormais réunis dans la vue principale. |
| 23 | Registre central des workflows | P | Registre cron-job.org prêt et intégré à Supabase/GitHub ; nécessite la clé CRON_JOB_ORG_API_KEY dans Supabase Edge. |
| 24 | Détection plus fiable des workflows doublés | C | Détection des doublons GitHub, tâches cron identiques par HMAC et corrélation probable cron-job.org/GitHub ; aucune désactivation automatique. |
| 25 | Centre d'incidents avec actions proposées | C | Watchdog GitHub OIDC chaque 15 minutes, détection/récupération, suivi des incidents, gravité et escalade via GitHub Actions. |
| 26 | Rechercher, paginer et exporter le journal d'audit | C | Pagination par 100, filtres locaux, détails et CSV des données chargées. |
| 27 | Distinguer temps réel et actualisation périodique | C | Libellés normalisés sur accueil admin, supervision, audience et installation : source, instantané UTC et actualisation. |

## Vérification antérieure du lot 2 — 7 novembre 2026

- **19/27 corrections fonctionnelles complètes dans le code, 8/27 encore partielles** (voir tableau).
- PR #332 : 11 workflows de tests réussis sur 11, dont compilation Deno et contrôles navigateur.
- GitHub Actions : **Deploy Supabase Functions** #42363363291 : réussite.
- GitHub Actions : **Deploy to GitHub Pages** #42363363300 : réussite.
- Supabase : 3 tables d'administration, la fonction de rôles, la recherche CMS serveur, le bucket privé et le déclencheur anti-suppression du dernier propriétaire sont présents.
- Edge Functions actives : admin-push v19, admin-list-subscribers v15, push-notifications v30, admin-media-publish v1, publish v29.
- Vérification des privilèges : les rôles anonymes ne peuvent exécuter ni admin_can ni admin_cms_search.
- La file de notifications était vide lors de la recette : **aucun envoi de campagne Push de test** n'a été réalisé ; l'envoi réel, le déclenchement GitHub OIDC et le traitement des erreurs restent à tester en conditions contrôlées.
- Un compte propriétaire reste actif. Aucun facteur MFA vérifié : **ne pas imposer AAL2** avant son enrôlement.
- Audit de sécurité Supabase : la protection contre les mots de passe compromis n'est toujours pas activée. <https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection>
- Les statuts C ne prouvent pas que la console principale est ouverte : **l'hébergement protégé et sa validation restent bloquants**.

## Contrôles

- Tests unitaires Node : comparaison et sûreté des publications, prévention des suppressions involontaires et conservation des analyses automatiques.
- Tests de structure : navigation, formulaires, sécurité de l'édition et journal d'audit.
- Test navigateur Playwright : desktop et mobile, authentification fictive non privilégiée, ouverture de la supervision, audience Push et édition.
- Aucun test ne réalise une écriture sur les données CMS de production.
- Les points **À faire** et **Bloqué** ne sont pas assimilés à des réalisations. La disponibilité publique de l'administration exige encore un déploiement protégé.
