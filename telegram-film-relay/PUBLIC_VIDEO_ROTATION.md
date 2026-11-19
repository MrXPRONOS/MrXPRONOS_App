# Ciné X — Archivage des films du canal principal

## Objectif
Conserver les vidéos des **10 films récents** avec affiche associée dans `@CineXFilms_vf`. Les films plus anciens doivent demeurer visibles via **leur affiche, leur description et les boutons vers la vidéothèque, le canal Secours et le dossier Telegram**. Les autres vidéos ne doivent être supprimées que si leur identité est vérifiée.

## Rattrapage des anciens films
- Le système lit au maximum 4 000 messages publics et trouve chaque couple vidéo + affiche **antérieure** par titre concordant, même lorsque des dizaines ou centaines de messages les séparent (jusqu'à 1 200 identifiants).
- Les associations éloignées exigent une concordance particulièrement forte. Aucune vidéo ambiguë, sans affiche ou sans titre ne sera supprimée par simple proximité.
- Les dix couples film/affiche les plus récents sont protégés et revérifiés avant chaque retrait. Les messages promotionnels ne comptent pas comme films.
- Les films *John Wick* restants sont **réservés au traitement manuel**, selon la consigne du propriétaire.
- Le rattrapage commence par le film **le plus ancien** parmi les candidats sûrs, pas par les candidats les plus récents.
- Si la vidéo est déjà présente dans la vidéothèque avec son affiche antérieure correspondante, cette paire est réutilisée. Sinon, le programme publie **d'abord une photo avec sa description**, vérifie sa présence, puis **la vidéo**, vérifie le document et leur ordre.
- Après vérification de la vidéothèque, l'affiche originale du canal principal est modifiée pour avoir les boutons 🎬 Voir le film, 🛟 Rejoindre le canal secours et 📁 Rejoindre le dossier. Le retrait de l'ancienne vidéo ne se produit **qu'après validation de ces liens**, et nouvelle vérification des dix derniers films.
- Les vidéos sans association certaine restent dans le canal et sont signalées comme « non associées ». Le workflow ne prétend pas avoir nettoyé intégralement ce cas.

## Horaires et quotas
Workflow : `.github/workflows/cinex-public-video-rotation.yml`.

Deux passages par jour à **00:00 et 12:00 UTC**, soit 00:00 et 12:00 à Lomé. Au maximum **10 films anciens par passage**, pour traiter au moins 5 films lorsqu'ils sont disponibles et vérifiables ; s'il y en a moins, le système traite ceux disponibles puis s'arrête. Le lancement manuel `apply=true` utilise également ce plafond. Les pauses et les limites Telegram sont respectées.

## Activation et sécurité
Le workflow requiert :
- `CINEX_ARCHIVE_ENABLED=true`
- `CINEX_ARCHIVE_DELETE_APPROVED=true`
- `CINEX_RIGHTS_VERIFIED=true`

La session propriétaire, le bot et les canaux doivent avoir les permissions Telegram effectivement requises. Les invitations Secours sont récupérées temporairement et vérifiées ; aucune invitation sensible n'est inscrite en clair dans Git. La suppression n'est jamais tentée si l'affiche ou le média privé ne sont pas fiables.

Pour lancer : GitHub Actions → « CineX - Rotation biquotidienne des 10 films » → Run workflow → `apply=true`.

## Limite importante
Le script s'arrête devant un titre ambigu, une affiche absente, une vidéo protégée, un canal sans autorisation ou un problème Telegram. **Il ne peut donc pas promettre exactement dix vidéos tant que l'historique contient des documents mal identifiés.** Les logs mentionnent le nombre de vidéos sans association pour faciliter une correction ciblée, plutôt que de risquer de supprimer un mauvais film.

Utiliser uniquement sur des médias dont la redistribution est autorisée.
