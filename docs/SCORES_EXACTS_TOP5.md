# Onglet Scores exacts — Mr XPRONOS

**Branche** : `feature/onglet-scores-exacts-20261103`, créée à partir de `main`, sans fusion automatique. 
**Page** : `scores-exacts.html` (desktop/mobile). **Flux** : `scores-exacts.json`.
**Statut** : le prévisionniste prospectif natif V3, le connecteur BSD, le publisher Top5 et le workflow GitHub Actions sont codés sur cette branche. Ils ne seront actifs sur le site public qu'après validation d'un vrai dry-run, fusion de la PR #279 et premier déploiement. Le flux initial reste volontairement `unavailable` : aucun match inventé.

## Méthode retenue

Pour chaque match à venir, le même modèle `machine_learning_v3_hybrid` calcule **avant le coup d'envoi** une matrice de probabilités normalisée 11 × 11 de scores exacts.

- **Top 5 scores simples, méthode A** : classement décroissant selon la probabilité de la cellule modale (score exact prédit), départagé par identifiant de match.
- **Top 5 scores groupés, méthode B** : on conserve **le même score exact modal et son groupe de trois scores**, puis on classe par la somme des trois probabilités ; départage par la probabilité modale puis l'identifiant.
- Seuls les matchs dont le coup d'envoi est **après l'heure de génération** et le jour UTC correspondant sont publiables. Les groupes restent les proxies **expérimentaux** du protocole de recherche ; leur existence chez 1xBet n'est pas confirmée.
- Au maximum cinq éléments par section, jamais de remplissage artificiel ; deux listes indépendantes, un match pouvant figurer deux fois. Aucune statistique de rendement ou cote bookmaker inventée.

## Raccordement avec un prévisionniste V3 réellement prospectif

Le moteur Pro/VIP `generate_data.py` n'est **pas modifié**. Le pipeline privé `.github/workflows/daily-hybrid-v3-exact-top5.yml` charge la version auditée du V3 depuis le commit de recherche gelé `f0c700b2448923fadd6fc6f260da34d0576f3e1f` et entraîne le modèle à partir des historiques chiffrés certifiés. L'entraînement des coefficients est **figé au 31/12/2025** (variante de validation gelée) ; les statistiques d'équipes restent mises à jour à partir des matchs BSD terminés jusqu'à la veille. Cette variante n'est pas identique au backtest B avec réentraînements progressifs sur 2026 ; ne pas transférer automatiquement ses taux de réussite au trafic réel. Le nom de championnat absent des événements futurs est résolu à partir de leur identifiant BSD via archive/catalogue/detail vérifié, jamais par supposition.

Le moteur `scripts/forecast_hybrid_v3_daily.py` génère un fichier JSON privé pré-match avec le schéma suivant (illustration **non destinée à être publiée**) :

```json
{
  "origin": "prospective_prematch",
  "model": "machine_learning_v3_hybrid",
  "generated_at": "YYYY-MM-DDTHH:MM:SSZ",
  "fixtures": [{
    "model": "machine_learning_v3_hybrid",
    "id": "identifiant-source-vérifié",
    "home": "Équipe domicile",
    "away": "Équipe extérieure",
    "league": "Championnat",
    "kickoff_utc": "YYYY-MM-DDTHH:MM:SSZ",
    "history_latest_day": "YYYY-MM-DD",
    "model_fit_latest_day": "YYYY-MM-DD",
    "grid": [[0.0, "... 11 valeurs"], "... 11 lignes au total"]
  }]
}
```

La grille doit contenir **121 probabilités numériques, pas les vraies chaînes d'exemple ci-dessus**. Toutes les lignes doivent avoir un identifiant unique, l'historique et l'entraînement doivent dater d'avant le jour de publication, et la grille doit être calculée avant chaque résultat. Ne pas incorporer `actual_score`, `home_score`, `away_score`, `hit`, `result` ou `is_finished` à ce fichier.

Une fois le moteur prospectif disponible et vérifié, la publication se fait par :

```bash
python scripts/publish_exact_scores.py \
  --input /tmp/v3-authentique-prematch.json \
  --out scores-exacts.json
```

Par défaut, la génération doit dater du jour UTC en cours. Une entrée vide publie un état `unavailable`, et les matchs commencés sont écartés. Il est volontairement **impossible** d'utiliser les sorties `all_predictions.csv` du backtest comme entrée directe : elles contiennent des résultats réels et ne sont pas une publication pré-match.

## Structure JSON publique

```json
{
  "schema_version": "mrx-exact-top5-v1",
  "model": "machine_learning_v3_hybrid",
  "status": "unavailable",
  "date": null,
  "generated_at": null,
  "simple": [],
  "grouped": []
}
```

Lorsqu'un vrai modèle prospectif publie, `status="published"`, `date` et `generated_at` doivent être valides et du **jour courant UTC**. Les éléments de `simple` comprennent `id`, `league`, `home`, `away`, `kickoff_utc`, `score`, `probability`. Les éléments de `grouped` ajoutent `group`, `group_scores` (exactement 3).

Le navigateur charge le JSON via `fetch` sans cache, contrôle sa structure et sa date, et n'affiche jamais les sélections d'une autre journée. Les valeurs provenant du JSON sont placées dans le DOM avec `textContent`, jamais interpolées dans du HTML.

## Validation locale et GitHub

```bash
python -m unittest discover -s tests -p 'test_exact_scores_tab.py' -v
node --check assets/js/scores-exacts.js
node --check assets/js/menu.js
```

Le workflow CI `.github/workflows/scores-exacts-page-tests.yml` vérifie le contrat du flux. Le workflow quotidien `.github/workflows/daily-hybrid-v3-exact-top5.yml` prévoit **00 h 22 et 11 h 42 UTC**, plus un lancement lors de son introduction sur la branche `main`. Sur la branche de travail, il effectue uniquement des dry-runs sans publication. En production, il refuse de publier des résultats périmés, des marchés non vérifiés ou moins de cinq sélections dans chaque Top. Une seule publication du jour est conservée (pas de remplacement opportuniste après résultat). L'écriture du JSON public déclenche explicitement `deploy.yml` car les commits du bot ne déclenchent pas automatiquement les autres workflows. Aucun canal Telegram ni générateur Pro/VIP n'est modifié.
