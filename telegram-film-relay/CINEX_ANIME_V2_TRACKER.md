# CinéX Anime V2 — suivi des 22 chantiers et intégration sécurisée

Préparation ouverte le **21 novembre 2026** sur une branche isolée :
`fix/cinex-anime-v2-dedup-followup-20261121`.
PR de préparation : https://github.com/MrXPRONOS/MrXPRONOS_App/pull/576

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

| # | Correction / amélioration | Code sur PR #576 | Ce qui manque pour la clôture définitive |
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

- **PR #578** — *CinéX vidéothèque privée commune et bouton Télécharger*,
  en développement parallèle. Recouvrement avec notre PR sur
  `anime_catalog.py`, `category_runner.py`, `publication.py`.
  Cet autre projet introduit une **vidéothèque centrale**, qui doit être
  prise en compte au moment du basculement pour éviter deux copies ou
  des liens Télécharger incompatibles.
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
