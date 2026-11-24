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
