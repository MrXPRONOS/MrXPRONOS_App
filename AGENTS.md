# Mr XPRONOS — règles permanentes pour les agents et les contributeurs

> Document de référence du dépôt. **Lire ce fichier puis `docs/FOOTBALL_MEDIA_ROADMAP.md` et `docs/FOOTBALL_MEDIA_PROGRESS.md` avant toute modification du moteur Football Stories.**

## Objectif produit non négociable

Créer un média football vidéo que l'on a **réellement envie de regarder**, et pas simplement des fichiers MP4 générés automatiquement. Privilégier les images de football pertinentes, l'émotion, les détails concrets, une mise en scène cinématographique sobre et une narration vérifiée.

## Flux de travail et commande « continue »

1. Ouvrir la feuille de route et le journal d'avancement de la branche de développement active. Vérifier **le vrai état GitHub, les tests et les livrables**, pas seulement la dernière réponse de l'assistant.
2. Ne travailler que sur **le lot actif**. Les lots sont séquentiels : 1 visuel (points 1–6), 2 éditorial (7–17), 3 médias/montage/voix (18–32), 4 qualité/amélioration (33–36).
3. Ne déclarer un lot « terminé » que lorsque **tous ses points** ont une implémentation inspectable, des tests et un rendu de validation. Documenter les défauts résiduels.
4. À la demande « continue », reprendre le lot actif tant qu'il n'est pas terminé. Passer au lot suivant seulement lorsqu'il est vraiment achevé, avec ses critères validés. Ne pas sauter de point.
5. Chaque fin de lot exige un **diagnostic de spectateur** : est-ce que je m'arrêterais dans les deux premières secondes ? Est-ce que je voudrais voir la suite ? Quels défauts visibles restent ? Ne pas confondre réussite technique et attractivité.
6. La publication automatique est **désactivée** pendant les travaux. Éviter tout changement non demandé dans les coupons, scripts existants et workflows associés.
7. Développer sur une branche isolée, demander une revue avant fusion dans `main`. Ne jamais activer une mise en ligne juste pour faire passer un test.

## Règles visuelles permanentes

- **Jamais** de joueurs, ballons ou terrains grossiers dessinés en Python ; jamais de diaporamas uniformes avec gros rectangles noirs et quatre blocs de texte.
- Photo/clip sportif pertinent et plein écran, dont la licence commerciale et les conditions sont vérifiées. En leur absence : bloquer, ne pas fabriquer de faux faits de match ni présenter un visuel IA comme une véritable action.
- Typographie lisible sur téléphone, petit branding Mr XPRONOS, identité limitée et cohérente, variété authentique des cadrages et compositions. Les visuels libres peuvent être *illustratifs* : ne jamais prétendre qu'ils montrent le match raconté.
- Respecter les droits, les attributions, les identités de personnes et l'actualité des données. Démonstrations fictives clairement marquées et jamais publiées.
- Protéger la sécurité : secrets uniquement dans GitHub Secrets, pas dans les logs/artefacts. API officielles, aucune promesse de publication sans validation réelle.

## Indicateurs de sortie

- Les tests automatisés assurent la conformité *technique* ; les notes créatives restent des jugements humains documentés.
- Se reporter au fichier `docs/FOOTBALL_MEDIA_PROGRESS.md` pour le lot actif, les preuves, les limites, la prochaine tâche et les résultats de la revue spectateur.
