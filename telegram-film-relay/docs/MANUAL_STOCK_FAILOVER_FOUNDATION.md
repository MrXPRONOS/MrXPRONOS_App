# CinéX + Formation — stock manuel et publication hybride

Date de conception : 24 novembre 2026.

## Avancement réel

La PR #676 est une intégration PARTIELLE, désactivée par défaut. Elle contient :

- Un inventaire des systèmes Films, Séries, Animés, Comédie, Désir, Action et Formations.
- Le moteur Python de sélection des candidats, quotas inter-modes et refus de
  bascule en cas de FloodWait, PeerFlood ou réponse incertaine.
- La réception de messages Telegram dans le Worker CinéRadar EXISTANT
  (chemin webhook /telegram ; pas de deuxième getUpdates).
- Une table D1 privée pour les sources explicitement approuvées, l'inventaire
  des messages, et la structure d'un futur journal d'envoi.
- Un prévol manuel de réutilisation/création d'UN canal privé par lancement :
  workflow cinex-manual-vault-provision.yml ; mode simulation par défaut.
- Des tests de réceptions répétées, modifications de médias, droits, titres,
  conflits de vidéos, sélection prudente et canaux existants.

**NON ENCORE RÉALISÉ / NE PAS ACTIVER EN PRODUCTION :**

- Les canaux privés réels n'ont pas été inventoriés et reliés à leurs destinations.
- Aucun canal Telegram n'a été créé par la PR et aucun bot n'a été promu.
- La base n'a pas reçu d'importation des anciens messages manuels.
- Le moteur de publication bot-only complet n'est PAS branché aux catalogues,
  flux de formation, boutons V4, reçus CineRadar et quotas existants.
- Le registre D1 n'est pas encore réconcilié avec tous les reçus historiques
  des publications normales. La bascule automatique reste donc désactivée.
- Aucun essai réel bout en bout n'a été effectué.

Ne jamais fusionner cette PR en la présentant comme une reprise de production
fonctionnelle. Les tests hors ligne ne prouvent pas une publication Telegram.

## Inventaire des réutilisations prioritaires

Sources candidates, à vérifier en direct comme des canaux réellement privés
appartenant au compte propriétaire :

- Films : TG_PRIVATE_CHANNEL.
- Séries : SERIES_PRIVATE_CHANNEL.
- Animés : ANIME_PRIVATE_CHANNEL.
- Comédie : COMEDIE_PRIVATE_CHANNEL.
- Désir : DESIR_PRIVATE_CHANNEL.
- Action : ACTION_PRIVATE_CHANNEL.
- Formation générale : FORMATION_STAGE_CHAT (canal technique).
- Formation Business / Finance / Digitale / Mindset : canaux privés
  correspondants dans FORMATION_DESTINATIONS_JSON.

Chaque source peut être remplacée explicitement par le secret GitHub
CINEX_MANUAL_<CATEGORIE>_CHAT si les canaux existants ne doivent pas servir de
réserve d'import. Un canal privé existant qui ne correspond pas à son rôle,
qui n'est pas possédé par l'utilisateur ou qui est inaccessible au bot ne peut
pas être activé à l'aveugle.

**Important :** les canaux Secours pour abonnés ne sont pas des réserves
d'importation. Le stock central CineRadar sert à la livraison vérifiée, et
les vidéothèques de catégories gardent leurs propres liens et contenus.

## Comment déposer les données, après activation des sources

- Pour un film autorisé : une vraie photo de couverture et une vraie vidéo,
  chacune avec un titre explicite et la même année (par exemple
  « Titre: Exemple » et « Année: 2025 »).
- Séries et animés : vrai titre et vrais codes S01E01, S01E02 ; aucune
  numérotation inventée. Une affiche de saison et plusieurs épisodes doivent
  être rattachés par le moteur de saisons existant, pas par un simple
  rapprochement approximatif.
- Formation : affiche ou annonce, fichiers, regroupement complet, catégorie,
  crédits de l'auteur. Les archives sont enregistrées comme références et
  jamais extraites ni exécutées par le webhook.
- Telegram photo, vidéo, document MKV et pièce jointe formation sont
  indexés comme des références. Aucune vidéo n'est téléchargée vers GitHub
  ou Cloudflare D1.

