# Ciné X — Synchronisation automatique des profils Telegram

## Canaux privés « Secours »
Chaque exécution du workflow existant `CineX - Creer et verifier les canaux Secours` traite les canaux qu'il retrouve ou vient de créer :

- lit la **description exacte** du canal principal avec `channels.GetFullChannelRequest`, sans ajouter de texte ni modifier les retours à la ligne ;
- lit son **avatar Telegram** avec `download_profile_photo` et applique la copie carrée au canal Secours avec `channels.EditPhotoRequest` ;
- vérifie la description après écriture ; n'écrit aucun média dans GitHub ;
- mémorise l'identifiant de la photo source et l'empreinte de la description dans `state/rescue_channels.json`, pour éviter les transferts d'avatar répétitifs ;
- si un administrateur change l'avatar ou la description du canal public, synchronise le changement lors du prochain passage ;
- ne change ni la confidentialité privée du canal Secours, ni son nom qui reste `<nom du canal principal> Secours`.

Si la photo d'origine est absente ou impossible à obtenir, aucune image arbitraire n'est inventée. Une erreur de profil est signalée dans le journal et peut être reprise lors du passage suivant.

## Canaux privés dédiés aux tendances
Chaque traitement d'un titre tendance, seulement après une correspondance vérifiée entre la tendance et les publications officielles :

- prend la photo de l'**affiche Telegram du film**, ou de l'affiche de la série / de l'animé stockée dans la vidéothèque Ciné X ;
- applique cette affiche comme **photo de profil** du canal privé dédié ;
- prend la **description / synopsis de Ciné Radar**, ou le synopsis indiqué sur la fiche existante. À défaut de synopsis, utilise une description neutre de disponibilité (sans inventer l'histoire) ;
- limite la description à la longueur compatible avec Telegram et vérifie la modification ;
- conserve le mécanisme actuel de création de canal, de publication des saisons/épisodes, d'épingles et de boutons.

Les nouveaux canaux et les anciens canaux de tendance réévalués bénéficient de la synchronisation. Les images de profil ne sont pas téléchargées vers Cloudflare/GitHub, seulement transférées par la session Telegram propriétaire. Entre deux opérations de profil Telegram, une pause est conservée (45 secondes pour Secours, 30 secondes pour les tendances).

## Validation
```bash
cd telegram-film-relay
python -m unittest discover -s tests -p test_channel_profiles.py -v
python -m unittest discover -s tests -v
```

Les processus automatisés restent soumis aux mêmes protections d'autorisation et aux mêmes variables d'activation que les workflows existants. Aucun droit d'auteur n'est accordé par la simple disponibilité d'une image ou d'une vidéo sur Telegram.
