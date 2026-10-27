# Mr XPRONOS — Football Stories V2

## Ce qui change après l'évaluation de la démo V1

Cette V2 ne se contente plus de quatre diapositives silencieuses. Elle comporte :

- **9 à 10 plans courts** par histoire, avec animations de caméra, visuels football originaux (stade, terrain, ballon, joueur **symbolique**), titres cinétiques et questions pour inciter à réagir.
- **Angle éditorial réel** : match qui finit avec beaucoup de buts, écart serré, classement factuel de buteurs issu de l'API, ou compilation de véritables clips autorisés.
- **Voix française neuronale** via `edge-tts` sans clé payante (service externe susceptible de changer ou tomber en panne) et **bande-son originale** synthétisée en Python, sans musique protégée. L'absence de voix **bloque la publication**.
- **Contrôle éditorial + technique** : refus des vidéos démo, des sources non vérifiées, des clips non autorisés, des vidéos sans vraie voix ou trop courtes/longues, des fichiers sans piste audio ou pas au format 9:16.
- **Mémoire séparée** sur branche `football-media-v2-state`, restaurée avant création et sauvegardée uniquement après la publication activée et réussie.
- **Aucune modification** apportée au générateur de coupons ni au workflow `.github/workflows/create-video.yml`.

## Démarrer sur GitHub

1. Ajouter `football_media_v2/`, `tests/test_football_v2.py` et `.github/workflows/football-media-v2.yml` à la racine du dépôt.
2. Fournir le secret GitHub `FOOTBALL_DATA_TOKEN` depuis [football-data.org](https://www.football-data.org/). Le plan gratuit peut limiter les championnats et l'accès au classement des buteurs : le moteur retombe sur une analyse de score **vérifié** si les buteurs ne sont pas disponibles.
3. Ouvrir **GitHub → Actions → Mr XPRONOS - Football Stories V2 → Run workflow** et choisir `demo=true`, `mode=match` (par défaut). La démo montre **un score fictif, clairement marqué** et n'est jamais publiée.
4. Télécharger les fichiers MP4 / PNG de l'artifact.
5. Relancer `demo=false` quand le rendu éditorial est satisfaisant. Vérifier le fichier `productions.json` et `quality.gates`. La publication reste **désactivée**.
6. Après vérification du contenu réel, ajouter les secrets officiels `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` si absents, et définir `FOOTBALL_NETWORKS=telegram,youtube` (ou seulement un des deux).
7. Pour activer, créer **GitHub Actions Variables** `FOOTBALL_MEDIA_V2_PUBLISH=true`. `FOOTBALL_YOUTUBE_PRIVACY=private` par défaut : ne passer à `public` qu'après vérifications. Une exécution programmée sans données vérifiables ne produit rien.

Les cron sont à **12 h 13 UTC** et **19 h 17 UTC mercredi/samedi**, fuseau de Lomé. GitHub peut exécuter avec retard. Les cron ne démarrent automatiquement qu'après présence du workflow sur `main`.

## Tests localement

```bash
pip install -r football_media_v2/requirements.txt
python -m unittest discover -s tests -p 'test_football_v2.py' -v
FOOTBALL_DISABLE_TTS=1 python -m football_media_v2.engine --mode match --demo
```

Requiert `ffmpeg`, `ffprobe`, polices `DejaVu Sans`. Le test local sans internet ne possède pas de voix neuronale : **prévisualisation seulement, non publiable**.

## Formats et limites

- `--mode match` : histoire construite à partir du **score final uniquement** ; ne prétend pas connaître buteurs, chronologie, xG ou actions.
- `--mode scorers` : Top 5 du championnat sélectionné (`FOOTBALL_COMPETITION=PL`, etc.), seulement si l'API le renvoie. Sinon fallback match validé.
- `--mode highlights` : au moins deux **fichiers et preuves d'autorisation** dans `licensed_clips/manifest.json` et une vérification humaine explicite. L'algorithme ne télécharge aucun match sous droit sans permission.
- `--mode auto` : classements certains jours, analyses les autres, repli sur données disponibles.

Les compositions ne simulent pas des buts réels et ne prétendent pas être des images des rencontres ; les visuels stylisés sont entièrement produits par le programme. Pour publier de **vrais buts de grands championnats**, il faudra des droits média et les clips correspondants. Les autorisations commerciales doivent être vérifiées au-delà d'un simple registre déclaratif.

**Diffusion actuellement intégrée** : Telegram, YouTube uniquement. Pas de fausse affirmation sur Facebook/Instagram/TikTok : connecteurs futurs à réutiliser depuis les workflows du dépôt après vérification des permissions. Aucun raccourci pour contourner les quotas/audits des plateformes.

## Sécurité de déploiement

Ce module est installé via une branche/PR dédiée. La modification de `main` reste sous contrôle. Les secrets n'apparaissent jamais dans les artefacts. La publication ne peut démarrer qu'en ajoutant une variable explicite ; la qualité audio reste un prérequis.
