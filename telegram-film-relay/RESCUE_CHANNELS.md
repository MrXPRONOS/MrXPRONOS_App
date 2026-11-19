# Ciné X — Canaux « Secours » automatiques

## Objectif et canaux
Créer **un canal Telegram privé**, exclusivement pour le secours de chaque canal principal sous contrôle du compte utilisateur. Le titre est le titre **exact** du canal principal plus ` Secours` (exemple : `Ciné X Films VF Secours`).

Cinq destinations sont prévues à partir du relais existant :
- Films : `TG_PUBLIC_CHANNEL` (par défaut `@CineXFilms_vf`)
- Séries : `@seriesvf_cinex` (destination de Ciné Radar, même si l'ancien catalogue Séries publie encore sur le canal Films configuré)
- Désir : `DESIR_PUBLIC_CHANNEL` (par défaut `@CineXDesirfr`)
- Comédie : `COMEDIE_PUBLIC_CHANNEL` (**doit être renseignée**)
- Animés : `ANIME_PUBLIC_CHANNEL` (par défaut `@CineXAnimeFR`)

Le miroir externe Torrent9 est volontairement ignoré tant que les transferts miroir sont suspendus.

## Principe
- Le compte Telegram propriétaire existant (secret `TG_STRING_SESSION` ou alias) récupère la vraie identité et le nom du canal public. Le processus refuse d'agir si le compte n'en est pas le créateur.
- Il recherche d'abord un canal **privé** portant exactement `<Titre public> Secours`. Un homonyme ambigu est rejeté.
- Sinon il crée le canal privé via Telegram, récupère son identifiant `-100...`, puis exporte un lien d'invitation Telegram natif.
- Le processus stocke l'association (username public / ID public / ID privé / titre / empreinte SHA-256 de l’invitation) dans `state/rescue_channels.json`, avec sauvegarde GitHub et fusion sécurisée après chaque exécution. **Jamais de recréation d'un canal déjà enregistré.**
- Chaque nouvelle **fiche de film**, **fiche de série/saisons** et **fiche d'animé** reçoit automatiquement un troisième bouton `🛟 Rejoindre le canal secours` si l'association du canal public existe et est valide. Les boutons de film, des saisons et du dossier de partage restent présents.
- Les éditions ultérieures (archivage des vidéos et canal privé de tendance) conservent aussi le bouton « Secours ».
- Le canal Secours est une solution de communication/réorientation, **pas une copie de tous les médias**. Aucun film ni épisode n'est transféré dans les canaux Secours.

## Workflow
`.github/workflows/cinex-rescue-channels.yml` : passage horaire à la minute 43 (UTC, même heure qu'à Lomé), au maximum **un canal nouveau par passage** avec **60 secondes** après création et après récupération de son invitation. Le groupe d'exclusion `mrx-telegram-personal-account` empêche les passages simultanés avec les autres flux qui utilisent le compte.

**Les passages programmés créent automatiquement un canal Secours au maximum par cycle.** Pour interrompre ces créations : GitHub → Settings → Secrets and variables → Actions → Variables → `CINEX_RESCUE_ENABLED=false`. Le lancement manuel reste en simulation par défaut.

GitHub → Actions → `CineX - Creer et verifier les canaux Secours` → Run workflow → `apply=true` pour une exécution manuelle contrôlée.

Les nouveaux boutons utilisent une invitation retrouvée temporairement via Telegram, puis vérifiée contre son empreinte ; le lien ne figure jamais dans Git. Les boutons seront ajoutés aux futures fiches lorsque le lien aura été retrouvé. L'ajout automatique aux publications historiques n'est pas compris dans cette première intégration.

## Limitations
- Seuls les canaux publics administrés par le compte propriétaire sont éligibles. Aucun compte extérieur et aucun canal source ne sont utilisés.
- Si le compte a déjà enregistré un canal de secours mais ne le retrouve plus, le programme **ne crée pas de doublon** : il signale une erreur.
- Les liens d'invitation doivent rester valides ; l'opérateur devra mettre à jour une invitation révoquée.
- La cadence ralentit les opérations mais ne garantit pas zéro restriction Telegram.
- Le système ne contourne pas les droits de publication ou les restrictions Telegram.

**Sécurité (phase 1) :** les invitations ne sont plus enregistrées en clair dans `state/rescue_channels.json`. Le workflow récupère les URLs auprès de Telegram en mémoire et les place temporairement dans `RUNNER_TEMP`, avec droits `0600`. La rotation des anciennes invitations présentes dans l’historique Git est différée tant que les anciennes fiches ne sont pas remises à jour.
