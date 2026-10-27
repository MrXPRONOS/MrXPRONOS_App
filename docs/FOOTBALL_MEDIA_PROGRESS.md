# Mr XPRONOS — état d'avancement et reprise (« continue »)

> **Branche : `feature/football-stories-v2` ; branche `main` et coupons inchangés.**

## Lot actif : lot 1 — identité et qualité visuelle (points 1–6)

État : **lot 1 TERMINÉ au niveau visuel / non publiable**. Vérifications réalisées localement le 27 octobre 2026 : 14/14 tests OK, neuf compositions générées, aperçu H.264/AAC vertical produit, contrôle vidéo bloquant la publication démonstration. **Le verdict spectateur de la vidéo complète reste négatif** : narration, voix, sélection des sujets et répétitions appartiennent aux lots 2 et 3. Ne pas annoncer une vidéo prête à diffuser.

| N° | Amélioration | Preuve attendue | État |
|---|---|---|---|
| 1 | Suppression dessins amateurs | Aucun dessin de joueur / ballon / terrain dans `visuals.py` | Implémenté |
| 2 | Photo plein écran obligatoire | `MissingLicensedMedia` sans image ; image réelle ou fixture test couvrant le cadre | Implémenté |
| 3 | Pas de gros panneaux | Dégradé de contraste, aucune large carte noire sur la photographie | Implémenté |
| 4 | Charte premium | Constantes design, marque typographique, test de sortie | Implémenté ; logo officiel non fourni |
| 5 | Hiérarchie sans rognage | 1 grand titre, 1 info secondaire ; long titre => erreur explicite | Implémenté |
| 6 | Vrais templates et diversité | 6+ layouts, au moins 3 photos différentes pour une production réelle | Implémenté |

### Vérifications exigées

- [x] Suite de tests nouveaux et anciens : **14/14 OK** (exécution locale).
- [ ] Planche de comparaison sur 9 plans vue par l'assistant.
- [x] Vidéo de démonstration 22,46 s, **720 × 1280**, vidéo H.264 + audio AAC inspectés ; démo fictive explicitement non publiable.
- [x] Modifications déposées sur la branche `feature/football-stories-v2` ; workflow modifié. **Exécution CI GitHub pas encore démontrée** (workflow absent de `main` tant que la PR n’est pas fusionnée).
- [x] Verdict spectateur : une image isolée est plus professionnelle, mais **je ne regarderais pas encore le Short entier** (accroche générique, match inventé de démonstration, photo répétée et absence de voix neuronale en test). Aucun score arbitraire de rétention publié.

### Limites connues

- Une image synthétique de démonstration ne représente **aucun vrai match** : toujours filigranée, exclue de la production réelle.
- Les données et voix de la V2 restent volontairement inchangées jusqu'aux lots éditorial et audiovisuel.
- Le logo officiel n'a pas été localisé ; identité typographique temporaire (pas de logo inventé).
- Les photos Wikimedia génériques doivent rester marquées « illustration », pas images de la rencontre en question.
- Un lot « terminé » ne signifie pas « prêt à publier ». La publication demeure désactivée.

### Prochaine action à la commande « continue »

Le lot 1 est clos **uniquement pour les éléments visuels implémentés et les tests locaux**. À « continue », commencer **le lot 2, amélioration n°7 : découverte de sujets**, puis les points 8–17, un par un. Si une régression du lot 1 apparaît, la corriger avant de poursuivre. Ne pas fusionner automatiquement dans `main`.