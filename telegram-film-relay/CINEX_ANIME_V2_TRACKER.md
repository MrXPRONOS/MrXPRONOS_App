# CinéX Anime V2 — suivi des 22 chantiers et intégration sécurisée

Préparation ouverte le **21 novembre 2026** sur une branche isolée :
`release/cinex-anime-v2-integration-20261121`.
PR de préparation : https://github.com/MrXPRONOS/MrXPRONOS_App/pull/585

> **Aucun déploiement ni fusion.** Les modules Bot API sont verrouillés par défaut.
> Un test hors ligne réussi ne démontre pas les permissions Telegram ni les
> droits de reproduction des sources, et n'autorise pas la publication.
> La migration finale n'a pas été testée avec les canaux réels.

## Règles demandées

- 4 cycles de publication par jour : **00:17 / 06:17 / 12:17 / 18:17 UTC**
  (horaire existant de l'ancien relais).
- Nouveautés : **au plus 4 épisodes de 4 animés différents** par cycle,
  pas 4 vidéos du même animé. Pas de numéro inventé, ni saut automatique
  au-dessus d'un épisode non réconcilié.
- Saison complète : conserver la priorité au lot complet, **25 épisodes
  au maximum par lot**, puis reprise contrôlée du lot suivant.
- En cas de collision, état incertain ou chaîne de publication partielle :
  **bloquer la répétition**, préserver les anciens reçus.
- Utiliser à terme les **bots uniquement**, avec collecte Bot API seulement
  depuis des canaux qui ont explicitement autorisé l'accès du bot.
- Conserver les anciennes fiches et les liens existants, aucun nettoyage
  historique destructif sans revue séparée.

## État exact des chantiers

| # | Correction / amélioration | Code sur PR #585 | Ce qui manque pour la clôture définitive |
|---|---|---|---|
| 1 | Crash `verify_library_bot` | Corrigé ; tests hors ligne | Validation pendant un cycle Telegram réel |
| 2 | Antidoublons multi-sources série+saison+épisode | Implémenté, avec quarantaine | Contrôle de la vraie base des publications |
| 3 | Même média sous plusieurs noms / autres encodages | `document.id` + `file_unique_id`, variantes signalées | Pas de signature SHA256 binaire universelle pour médias réencodés |
| 4 | Empêcher nouveaux doublons de fiches/vidéos | Marqueur stable, reçus intermédiaires, récupération ancienne paire | Audit et nettoyage des doublons historiques existants |
| 5 | Reprendre après crash/réseau incertain | Journal d'opérations sans réessai aveugle, copie vérifiée | Réconciliation MANUELLE des envois indéterminés |
| 6 | Réunifier les séries/fiches historiques | Consolidation existante + import offline sécurisé vers Bot V2 | Valider les clés et collisions sur les canaux réels |
| 7 | Alias / noms alternatifs des animés | Registre d'alias approuvés, contrôle des collisions | Définir/valider les alias des cas réellement ambigus |
| 8 | Publier nouvel épisode d'un animé déjà connu | Sélecteur incrémental avec reçus par épisode | Test réel sur une publication autorisée |
| 9 | Association affiche→texte→vidéo isolée | Parseur par canal, saison explicite, quarantaine | Messages réellement ambigus nécessitant une intervention |
| 10 | GIF hebdomadaire et périodicité | Extraction cadence + réemploi optionnel du GIF source | GIF original de marque non créé ; droits et activation à vérifier |
| 11 | 4 épisodes de 4 séries distinctes | Sélecteur et tests unitaires | Vérifier la répartition après plusieurs vrais cycles |
| 12 | Saison complète par lots successifs | Sélecteur priorité complète + 25 par lot | Test source réelle >25 épisodes |
| 13 | File d'attente durable | Inbox Bot API privée + fichier atomique + verrou | Support persistant réel externe/privé et sauvegarde à provisionner |
| 14 | Archives et curseurs bloqués | Nouvelle archive queue opt-in + reprise exact-ID | Activer et valider l'avancement sur ancien historique |
| 15 | Saisons partielles, trous, OVA, hors-série | Trous bloqués, OVA/ONA/spéciaux quarantainés | Classification/publication distincte des contenus spéciaux |
| 16 | Fiches, index, boutons et mise à jour saison | Cartes réutilisées, index privé paginé 25, nouvelle annonce de saison | Revoir l'interface et la propriété des anciennes cartes |
| 17 | 100 % Bot API | Poller, média privé/public, index, migration et garde-fous codés | Bot dédié + permissions + arrêt ancien relais + validation réelle |
| 18 | 4 cycles et protections FloodWait | Cron actuel préservé, nouvelle copie Bot API fail-closed | Brancher mode Bot V2 sur nouveau cron après bascule seulement |
| 19 | Tableau de bord et trous initiaux | Compteurs corrigés, métriques doublons/cadence ajoutées | Vérification avec inventaire final |
| 20 | Surveillance doublons/retards/erreurs | File de revue + rapport de santé offline sans données sensibles | Notifications automatiques et processus de résolution humaine |
| 21 | Tests et non-régression | Nombreux tests offline + workflow CI + garde conflit | Dernier SHA au vert + essais d'intégration réellement autorisés |
| 22 | Tests production et respect des permissions | Préflight bot, attestation de droits, anti-concurrence | **Non réalisé :** aucun accès réel ni action en production |

**Statut global** : les algorithmes et les opérations offline des points 1,
2, 5, 7, 8, 9, 11, 12 et 13 sont codés ; **aucun des 22 points ne doit être
qualifié de validé en production**. Les points 3, 4, 6, 10, 14, 15, 16, 18,
19, 20, 21 et 22 exigent encore des validations ou compléments.

## Deux chemins de code à ne pas confondre

1. **Relais Anime existant** : `anime_catalog.py`, toujours utilisateur Telethon.
   Nouveau regroupement antidoublon, reprise de reçus, quota et
   `CINEX_ANIME_ARCHIVE_QUEUE_ENABLED=true` optionnel (désactivé).
2. **Relais Bot V2 indépendant** : `scripts/anime_bot_v2.py` et modules
   `anime_bot_*.py`. Aucune session personnelle. Opérations disponibles :
   `audit` (hors réseau), `migration-preview` (hors réseau),
   `migration-apply` (stockage privé approuvé), `alias-apply`,
   `poll` (ingestion Bot API), `publish` (publication).
   Les modes réseau exigent un bot distinct, les droits attestés et
   les canaux source autorisés.

Le Bot API ne peut **pas** parcourir l'historique d'un canal tiers. Le bot
doit être administrateur des sources et destinations pertinentes. Ne jamais
activer `getUpdates` sur un token déjà utilisé par un webhook ou un autre
système ; le préflight le refuse.

## Conflits détectés avec les autres travaux

- **PR #578 fusionnée dans main le 21/11/2026 vers 13:53 UTC** —
  *CinéX vidéothèque privée commune et bouton Télécharger* :
  **conflit de fusion initial résolu sur la branche d'intégration** sur `anime_catalog.py`,
  `category_runner.py` et `publication.py`. Les nouveaux liens
  Télécharger passent par la vidéothèque commune / CineRadarFr_Bot.
  **Ne pas écraser ou revenir à l'ancienne version de ces fichiers.**
  Réconcilier soigneusement l'antidoublon Anime, les reçus publics,
  `UnifiedLibrary` et les boutons de téléchargement avant tout déploiement.
- **PR #388** — *réactions après nouveau film* (ancienne PR encore ouverte),
  recouvrement avec `bot_http.py` et `category_runner.py`.
- Les modifications déjà sur `main` concernent aussi les webhooks et la
  réparation des anciennes publications. Elles doivent être recontrôlées
  **au moment de l'intégration**, pas seulement au début du projet.
- Le workflow `cinex-anime-v2-parallel-guard.yml` **échoue volontairement**
  si d'autres PR CinéX récentes ou `main` touchent les mêmes fichiers ;
  il n'effectue ni fusion ni correctif silencieux.

## Prérequis avant publication Bot V2

1. Inspecter le dernier commit de `main`, les PR CinéX récentes et
   leurs fichiers touchés ; rebaser/réconcilier sans écraser le travail tiers.
2. Obtenir un **bot dédié**, l'identifiant attendu, les droits administrateur
   source/privé/public et l'autorisation de republier chaque contenu.
3. Protéger un stockage durable **privé**, avec sauvegarde et verrouillage :
   les `file_id` et sources ne doivent pas être commités en clair.
4. Faire un `migration-preview` des reçus Anime historiques ; vérifier
   les collisions et épisodes publics hérités puis seulement importer.
5. Vérifier le **propriétaire du bot** de chaque ancienne fiche publique :
   une autre identité de bot ne peut pas éditer aveuglément les anciens posts.
6. Prendre en compte la vidéothèque commune en cours de développement (#578).
   Vérifier les liens privés, les accès abonnés et la déduplication dans les
   deux systèmes **avant** d'activer le nouveau relais.
7. Vérifier que le relais Anime **historique ne publie plus** pendant le
   basculement. Ne jamais faire tourner deux publicateurs sur les mêmes canaux.
8. Faire passer tous les tests du SHA final, puis un audit en lecture seule,
   puis seulement un test Telegram limité avec contrôles de reçus et rollback.
9. Garder la version actuelle active jusqu'à preuve que la nouvelle est sûre.

## Limites connues qui exigent décision ou accès extérieur

- Le robot ne peut pas effacer le risque d'anciens doublons sans comparer
  l'état réel des chaînes Telegram et les reçus historiques ; aucune
  suppression de messages n'a été effectuée.
- La file Bot V2 démarre sur des **nouveaux** `channel_post` ; elle ne peut
  pas importer l'historique de sources non autorisées.
- Les contenus spéciaux OVA/ONA sont volontairement isolés, pas diffusés à
  tort sous `S01E01`.
- Une réponse réseau indéterminée peut requérir une vérification humaine ;
  la sécurité contre les doublons prime sur l'automatisation absolue.
- L'intégration de la vidéothèque centrale (#578), l'envoi effectif de
  notifications de supervision et la validation réelle des droits sont
  **des travaux ouverts** ; ne pas les déclarer terminés.

## Phase d'intégration du 21/11/2026 (PR #585)

- Nouvelle branche reconstruite depuis le `main` contenant les mises à
  jour récentes, notamment la vidéothèque commune (#578), le registre CineRadar
  et les corrections webhook.
- Les trois fichiers conflictuels ont été intégrés manuellement. L'envoi
  vers la vidéothèque unifiée et les boutons `download_url` sont préservés ;
  l'ancienne PR #576 ne doit plus être fusionnée indépendamment.
- Le scanner historique a une protection supplémentaire : un identifiant de
  vidéo associé à plusieurs numéros d'épisodes distincts est mis en
  quarantaine. Même protection du côté des `file_unique_id` du Bot API.
- `scripts/anime_bot_readiness.py` + workflow
  `cinex-anime-v2-readiness.yml` : contrôles **en lecture seule** des
  autorisations, de l'identité du bot, des droits, du stockage privé et des
  reçus historiques, sans consommation de `getUpdates`.
- **La fusion du code sur main n'active pas le nouveau Bot API** : aucun
  canal source, token dédié, transfert vers la vidéothèque commune ou
  migration des reçus ne doit être deviné.
- Le calendrier existant des **4 cycles par jour** reste inchangé.
- Contrôle de la production avant bascule : `main` et la liste des PR
  pertinentes doivent être consultés une nouvelle fois. La fin des
  traitements GitHub Actions en cours doit être vérifiée, ainsi que les
  éventuels rapports de santé, avant de déclarer le système opérationnel.

### Critères indispensables pour dire « chantier 22 terminé »

1. Tous les tests CI sur le SHA exact intégrable sont verts et le scan
   historique est passé en lecture seule.
2. Le contrôle réel des permissions Bot API valide **tous** les canaux
   sources, la vidéothèque privée et le canal Anime public.
3. Les droits de redistribution des médias et GIF sont vérifiés, pas
   déduits du seul accès Telegram.
4. Les anciennes fiches et épisodes sont réconciliés sur Telegram ; aucune
   copie supposée sans reçu. Les résultats d'envoi incertains sont résolus.
5. La même vidéo reste disponible via le dossier privé et, si activé,
   via le vrai bot de téléchargement CineRadar, sans lien cassé.
6. L'ancien publicateur Anime est désactivé avant l'activation du nouveau.
7. Un test de publication réel, limité et autorisé, est suivi d'un
   second cycle idempotent sans nouveau doublon.
8. Les quatre exécutions quotidiennes, la file de rattrapage et les
   alertes sont observées sur la durée.

**Ne pas déclarer le point #22 achevé si ces vérifications externes
ne sont pas démontrées.**

## Résultat réel après fusion du 21/11/2026 (lecture seule)

- PR #585 **fusionnée** : `9ee3eccfbca722bfd3c95e1c9dcabc42250bcf03`.
- Validation post-fusion du relais **réussie** sur `main`.
- Préflight Bot API :
  https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/44942650177
  (workflow réussi comme **diagnostic**, mais `ready_to_publish=false`).
- **0 canaux sources numériques autorisés configurés** pour le nouveau bot ;
  `CINEX_ANIME_SOURCE_BOT_TOKEN` et son identité attendue ne sont pas
  configurés ; les IDs numériques des destinations manquent.
- Attestation des droits de publication, du stockage privé durable,
  du basculement et de la compatibilité vidéothèque commune **absentes**
  de la configuration attendue.
- L'ancien relais Anime est **encore actif**. Le remplacer maintenant
  sans accès aux canaux sources créerait un risque de rupture de service.
- Prévisualisation de migration : **7 séries, 128 épisodes privés,
  23 paires publiques vérifiées**, **105 épisodes historiques sans reçus
  publics de type nouveau format**. Cela ne prouve pas que les 105 sont
  absents de Telegram ; toute republication en aveugle reste interdite.
- Aucun test de publication réelle par le nouveau bot n'a été exécuté.

**Conclusion :** l'intégration du code de V2 est déployée, mais le chantier
22 ne peut pas être considéré comme « complètement terminé ». La
configuration externe et la réconciliation des anciens reçus restent
obligatoires. Ne jamais contourner les gardes de sécurité pour produire
artificiellement un feu vert.

## Audit complémentaire du 21/11/2026 — préserver le chantier parallèle

**PR #586 fusionnée** : https://github.com/MrXPRONOS/MrXPRONOS_App/pull/586
**Audit réel des bots** :
https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/44943796210
(succès du workflow de lecture seule ; **aucune autorisation de publication V2**).

- **10 sources Anime configurées** dans l'ancien système, mais **0/10**
  accessibles comme administrateur aux **deux bots effectivement exposés**
  par les secrets GitHub de ce workflow (`radar` et `legacy`).
- Ces deux bots disposent de droits de publication dans les destinations
  Anime et le stock privé central ; leurs **webhooks sont actifs**.
  **Ne pas utiliser `getUpdates` avec ces tokens** : cela perturberait la
  consommation de mises à jour de CineRadar/l'ancien relais.
- Ce diagnostic ne prouve PAS qu'aucun autre bot existe dans Telegram : seuls
  les **deux secrets disponibles** ont pu être contrôlés. Il faut soit un
  accès Bot API autorisé aux sources, soit un flux entrant fourni par celles-ci,
  sans inventer l'historique inaccessible par bot.
- Le stock privé unique **CinéX — Stock privé**, son empreinte SHA256
  approuvée et les bots déjà administrateurs **ne doivent pas être remplacés**
  par un nouveau canal ou des permissions élargies.
- D1 CineRadar lu directement en mode **SELECT uniquement** : **7 liens
  publiés**, **11 reçus de livraison** (5 `sent`, 6 `deleted`),
  **1 configuration de stock privé marquée prête**, et le service de
  téléchargement est **activé**. L'inventaire comporte des références à
  **2 ID de canaux source distincts** : elles ne sont pas une preuve de deux
  stocks privés actuels. Vérifier chaque ancien lien et sa destination avant
  modification ; ne supprimer aucune référence historique automatiquement.

### Règles impératives reprises de l'autre discussion

1. Conserver la vidéothèque commune, `@CineRadarFr_Bot`, le registre D1,
   les boutons `Télécharger`, les liens existants et les correctifs webhook.
2. Maintenir la rotation : dix dernières vidéos publiques par canal ;
   dix suppressions **maximum** par canal et cycle, uniquement après
   validation complète du couple affiche/vidéo et de l'archive privée.
   Ne jamais effacer les vidéos du stock central.
3. Reconnaître affiche → vidéo et affiche → texte → vidéo. Refuser toute
   association ambiguë, et préserver les anciennes publications non
   identifiées plutôt que de les détruire par défaut.
4. Préserver les workflows de publication, les délais anti-FloodWait et les
   mécanismes de sauvegarde/réconciliation existants.
5. Ne pas affirmer que les **105 épisodes sans nouveau reçu public** sont
   absents : une partie peut être représentée par des fiches historiques.

### État du chantier 22 après ce contrôle

Le **code Anime V2 a été intégré**, les validations CI sont passées, et le
contrôle des bots existants a réellement été exécuté. **La bascule 100 % bots,
la vérification des droits de distribution pour toutes les sources et le
test réel sans doublon ne sont PAS terminés.**

**Blocage externe vérifié, non contournable par code seul :** les bots
contrôlés n'ont pas accès aux 10 sources Anime. Aucune nouvelle publication,
suppression, édition de droit Telegram ou désactivation des workflows
existants ne doit être faite pour simplement masquer ce blocage.
