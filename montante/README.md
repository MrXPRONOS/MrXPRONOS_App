# Montante quotidienne — BSD V2

Le moteur sélectionne **au plus une** prédiction avant-match sur la journée UTC à partir des pronostics **BSD V2 déjà publiés** (`data.json`). Il ne place **aucune mise**. L'absence de sélection est volontaire si la fiabilité ou la disponibilité des cotes est insuffisante.

## Règles
- Marché simple, jamais un combiné : catégories PRO/VIP, niveau de confiance public >= 79 %, sélection recommandable et match du jour non commencé, avec au moins 60 minutes de marge.
- **Cote > 1,20** (strictement, pas égale), avec origine vérifiée dans le moteur BSD V2, horodatée il y a moins de six heures. Les cotes `mrxpronos_model` sont **exclues**. Une cote consensus est une observation, **pas une offre de pari certaine**.
- Probabilité **conservatrice >= 82 %** et écart d'au moins **2,5 points** au-dessus de la probabilité implicite `1/cote` ; les garde-fous BSD V2.1 et le suivi historique de dérive restent actifs. Marchés `12` et `UNDER_45` exclus.
- Départage selon la probabilité conservatrice, l'écart avec la cote, la calibration, l'historique clôturé et la provenance de la cote. Aucun de ces critères n'implique une certitude.
- Premier choix **figé** dans `montante/ledger.json` par date UTC; une exécution ultérieure ne peut pas le remplacer. Si aucun choix n'est éligible, le moteur peut retenter après la prochaine génération.

## Sorties
- `montante/du-jour.md`: lisible directement sur GitHub.
- `montante/daily.json`: sélection et diagnostics de rejets.
- `montante/ledger.json`: archive immuable des jours sélectionnés, jamais de tickets de bookmaker.

## Automatisation
Workflow `.github/workflows/bsd-v2-montante.yml` : après une production BSD V2 réussie, à 06:35, 12:35 et 18:35 UTC et déclenchement manuel. Un `pull_request` n'exécute que les tests. La mise en production exige la fusion explicite de la PR; le cron peut être retardé.

## Limites
Ce module ne réinterroge pas un bookmaker au moment de miser, n'exécute aucun pari et ne garantit ni victoire, ni disponibilité de la cote annoncée, ni rendement positif. Vérifier match, sélection, prix et conditions chez le bookmaker immédiatement avant de miser. Si un pronostic change de statut après son choix figé, il faut **renoncer** à le jouer plutôt que forcer une mise.