# Audit de livraison — Dixon-Coles indépendant — 5 novembre 2026

## État de l'implémentation

| Fonction | Implémenté | Vérifié |
|---|---|---|
| Nouveau moteur Dixon-Coles (α, β, γ, ρ) | Oui | Tests unitaires sur τ, probabilités et normalisation |
| Vraisemblance pondérée et optimisation numérique | Oui | Entraînement et convergence sur championnat fictif |
| Garde-fous (positivité, équipes, historique, temps) | Oui | Tests de cas limites et de fuite de données futures |
| Source CSV et sources d'identifiants séparées | Oui | Tests d'import et de validation |
| API football-data.org v4 | Oui | Test de réponse simulée et schéma officiel ; pas de clé utilisateur réelle |
| Import de matchs à venir et sélection manuelle | Oui | Tests HTTP et interface web |
| Prédiction d'un seul match futur | Oui | Tests moteur, API, CLI, navigateur |
| Calcul Top 5 et 1N2 | Oui | Comparaison numérique des probabilités à la somme de la matrice |
| Historique SQLite et résultat final | Oui | Tests persistance et enregistrement manuel |
| Backtest chronologique Top 1/Top 3/log-loss | Oui | Tests et démonstration sur matchs synthétiques |
| Interface web responsive | Oui | Essai Chromium sans erreur JavaScript (API relayée localement) |
| Outils CLI | Oui | Tests CLI et démo |
| Suite de tests automatisés | Oui | `python -m pytest -q` |
| Github Actions pour futur dépôt autonome | Oui | Fichier YAML présent ; non exécuté sur GitHub |

## Contrôles effectivement exécutés

- Fonctions `τ(0,0)`, `τ(0,1)`, `τ(1,0)`, `τ(1,1)` comparées aux équations originales.
- Une grille jusqu'à 18 buts conserve une masse totale ~1 et les marges Poisson.
- Les probabilités de victoire, nul et défaite sont cohérentes avec la grille.
- La moyenne des forces offensives estimées vaut exactement ~1.
- Les matchs terminés datés dans le futur ne sont pas utilisés pour entraîner le modèle.
- Aucune rencontre du jour testé n'entre dans l'historique du backtest.
- Tests des erreurs de CSV, du refus d'API sans jeton, des IDs stables et du refus des groupes d'équipes déconnectés.
- HTTP + page et scripts statiques disponibles en test local.
- Chromium : chargement, démo, sélection du match, prévision, backtest et absence d'erreurs JavaScript. La navigation directe vers localhost était bloquée par le navigateur d'audit ; les requêtes ont été relayées à la véritable API locale. Cela ne valide pas un déploiement public.

## Ce qui n'a PAS pu être validé à partir d'ici

1. Une synchronisation live avec **la véritable clé privée football-data.org du propriétaire**. La connexion et ses droits d'accès dépendent d'un jeton non fourni. L'adaptateur est implémenté et testé avec une réponse factice aux mêmes champs.
2. La qualité prédictive sur des **matchs réels non vus** : il faut importer plusieurs saisons réelles d'une compétition puis lancer et interpréter un backtest externe suffisamment grand.
3. Une publication sur Internet ou un nouveau dépôt GitHub : volontairement **non exécutée** pour respecter l'indépendance exigée et ne pas toucher aux anciens repos.
4. Une exploitation publique multi-utilisateurs : cette version est une application locale sans authentification ; l'exposer en ligne exigerait un contrôle d'accès et une revue de sécurité.

**Conclusion de l'audit :** toutes les fonctions prévues pour le logiciel autonome et local sont livrées et testées sans clé réelle ; validation live, performance sur données réelles et éventuel déploiement restent conditionnels. Aucun chiffre de réussite réelle n'est revendiqué.


## Intégration monorepo

Un workflow CI distinct est placé dans `.github/workflows/dixon-coles-independent-tests.yml` ; il exécute seulement les tests de `dixon-coles/` lorsqu’un fichier de ce sous-projet change. Aucun système historique n’est remplacé.
