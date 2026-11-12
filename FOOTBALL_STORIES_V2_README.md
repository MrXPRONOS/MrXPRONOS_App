# Mr XPRONOS Football Stories — phase visuelle V3

**État : premier lot terminé au niveau graphique, moteur complet NON prêt à publier.**

Le projet de référence est désormais dans :

- [`AGENTS.md`](AGENTS.md) — consignes permanentes pour les futurs travaux et pour « continue ».
- [`docs/FOOTBALL_MEDIA_ROADMAP.md`](docs/FOOTBALL_MEDIA_ROADMAP.md) — les **36 améliorations** réparties en quatre lots et leurs critères.
- [`docs/FOOTBALL_MEDIA_PROGRESS.md`](docs/FOOTBALL_MEDIA_PROGRESS.md) — état réel, preuves, limites, prochaine action.

## Lot 1 achevé — modifications visuelles 1 à 6

- Retrait de toutes les silhouettes, petits ballons, terrains dessinés et illustrations procédurales de `football_media_v2/visuals.py`.
- Photographie de football au format plein écran, cadrage photographique, dégradés sobres au lieu de cadres noirs encombrants.
- Palette sobre et signature typographique Mr XPRONOS. **Pas de faux logo** en remplacement du logo officiel, non encore fourni.
- Règles sur les marges et la hiérarchie des textes ; un titre trop long déclenche une erreur plutôt qu'une troncature silencieuse.
- **9 compositions distinctes** prévues selon le rôle narratif : couverture, plan d'ambiance, duel, score, statistique, insight, révélation, preuve et conclusion (et une dixième pour classements).
- Production réelle refusée sans **trois photos différentes au minimum**, publiables selon leurs licences. Les images génériques sont signalées comme photos d'illustration.

## Sécurité

- Le fichier `football_media_v2/assets/demo_synthetic_football.jpg.b64` est un **asset IA fictif uniquement pour prévisualiser** la direction artistique, jamais une image de vrai match.
- Le mode `--demo` décode l'asset localement si nécessaire et marque la vidéo « DÉMONSTRATION FICTIVE — NON PUBLIABLE ».
- Aucun changement aux coupons, au script de leur création ni à leur workflow GitHub Actions.
- La publication n'est pas activée ; l'absence de vraie voix, les visuels fictifs ou un contrôle qualité échoué bloquent le lancement sur les réseaux.

## Tester

```bash
pip install -r football_media_v2/requirements.txt
python -m unittest discover -s tests -p 'test_football*.py' -v
FOOTBALL_DISABLE_TTS=1 python -m football_media_v2.engine --mode match --demo
```

Nécessite Python 3.11+, ffmpeg, ffprobe et `fonts-dejavu-core`. Le fichier JPEG est automatiquement reconstruit à partir du texte encodé dans le mode test. Sur GitHub, lancer le workflow **Mr XPRONOS - Football Stories V2** sur cette branche en choisissant `demo=true`, s'il est accessible via l'interface Actions. Les exécutions programmées ne sont pas activées par la seule existence de la branche.

## Diagnostic de spectateur

Un plan isolé apparaît désormais plus professionnel ; les compositions sont lisibles et centrées sur le football. Mais **la démonstration actuelle n'est toujours pas une vidéo captivante** : même photo synthétique répétée, match fictif et accroches trop génériques. Ce défaut relève notamment du **lot 2 (sujets et storytelling, points 7–17)**, puis du lot 3 (sélection de médias réels, montage, voix).

À la prochaine commande « continue », vérifier le journal d'avancement puis **commencer le lot 2 par l'amélioration n°7**, sans effacer les contrôles acquis au lot 1. Ne pas présenter le succès des tests comme une validation créative finale.