# CinéX V4 — Lot 3 : saisons et épisodes progressifs

## Contrat (séries TV et animés)

- **Une saison par titre et par cycle.** Un autre titre peut être traité lors du même cycle, sous réserve du quota et des contrôles de la session Telegram. Si S01 et S02 sont complètes, S01 est prioritaire, S02 arrive au cycle suivant.
- **Saison annoncée complète :** publier tous les épisodes numérotés et réellement disponibles de cette saison dans un même lot, jamais les 12/25 premiers arbitrairement. Maximum technique **50 épisodes** par lot ; au-delà, bloquer pour revue plutôt que couper en deux.
- **Saison en cours :** si E01–E04 sont disponibles, publier une seule fiche « Saison 1 — Épisodes 1 à 4 » puis quatre vidéos dans l'ordre. Si E05 arrive plus tard, publier une autre fiche « Saison 1 — Épisode 5 » puis cette vidéo. E06–E07 arrivant ensemble donnent un seul nouveau lot. Les reçus des épisodes précédents ne sont pas renvoyés.
- **Trou de numérotation :** jamais d'E06 avant E05 si E05 n'est ni publié ni présent dans le lot. Aucun nom de fichier ambigu ne reçoit de numéro inventé. Seules les annonces explicites dans la source justifient « Hebdomadaire ».
- **En cas de crash :** l'identité du lot, ses sources exactes et les reçus par index, photo et vidéo sont enregistrés. Une diffusion incertaine reste bloquée pour vérification ; aucun renvoi aveugle.

## Publication dans les canaux de catégorie (Telethon + Bot)

1. Verrouiller le lot de source, vérifier vrais numéros/affiche/documents.
2. Archiver **chacune** des vidéos avec sa véritable affiche dans le stock central privé CineRadar ; obtenir chaque URL vérifiée.
3. Créer dans la vidéothèque privée un **index de téléchargement** du lot (une URL CineRadar par épisode), puis une **seule affiche de lot** avec trois boutons : rejoindre le canal principal, rejoindre le dossier, télécharger les vidéos (index).
4. Envoyer toutes les vidéos privées du lot par ordre d'épisode, sans affiche répétée.
5. Créer dans le canal public une **seule fiche** identifiant saison et plage d'épisodes. Quatre boutons : voir la série/animé (vers la fiche privée), télécharger les vidéos (vers l'index), rejoindre le canal Secours vérifié, rejoindre le dossier.
6. Copier toutes les vidéos dans le public **après** la fiche, dans l'ordre, avec les **mêmes quatre boutons** et le marqueur de rétention \`#CINEX_VIDEO_24H_V1\`. Chaque envoi reste distinctement vérifié et reçu ; le nettoyage horaire du Lot 1 concerne ces vidéos seulement.

L'index privé est envoyé *avant* la fiche pour pouvoir obtenir un ID réel ; la chronologie visible pertinente reste **fiche → épisodes**. Les anciennes fiches originales, anciens posts à deux/quatre boutons, et anciennes vidéos sont conservés ; seules les nouvelles diffusions utilisent le regroupement. Pour les anciens lots partiellement archivés, il peut exister des vidéos antérieures à la nouvelle fiche ; ces vidéos sont conservées et jamais dupliquées uniquement pour des raisons cosmétiques.

## Bot-only Anime V2

Le bot autonome suit le même ordre avec les seules méthodes du Bot API : copies centrale illustrée, liens D1, index, fiche privée et vidéos privées, fiche publique et vidéos publiques avec quatre boutons. La session personnelle n'est pas utilisée. Chaque opération a un reçu durable \`inflight/uncertain/complete\`.

**Bascule production indépendante** : toujours soumise à la présence du token du bot dédié, à l'identité et aux sources autorisées, aux droits des deux destinations et du stock central, à l'état persistant et à la preuve de désactivation du relais ancien. Aucune de ces autorisations n'est inventée. Tant que ces éléments ne sont pas confirmés, le relais historique Anime reste le chemin de production configuré.

## Vérifications et limites

Tests sans réseau : \`python -m unittest discover -s tests -p 'test_season_batches_v4.py' -v\`, \`test_anime_bot_pipeline.py\`, \`test_series_catalog.py\`, \`test_anime_catalog.py\`, et la suite complète \`telegram-film-tests.yml\`. Vérifier en lecture seule les messages réels d'un nouveau lot et les statuts du workflow horaire avant d'annoncer « validé en direct ».

Les mécanismes de conservation/suppression n'accordent aucun droit sur les films, séries ou animés, et ne constituent pas une protection contre les retraits ni la modération de Telegram. N'alimenter les sources et destinations qu'avec les droits de diffusion nécessaires.

## Lots adjacents

- Lot 1 : secours limités aux relais principaux ; durée de vie des nouvelles vidéos automatiques publiques 24 h, sous réserve des autorisations Telegram / workflow actif.
- Lot 2 : quatre boutons pour le public, trois pour les nouvelles fiches privées, liens CineRadar réels.
- Lot 4 : spécialisation du nouveau canal Fichiers Cloud dans l'horreur/thriller après vérification de sa vidéothèque privée et de son Secours.
