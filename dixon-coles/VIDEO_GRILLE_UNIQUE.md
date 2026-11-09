# Mr XPRONOS — vidéo quotidienne en un seul écran

Format officiel : **les 10 rencontres à l'écran du premier au dernier photogramme**.
Aucune introduction, aucun écran final ni changement de carte. Durée 15,22 secondes,
2 colonnes × 5 rangées, logos de clubs, noms, score exact modal prédit,
marque discrète et date du jour ciblé. Les scores se révèlent les uns après
les autres (surbrillance brève), **sans horloge ni fausses actions de match**.

Le format ne montre ni probabilité, ni pari, ni cote, ni championnat. Le fichier
JSON conserve ces informations pour analyse interne, pas pour le rendu.

## Lancer

```bash
cd dixon-coles
python -m pip install -e '.[test,video]'
python -m dcscore.video_grid \
  --payload video_examples/demo_real_club_logos_top10.json \
  --output results/studio_demo/preview_grille_10_scores.mp4 \
  --preview --fullhd
```

La démonstration utilise **de vrais logos de clubs, mais des affiches et
scores entièrement fictifs**, d'où la mention DÉMO persistante. Elle ne doit
pas être publiée comme une liste de pronostics réels.

Pour la production, le workflow quotidien appelle désormais
`python -m dcscore.video_grid --payload results/daily/<date>/video_payload.json
--output results/daily/<date>/top10.mp4 --fullhd` uniquement si le fichier
`video_payload.json` est `READY`, contient exactement **10 matchs à venir**, et
les 20 écussons sont disponibles. Un nombre insuffisant de matchs, un résultat
inventé, une date obsolète ou un logo manquant bloque le rendu de production.

Le titre utilise `date_local_africa_lome` ; un changement de date est
automatique. Les logos sont récupérés uniquement via les fournisseurs
allowlistés, avec cache de téléchargement et validation de format/poids.
La publication sur les plateformes sociales est volontairement désactivée.

Droits des logos : vérifier la possibilité de diffusion publique et commerciale
et les marques des clubs avant publication. Les cartes de démonstration ne sont
pas des pronostics de rencontres vérifiées.

Tests : `python -m pytest -q tests/test_video_grid.py`.