Un fichier qui a été renommé ou réencodé peut ne pas partager l'identifiant
Telegram de l'original ; le titre, l'épisode et les reçus restent indispensables.
Aucune détection ne garantit 100 % des doublons.

## Sécurité et exploitation

Le Worker n'écoute les réserves approuvées que si
CINEX_MANUAL_INBOX_ENABLED=true est configuré volontairement après prévol.
La table cine_manual_fallback_sources doit avoir pour chaque canal les drapeaux
owner_approved=1, rights_attested=1, bot_access_verified=1, enabled=1.

Le workflow de provisioning ne peut créer une réserve que via la session
personnelle authentifiée, jamais lorsque la session est révoquée.
Il respecte le verrou mrx-telegram-personal-account et le cooldown.
Une nouvelle réserve est limitée à une catégorie et un canal par exécution.
Le bot identifié doit être précisément CineRadar ; seuls les droits minimaux
de publication dans la source privée peuvent être accordés. Une identité
incorrecte bloque toute promotion.

L'application des migrations D1 et le référencement du canal sont
conditionnés aux variables explicites CINEX_MANUAL_RIGHTS_ATTESTED=true et
CINEX_MANUAL_OWNER_APPROVED=true. Ces attestations ne sont pas déduites de
la seule présence d'un fichier ou d'un canal.

La session utilisateur reste PRIORITAIRE. Le repli est autorisé uniquement si
son absence/révocation a été confirmée. FloodWait, limite Telegram, réponse
réseau incertaine ou droits insuffisants ne justifient pas un contournement.

## Pour terminer l'intégration

1. Auditer en lecture seule les canaux réels, leurs administrateurs et leurs
   bibliothèques ; réutiliser les réserves existantes.
2. Créer seulement celles réellement manquantes et valider les permissions.
3. Activer l'ingestion des nouvelles publications, sans publication publique.
4. Importer les stocks antérieurs autorisés et réconcilier les reçus normaux.
5. Ajouter les adaptateurs de publication bot-only par catégorie, en réutilisant
   les contrats existants : CineRadar D1, V4 quatre/trois boutons,
   saisons complètes/progressives, crédits et formations multi-fichiers.
6. Ajouter un verrou commun et un quota calculé depuis les publications normales
   et de secours du même cycle.
7. Réaliser une simulation de session révoquée et un essai Telegram réel avec
   des médias autorisés pour chaque catégorie, contrôler liens et reprises.
8. Activer progressivement le basculement derrière un interrupteur distinct
   de celui de l'ingestion, et conserver le chemin de retour arrière.

Aucun secret ni identifiant de canal privé ne doit être exposé dans GitHub.

## Avancement complémentaire du 24 novembre — vérifications réelles

- Contrôle de la base Cloudflare D1 existante effectué en lecture : stock central
  configuré et prêt, **178 copies médias en état stored**, 178 liens classiques
  marqués published. Les vidéothèques Action et Séries ont chacune un accès
  bot vérifié et une attestation de droits dans le registre consulté.
- Migration 029 appliquée à la même base D1 : six opérations réussies ; les
  trois tables du secours manuel existent désormais en production.
- **L'ingestion manuelle reste désactivée** dans le code Worker
  (CINEX_MANUAL_INBOX_ENABLED=false). Les nouveaux canaux privés ne sont pas
  encore reconnus et aucune publication autonome n'est activée.
- Planificateur hors réseau ajouté pour films (couverture + fichier), épisodes
  SxxExx progressifs sans trou et formations multi-parties complètes. Quotas
  et blocage si une même identité média revendique plusieurs contenus.
- Journal D1 ajouté pour les différentes étapes de publication : reserve,
  inflight, uncertain et complete. Une issue inconnue interdit tout renvoi
  automatique sans réconciliation manuelle, y compris après un redémarrage.
- Audit agrégé en lecture seule ajouté ; il ne renvoie ni identifiants des
  canaux privés, ni fichiers, ni descriptions des médias.
- Les destinations publiques de Formation ne sont **jamais** converties en
  sources privées par simple similarité de catégorie : des réserves spécifiques
  doivent être réellement privées et validées.

