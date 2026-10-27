# Mr XPRONOS — état d'avancement et reprise (« continue »)

> **Branche : `feature/football-stories-v2` ; branche `main` et coupons inchangés.**

## Lot actif : lot 1 — identité et qualité visuelle (points 1–6)

État : **implémenté dans le code de la branche de travail, validation nécessaire avant clôture**. Vérifier tests et rendu et compléter ci-dessous avant d'annoncer « terminé ». Lot 2 non entamé.

| N° | Amélioration | Preuve attendue | État |
|---|---|---|---|
| 1 | Suppression dessins amateurs | Aucun dessin de joueur / ballon / terrain dans `visuals.py` | Implémenté |
| 2 | Photo plein écran obligatoire | `MissingLicensedMedia` sans image ; image réelle ou fixture test couvrant le cadre | Implémenté |
| 3 | Pas de gros panneaux | Dégradé de contraste, aucune large carte noire sur la photographie | Implémenté |
| 4 | Charte premium | Constantes design, marque typographique, test de sortie | Implémenté ; logo officiel non fourni |
| 5 | Hiérarchie sans rognage | 1 grand titre, 1 info secondaire ; long titre => erreur explicite | Implémenté |
| 6 | Vrais templates et diversité | 6+ layouts, au moins 3 photos différentes pour une production réelle | Implémenté |

### Vérifications exigées

- [ ] Suite de tests nouveaux et anciens : 0 échec.
- [ ] Planche de comparaison sur 9 plans vue par l'assistant.
- [ ] Vidéo de démonstration produite et inspectée, avec ses limites documentées.
- [ ] Vérification sur GitHub du code publié et de la disponibilité du workflow.
- [ ] Verdict de spectateur rapporté honnêtement ; pas de note 8/10 sur la vidéo complète avant le lot 3.

### Limites connues

- Une image synthétique de démonstration ne représente **aucun vrai match** : toujours filigranée, exclue de la production réelle.
- Les données et voix de la V2 restent volontairement inchangées jusqu'aux lots éditorial et audiovisuel.
- Le logo officiel n'a pas été localisé ; identité typographique temporaire (pas de logo inventé).
- Les photos Wikimedia génériques doivent rester marquées « illustration », pas images de la rencontre en question.
- Un lot « terminé » ne signifie pas « prêt à publier ». La publication demeure désactivée.

### Prochaine action à la commande « continue »

Consulter les coches et les tests GitHub ci-dessus. Si l'une échoue : **terminer le lot 1**. Sinon, après diagnostic visuel et acceptation des limites explicitement documentées, marquer le lot 1 terminé et **commencer le lot 2 point 7**, sans sauter de point. Ne jamais présumer qu'une PR est fusionnée.
