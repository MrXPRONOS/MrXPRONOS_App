# Mr XPRONOS — Générateur vidéo (version studio)

## Fonctionnement

Le moteur indépendant `dcscore.video_render` transforme **uniquement** les entrées vidéo
produites par `dcscore.daily` en un MP4 vertical H.264 + AAC, avec textes en français,
cartes de scores, animations et une bande-son **entièrement synthétisée par le code**.
Les logos des clubs ne sont pas téléchargés ou utilisés : les monogrammes sont des graphismes originaux.

**Le rendu n'est pas une publication sociale.** Les données météo, résultats, équipes,
probabilités et dates doivent provenir du JSON du pipeline, sans scores fabriqués pour compléter la liste.

### Mode production (strict)

La commande refuse : `ready_for_video != true`, état différent de `READY`,
moins de **10 matchs**, date non égale à aujourd'hui ou demain (UTC/Lomé),
rapport vieux de plus de 4 heures, coups d'envoi déjà passés, scores invalides.

```bash
python -m pip install -e '.[video]'
# Installer FFmpeg : ffmpeg et ffprobe doivent être accessibles depuis PATH.
python -m dcscore.video_render \
  --payload results/daily/AAAA-MM-JJ/video_payload.json \
  --output results/daily/AAAA-MM-JJ/top10.mp4
```

Le workflow `dixon-coles-daily-top10.yml` rend automatiquement le MP4 **seulement si**
`ready_for_video=true`. Le MP4 est conservé comme artefact GitHub, sans upload vers les réseaux.
Le pipeline de publication TikTok/Meta/YouTube n'est pas activé.

### Prévisualisation du style (données entièrement fictives)

```bash
python -m dcscore.video_render \
  --payload video_examples/demo_payload.json \
  --output preview-demo.mp4 \
  --preview --allow-partial-preview
```

En mode preview, un bandeau **DÉMO · MODÈLES NON CALIBRÉS** est incrusté ; aucune
vidéo de production n'est créée. L'exemple fourni comporte volontairement 3 équipes et
3 scores inventés : il sert à tester le graphisme, pas la performance statistique.

### Caractéristiques de réalisation

- 9:16, 720 × 1 280, 25 fps (premier profil optimisé pour rendu GitHub Actions).
- Animation d'introduction (2,7 s), 3,05 s par rencontre, outro (2,75 s).
- Des scores qui apparaissent puis des probabilités affichées en décalé.
- Texte principal : « score le plus probable », jamais « score sûr ».
- Top 3 et pourcentage, rappel 18+, aucun conseil de mise.
- Musique originale générée localement, sans échantillon tiers.
- Montages sans image des joueurs et sans logo licencié, ce qui permet de tester
  la création avec uniquement Python, Pillow et FFmpeg.
- Personnalisation possible via les couleurs et la police du module.

### Conseils pour la future publication automatique

D'abord collecter des statistiques de visionnage : taux de rétention à 3 secondes,
5 secondes, complétion et relecture. Une évaluation visuelle humaine ne peut
pas démontrer qu'un public réel regardera la vidéo jusqu'à la fin.
Pour l'activation de publication, il faudra ajouter un contrôle des droits des
sources, les autorisations des plateformes, une empreinte anti-doublon
(date et contenu), une politique de correction des rencontres reportées,
un suivi des erreurs, et un mode de validation avant diffusion.

## Dépendances

Python 3.10+, Pillow 10+, numpy 1.26+ et FFmpeg avec libx264 et AAC.
La police Inter est détectée localement quand présente, sinon DejaVu Sans.
Ne jamais commiter de fichiers de polices propriétaires dans GitHub.

Pour l'export production, le workflow ajoute `--fullhd` et génère un
MP4 **1080 × 1920** par suréchantillonnage Lanczos du moteur de motion graphics
720 × 1280. Les éléments ne sont pas recréés en 1080 natif : ceci est un profil
d'export, pas une affirmation de résolution native. La prévisualisation rapide reste
possible en 720 × 1280 sans ce drapeau.
