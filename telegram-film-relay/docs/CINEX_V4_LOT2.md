# CinéX V4 — Lot 2 : publications et vidéothèques

## Règle commune pour les nouvelles fiches

**Public (quatre boutons, dans cet ordre)** : VOIR LE FILM / LA SÉRIE / L'ANIMÉ, TÉLÉCHARGER LA VIDÉO / LES VIDÉOS, REJOINDRE LE CANAL SECOURS, REJOINDRE LE DOSSIER. Le lien de visualisation vise la vidéo exacte dans la bibliothèque privée ; le lien de téléchargement est un reçu `CineRadar` vérifié, pas une recherche ou une URL inventée.

**Vidéothèque privée (trois boutons, dans cet ordre)** : REJOINDRE LE CANAL principal (`https://t.me/<handle vérifié>`), REJOINDRE LE DOSSIER, TÉLÉCHARGER (CineRadar). Le bouton Secours **n'est pas** ajouté aux fiches privées.

Les fichiers source et la description authentique sont préservés. Le contrôle de l'affiche publique compare strictement les quatre destinations, et la vidéo publique copiée par bot compare aussi les libellés.

## Ordre transactionnel

1. Détecter le document source et sa véritable affiche.
2. Vérifier/dédupliquer puis sauvegarder **l'affiche et la vidéo** dans le stock central privé CineRadar. Attendre un reçu D1 valide ; si absent, ne pas publier.
3. Publier ou corriger **en place** la fiche illustrée privée avec les trois boutons ; aucune nouvelle photo en cas de reprise de l'ancien message.
4. Publier/identifier la vidéo correspondante en vidéothèque de catégorie.
5. Publier la fiche publique à quatre boutons, puis copier la vidéo publique avec les mêmes quatre boutons et le reçu `#CINEX_VIDEO_24H_V1` déjà défini au Lot 1.
6. Écrire les reçus anti-doublons. Les erreurs d'issue incertaine arrêtent le flux sans renvoi à l'aveugle.

Ce contrat s'applique aux relais Films, Comédie, Action, Désir, films d'animés et aux épisodes Séries/Animés des catalogues.

## Bot-only Anime V2

Le bot autonome ne peut pas utiliser la session Telethon. Il copie directement affiche + vidéo du canal source vers le **même stock central**, enregistre la référence exacte via CineRadar, puis publie dans la vidéothèque Anime (fiche 3 boutons, vidéo) et dans le public (fiche + vidéo 4 boutons). Chacun de ses envois possède un reçu idempotent, et un résultat incertain stoppe les reprises.

La publication réelle exige le bot administrateur du stock central, les variables owner-approved, l'accès D1 et l'invitation Secours vérifiée dans son runtime. Aucun accès, lien ou bot alternatif n'est inventé.

## Compatibilité des catalogues / limitations

Les **fiches illustrées** créées à partir du Lot 2 reçoivent trois boutons. Les anciennes fiches retrouvées et identifiées sont mises à jour **sur place** lorsque leur téléchargement peut être vérifié et que le bot en est l'auteur. Les anciennes fiches sans preuve de téléchargement ne sont ni falsifiées ni dupliquées.

Les index de saisons restent des messages à liens dynamiques pour les nombreux épisodes (ils ne sont pas des fiches-photo). Leur regroupement et la présentation par saison relèvent du **Lot 3**. Le lien de téléchargement d'une fiche d'accueil de série ouvre le premier épisode vérifié ; la description doit l'indiquer clairement. Chaque épisode possède son propre lien de téléchargement.

**Tests** : GitHub Actions `CineX - Tests videos 24h et boutons (hors ligne)` ; aucune publication réelle déclenchée par un push. Pour déclarer la production totalement vérifiée, observer une publication réelle sur au moins un canal de chaque catégorie, incluant le bot autonome, et vérifier les permissions.
