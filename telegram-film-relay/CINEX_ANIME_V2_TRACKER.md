# CinéX Anime V2 — correction, améliorations et vérification

Date initiale : 2026-11-21. Branche : `fix/cinex-anime-v2-dedup-followup-20261121`.
PR : https://github.com/MrXPRONOS/MrXPRONOS_App/pull/576

**Statut : changements proposés, non déployés en production.** Aucun post Telegram
n'est envoyé par les tests de cette branche. Un test hors ligne passé ne prouve
ni l'accès aux canaux sources, ni la permission de republier leurs contenus.

## Contrat fonctionnel

- Quatre exécutions par jour, à 00:17, 06:17, 12:17, 18:17 UTC.
- En mode nouveaux épisodes : au plus quatre épisodes de quatre animés distincts
  par cycle, un seul nouvel épisode sélectionné par animé, avec priorité aux
  précédents épisodes manquants.
- Les saisons **explicitement complètes et prouvées** gardent leur transfert
  exclusif par lot (plafond existant : 25 épisodes), sans les réduire à quatre.
- Chaque série conserve une seule identité canonique, ses index privés,
  ses annonces déjà envoyées et ses reçus de source d'origine.
- En cas de doute sur un upload après erreur réseau, **arrêter et récupérer** :
  jamais relancer sans vérification au risque d'un doublon.
- Aucun transfert depuis une source protégée ou sans droits de redistribution.
- Architecture future 100 % Bot API : subordonnée à l'accès effectif des bots
  aux canaux sources et à la disponibilité des archives nécessaires. Les
  sessions personnelles existantes ne sont pas encore remplacées.

## Suivi des 22 chantiers

| # | Chantier | Statut sur la branche | Observations / validation restante |
|---|---|---|---|
| 1 | Import manquant `verify_library_bot` | Code corrigé | Import des trois fonctions réellement appelées dans `category_runner.py`; test d'exécution réelle encore nécessaire |
| 2 | Doublons (titre + saison + épisode) entre sources | Implémenté, à valider en production | `anime_dedup.py`; reçus alternatifs et rapprochement des vidéos privées existantes |
| 3 | Média identique, noms/fichiers différents | Partiel | Regroupement au niveau de l'épisode et audit de `document.id`; pas de hachage du contenu binaire |
| 4 | Fiches/affiches/vidéos publiques dupliquées | Partiel | Marqueur de couple d'épisode, recherche des envois antérieurs, reçus persistés ; nettoyage des doublons historiques non effectué |
| 5 | Reprise d'upload après crash/time-out | Partiel | `pending_public_episode_posts`, affiche persistée avant vidéo, reprise des vidéos connues, blocage quand état incertain |
| 6 | Consolidation des anciennes fiches | Existant, à améliorer | `anime_identity.py` conserve ID et quarantaines ; audit manuel des collisions restant |
| 7 | Alias et orthographes de titres | Partiel | Résolution explicite des alias et normalisation prudente ; revue des collisions restantes |
| 8 | Nouveaux épisodes des animés déjà publiés | Implémentation initiale | Sélection des suites consécutives après les reçus de saison, tests hors ligne |
| 9 | Vidéo isolée / affiche / texte / GIF | Partiel | Classement affiche→texte→vidéo présent et GIF de cadence reconnu ; les vidéos ambiguës restent ignorées |
| 10 | Mention « Hebdomadaire » / bimensualité | Implémentation initiale | Détection dans textes et noms de GIF, métadonnée `cadence_hint`; GIF de présentation non créé |
| 11 | Quatre épisodes de quatre animés distincts | Implémentation initiale | Nouveau sélecteur sans modifier le calendrier 4 fois/jour; test Telegram réel encore requis |
| 12 | Saisons complètes par lots | Préservé | Mode complet prioritaire et exclusif ; limite historique 25 par lot |
| 13 | File d'attente durable | Partiel | Le catalogue et `active_batch` assurent certaines reprises ; file de découverte distincte pas encore réalisée |
| 14 | Archives/cursors et arriérés | Partiel | Rapprochement de reposts déjà publiés réduit les blocages ; file d'ingestion indépendante à faire |
| 15 | Saisons partielles / hors-série / numéros manquants | Partiel | Traitement progressif sans sauter les trous ; hors-séries et OVA non intégrés |
| 16 | Index, cartes et boutons enrichis | Existant, à améliorer | Mise à jour d'index conservée ; annonces de nouveautés plus explicites à concevoir |
| 17 | Collecte et publication 100 % bots | Non réalisé | Architecture actuelle lit/transfère encore avec une session utilisateur ; accès Bot API aux sources à qualifier |
| 18 | Quatre cycles / FloodWait | Conservé, amélioration restante | Cron `17 */6 * * *` et pacing existant; cooldown dynamique unifié à revoir |
| 19 | Statistiques du tableau de bord | Partiel | Comptage des premiers épisodes absents corrigé ; métriques de doublons/cadence ajoutées |
| 20 | Alertes, retards et santé réelle | Partiel | `cycle_monitor` existant ; alertes dédiées doublons/envois incertains à intégrer |
| 21 | Tests de régression et des interruptions | En cours de validation CI | Tests ajoutés sans réseau ; validation complète et environnement live restant |
| 22 | Test production et contrôle droits | Non réalisé | Aucun vrai envoi ni fusion de PR avant validation des permissions et absence de doublons |

## Critères d'acceptation avant fusion

1. Tests `telegram-film-tests.yml` et `cinex-anime-quality.yml` au vert sur le SHA final.
2. Scanner les anciens reçus, comparer les identités, évaluer les collisions et
   les messages déjà publiés, sans suppression ni nouvelle publication.
3. Vérifier explicitement que les bots ont accès à **chaque source autorisée**,
   aux vidéothèques et aux canaux publics.
4. Valider des simulations réalistes : 4 séries nouvelles, 1 saison complète,
   nouvelle vidéo d'une ancienne saison, même vidéo depuis deux sources,
   reprise après envoi incertain et vrai manque d'épisode.
5. Seulement ensuite procéder à un test de production contrôlé, avec surveillance
   des messages, reçus et quotas.
6. Ne déclarer « corrigé en production » qu'après constat Telegram et logs GitHub.

## Nouvelles améliorations non encore programmées

- Vraie collecte via `channel_post`/Bot API avec stockage de file durable,
  sans dépendance à une session personnelle, **seulement** sur les canaux
  qui acceptent l'accès du bot.
- GIF original « ANIMÉ HEBDOMADAIRE » en option, compatible publication
  bot, avec fallback légende texte.
- Priorités et équité inter-cycles, saison complète au-delà de 25 via reprises
  de lots contrôlés, et gestion OVA/ONA/specials distincts.
- Audit historique des doublons publics, consultation sans suppression
  automatique, redirection des anciennes fiches vers l'index conservé.
- Alertes pour titres ambigus, médias variantes, liens expirés, nouveaux
  épisodes non publiés et files d'attente anormalement longues.
