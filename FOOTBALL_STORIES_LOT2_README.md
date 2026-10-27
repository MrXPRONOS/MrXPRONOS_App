# Football Stories — lot 2 éditorial

Voir `docs/FOOTBALL_LOT2_EDITORIAL_GUIDE.md` et `docs/FOOTBALL_MEDIA_PROGRESS.md`.

L'ajout est volontairement séparé du générateur existant de coupons. Il produit des
scénarios factuels traçables, pas des vidéos publiables automatiquement à ce stade.

Exécuter les 32 tests :
`python -m unittest discover -s tests -p 'test_football*.py' -v`

Exécuter un exemple éditorial sourcé, sans créer de vidéo :
`python -m football_media_v2.engine --mode story --storypack football_media_v2/editorial_packs/verified_examples.json --editorial-only`

Interprétation des sorties : `editorial_report.json` indique pour chaque phrase
les éléments de preuve documentés. Les trois variantes sont comparées. Les titres
RSS restent des pistes de recherche (jamais des faits prêts à raconter).

**Les médias FIFA ne sont pas réutilisables par défaut** ; le pack contient uniquement
des faits documentés et leurs liens.
