# Mr XPRONOS — Vidéo quotidienne minimaliste (V2)

## Livrable

Une vidéo verticale de **10 rencontres et 10 scores**, un match par écran. Le seul contenu visuel principal de chaque écran est : **écusson domicile · écusson extérieur · noms des clubs · score calculé**. Pas de probabilité, de statistiques secondaires, de cotes ni de longues explications.

- Intro 1,05 s : « 10 MATCHS / 10 SCORES EXACTS ».
- 10 matchs × 1,95 s = 19,50 s ; écussons glissant doucement depuis les côtés, puis score qui apparaît ; progression discrète des dix rencontres.
- Outro 1,35 s : « TU EN VALIDES COMBIEN ? ».
- Durée totale **21,90 s**, son de synthèse original (sans musique sous droits).
- Format 9:16, MP4 H.264/AAC, jusqu'à **1080 × 1920**.

## Source et logos : aucune invention

La sélection quotidienne continue de classer le prestige des championnats, les affiches reconnues, les finales et derbies, **puis vérifie la disponibilité de l'historique sportif et de deux écussons réels** avant de marquer le rapport `READY`. Les champs `home_logo_url` et `away_logo_url` proviennent, lorsqu'ils existent, des objets `homeTeam.crest` et `awayTeam.crest` fournis par football-data.org. Les logos sont des marques appartenant aux clubs. L'utilisateur doit s'assurer que leur utilisation publique respecte les droits des titulaires et les conditions des fournisseurs.

Le rendu de production refuse :

- Moins de **10** scores calculés, une source non vérifiée, un terrain de finale incertain, une rencontre déjà commencée, ou un rapport expiré ;
- Des écussons absents, non décodables, trop lourds ou provenant d'URL non autorisées ;
- Les chemins locaux traversant des dossiers parents (`..`).

URLs de logo permises uniquement depuis `crests.football-data.org` et `upload.wikimedia.org`, en HTTPS et sans redirection vers un domaine tiers. Conversion SVG seulement lorsque nécessaire avec `cairosvg`, en interdisant les références externes et les scripts. Aucune image synthétique de club réel n'est utilisée en production. L'absence de droits ou de licence peut aussi interdire la publication, même lorsque le logo est techniquement accessible.

Le mode **--preview** peut montrer des logos fictifs générés automatiquement, portant obligatoirement la mention « DÉMO · MATCHS ET SCORES FICTIFS ». Le fichier `video_examples/demo_real_club_logos_top10.json` montre 10 affiches fictives de clubs existants, avec URLs d'écussons officiels ; ses scores sont des **exemples inventés**, absolument pas des pronostics ou le calendrier réel.

## Déclenchement GitHub Actions

Chaque soir à **21 h UTC (21 h à Lomé)**, le workflow `.github/workflows/dixon-coles-daily-top10.yml` :

1. Recueille les données et sélectionne les 10 meilleures rencontres éligibles.
2. Calcule les 10 scores avec le moteur Dixon-Coles, en gardant chaque ligue séparée.
3. Prépare `results/daily/YYYY-MM-DD/video_payload.json` comprenant les logos.
4. Génère `top10.mp4` uniquement si `status == "READY"`, `ready_for_video` est vrai, les matchs sont futurs et les dix logos par côté sont valides.
5. Dépose les fichiers dans l'artefact GitHub Actions. **Il n'y a pas encore de publication automatisée vers les réseaux sociaux.**

En cas de moins de dix matchs éligibles, aucun MP4 de production n'est inventé ni publié. Des sources/clefs supplémentaires sont nécessaires pour garantir une bonne couverture la plupart des jours.

## Prévisualisation sur son PC

Depuis `dixon-coles/` :

```bash
python -m pip install -e '.[test,video]'
python -m dcscore.video_render \
  --payload video_examples/demo_fictional_top10.json \
  --output demo_top10.mp4 --preview --fullhd
```

`ffmpeg` et `ffprobe` doivent être installés. Pour tester les logos de clubs réels dans des **affiches fictives** :

```bash
python -m dcscore.video_render \
  --payload video_examples/demo_real_club_logos_top10.json \
  --output demo_logos_reels.mp4 --preview --fullhd
```

L'accès réseau au fournisseur d'écussons est nécessaire ; le mode démo affichera une vignette typographique de remplacement et signalera le nombre de logos non téléchargés. Le mode production, lui, refusera ces remplacements.

## Non encore implémenté

La publication directe sur TikTok, YouTube Shorts, Facebook Reels et Instagram Reels n'est pas activée. Il reste à vérifier les permissions de l'API de chaque plateforme, les droits sur les écussons, puis tester les uploads et les mécanismes anti-doublon avant d'activer une diffusion sans validation humaine.
