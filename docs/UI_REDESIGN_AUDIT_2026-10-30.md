# Audit des 20 améliorations UI — Mr XPRONOS
Date de revue : 2026-10-30
Branche : `feat/editorial-navigation-redesign-20261030`
Pull Request : #268

## Statuts et preuves

Légende :
- **Implémenté, vérifié statiquement** : code présent et inspections structurelles réalisées ; test navigateur encore nécessaire.
- **Partiel** : le mécanisme est présent mais l'enrichissement réel ou la preuve d'expérience utilisateur n'est pas encore complet.
- **CI bloquée** : GitHub Actions a enregistré les jobs mais ceux-ci restent `queued`. Ne jamais déclarer ces tests « réussis ».

| N° | Demande | Statut au 30/10 | Contrôle |
|---|---|---|---|
| 1 | Navigation desktop simplifiée | Implémenté, vérifié statiquement | 5 liens prioritaires sur les 11 pages |
| 2 | Rubrique « Plus » | Implémenté, vérifié statiquement | Menu déroulant natif Conseils/Bonus/Contact |
| 3 | Menu mobile organisé par groupes | Implémenté, vérifié statiquement | 3 groupes Football/Découvrir/Informations |
| 4 | Maximum 5 raccourcis mobiles, aucun menu doublon | Implémenté, vérifié statiquement | 5 items, contrôle principal dans la barre inférieure |
| 5 | En-têtes harmonisés | Implémenté, vérifié statiquement | Une navigation commune sur 11 routes |
| 6 | Pieds de page, liens, année et prévention | Implémenté, vérifié statiquement | 3 colonnes thématiques + logo/social/année dynamique |
| 7 | « Analyses & Décryptages » | Implémenté, vérifié statiquement | Blog title, hero, métadonnées SEO |
| 8 | Séparation Infos Foot / Analyses | Implémenté, vérifié statiquement | Navigation et filtre éditorial dédiés |
| 9 | Analyse à la une | Implémenté, vérifié statiquement | `#blog-featured`, article le plus récent |
| 10 | Catégories adaptées aux contenus | Implémenté, vérifié statiquement | 4 filtres maximum, catégories vides cachées |
| 11 | Cartes lisibles sur mobile | Implémenté, vérifié statiquement | CSS, texte/extraits visibles, liens de lecture |
| 12 | 8 sections d'analyse plus instructives | **Partiel** | 8 titres générés pour nouvelles + anciennes fiches ; statistiques sportives manquantes non disponibles |
| 13 | Statistiques vérifiables sans invention | Implémenté avec limite de données | Références conservées ; formes/H2H non affirmées sans preuve |
| 14 | Analyse informative distincte du pronostic | Implémenté, vérifié statiquement | Pro/VIP ≥79 % filtrés, historique sans fausse publication préalable |
| 15 | Recherche par sujet/équipe/compétition | Implémenté, vérifié statiquement | Index article titre, match, ligue, contenu et mots-clés |
| 16 | Tri par date et compétition | Implémenté, vérifié statiquement | Plus récentes, plus anciennes, compétition A–Z |
| 17 | « Afficher plus » | Implémenté, vérifié statiquement | 9 articles supplémentaires par activation |
| 18 | Fil de navigation | Implémenté, vérifié statiquement | Détails analyses et conseils |
| 19 | Analyses et guides similaires | Implémenté, vérifié statiquement | Jusqu'à trois contenus, même ligue prioritaire |
| 20 | Tests navigateur, sécurité, mobile et performance | **Partiel : CI en attente** | Syntaxes JS validées, checks structurels 11/11 ; tests GitHub Actions toujours queued |

## Tests et limites

Les scripts `assets/js/main.js` (import ES mis de côté pour la validation de syntaxe) et `assets/js/menu.js` sont syntaxiquement corrects (compilation V8 sans exécution).
Inspection structurelle : 11/11 pages possèdent la navigation harmonisée, le pied de page harmonisé, trois groupes de liens et l'année dynamique. Les générateurs possèdent les huit titres et des avertissements contre les fausses statistiques et les preuves rétroactives.

Des tests automatiques ont été ajoutés/adaptés :
- `tests/test_site_editorial_redesign.py`
- `scripts/blog_visual_smoke.py`
- `scripts/public_pages_header_smoke.py`
- `scripts/detail_pages_mobile_smoke.py`
- `scripts/mobile_nav_premium_smoke.py`
- `.github/workflows/public-site-safety.yml`
- `.github/workflows/public-pages-header-smoke.yml`

**Attention** : ces tests n'ont pas encore été exécutés avec un résultat de réussite par GitHub Actions. Les exécutions récentes du dépôt, même celles lancées depuis `main`, restent en file d'attente (`queued`). Ne pas fusionner ni annoncer le déploiement de la PR #268 avant les validations nécessaires.

## Limites de données et conditions de complétion

Les anciennes fiches ne contiennent ni séries de forme récente, ni H2H confirmés, ni tirs/corners/possession : ces informations ne peuvent pas être inventées. L'enrichissement sportif réel reste partiel jusqu'à l'arrivée d'une source historique vérifiable. Les URLs des preuves existantes et l'historique public ne sont pas modifiés.

Le site public `gh-pages` conserve sa version actuelle tant que la PR #268 n'est pas fusionnée. Pour valider intégralement : obtenir les résultats des tests, corriger les échecs pertinents, contrôler visuellement 320/390/768/1024 px, fusionner et vérifier le déploiement public et le nettoyage déjà en place.