Le journal et le planificateur ne constituent pas encore un publisher complet.
Les reçus des modes personnels ne sont pas tous réconciliés dans la structure
commune et aucun test de bascule réel n'a été passé. Ne pas déployer ni annoncer
un fonctionnement autonome final avant ces contrôles.

## Extension du 24/11 : moteur bot-only réel ajouté, lancement contrôlé

Code présent sur la branche :
- cinecanaux/manual-fallback-live.mjs : transmission de vrais messages Telegram
  par copyMessage/sendMessage (films, séries, animés, formations), registre
  CineRadar D1, carte privée 3 boutons et carte/vidéo publique 4 boutons,
  téléchargements vérifiés, reprise à partir de reçus immuables.
- cinecanaux/manual-fallback-cycle.mjs : recherche D1, sélection par quotas,
  vérification historique Film + Séries + Animés, contrôle de tous les
  droits du bot, et publication SEULEMENT si la session personnelle est
  réellement absente/révoquée.
- telegram-film-relay/scripts/probe_personal_session_for_fallback.py :
  ne bascule JAMAIS en cas de FloodWait/PeerFlood, connexion incertaine,
  cooldown actif ou session valide.
- .github/workflows/cinex-manual-fallback-live.yml : déclenchement programmé
  après les cycles personnels, sous verrou mrx-telegram-personal-account.
- cinecanaux/manual-fallback-expiry.mjs et son workflow horaire :
  expiration des vidéos publiques 12h après envoi, sans jamais supprimer
  une source ou une vidéothèque privée ; résultat incertain bloqué.
- cinecanaux/tests/manual-fallback-live.test.mjs et expiry.test.mjs :
  tests réseau simulés garantissant les étapes et l'idempotence.

D1 a déjà été préparé : migration 029 (réserves+références+reçus) et 030
(expiration) appliquées sans incident. Les deux bibliothèques privées
Action et Séries, déjà attestées owner_access et bot_access verified le
24/11, ont été inscrites dans la liste D1 des réserves activées.
AUCUN média manuement déposé n'a encore été enregistré dans la nouvelle
boîte de réception et aucun nouvel envoi ne peut être déclaré testé
en conditions réelles.

### Instructions de dépôt manuel (après déploiement de la version activée)

Film : une photo avec légende
    Titre: Mon Film
    Année: 2025
puis un vrai fichier vidéo avec même titre et même année.

Série / animé : une vraie photo d'affiche saison avec
    Titre: Ma Série
    S01
puis des vrais épisodes ordonnés avec
    Titre: Ma Série
    S01E01
    ...
Les épisodes manquants ne sont jamais inventés ou sautés.

Formation : une affiche
    Cours: apprentissage-2026
    Auteur: Nom du formateur autorisé
puis chaque fichier (PDF, vidéo, document, ZIP, etc.) avec
    Cours: apprentissage-2026
    Total: 3
    Partie: 1/3
et ainsi de suite jusqu'à 3/3. Aucune formation incomplète ou
dépourvue de crédit d'auteur n'est envoyée.

Aucune extension exécutable ou fichier protégé ne peut être sélectionné.
Le stockage manuel existant dans la même vidéothèque est pris en charge :
la vidéo originale est référencée, pas envoyée deux fois dans la réserve.

### Restrictions subsistantes et critères de disponibilité

Un moteur complet dans GitHub ne prouve pas que Telegram peut publier.
Seules les sources réellement possédées, approuvées, bot-admin et couvertes
par des droits de redistribution pourront fonctionner. Les autres
catégories nécessitent encore un audit live des canaux et un workflow
de provisioning autorisé. Les invitations Secours sont à vérifier :
l'archive D1 consultée ne contient actuellement qu'une entrée dédiée
au canal Films. Les catégories sans Secours vérifié sont bloquées.
Les bots de catégorie doivent aussi être inscrits dans les permissions
réelles du stock central : les anciens inventaires ne prouvent pas
leur accès, et aucune permission ne peut être supposée.
Les 178 vidéos d'archive déjà publiées ne constituent PAS du stock
neuf pour être republiées.

Même après fusion/déploiement, un canal en attente de permissions, sans
stock manuel, sans liens Secours ou avec erreur Telegram est marqué
« non prêt », pas « opérationnel ». Sans vrai essai de contenu autorisé,
ne jamais affirmer une validation bout en bout.
