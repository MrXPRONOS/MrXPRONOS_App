# Dixon-Coles — nouveau projet totalement indépendant

Version 1.0.0 — **aucun code ni fichier repris d'un autre système Mr XPRONOS**. Le dépôt est autonome, avec sa propre base SQLite, son moteur et son interface.

## Fonctionnalités livrées

- Modèle Dixon-Coles (1997) : attaques `α`, faiblesses défensives `β`, avantage domicile `γ`, paramètre commun `ρ`.
- Maximum de vraisemblance pondéré par la récence, avec `ξ=0.0065` par **demi-semaine** (modifiable).
- Contrôle de l'identifiabilité (moyenne des attaques = 1, graphe d'adversaires connecté), contraintes de positivité, régularisation configurable.
- Distribution des scores exacts, classement Top 5, scores 1-N-2, probabilité de masse hors grille.
- Import CSV UTF-8 des résultats (standards ou colonnes de Football-Data.co.uk), dates normalisées en UTC.
- Synchronisation sur demande des saisons d'une ligue via API officielle football-data.org v4, avec jeton privé.
- Sélection des rencontres futures fournies par l'API ou création manuelle d'un match entre deux équipes connues.
- Recalcul intégral du modèle au moment de la prédiction, uniquement avec les résultats **antérieurs au lancement de l'analyse**.
- Historique immuable des prévisions avec comparaison automatique aux résultats synchronisés. Possibilité de saisir un résultat pour un match créé manuellement, marqué non vérifié.
- Backtest walk-forward : chaque match test est prédit après réentraînement sur les matchs d'avant sa date (aucune rencontre du même jour dans l'apprentissage), avec Top 1, Top 3 et log loss.
- CLI et interface web responsive, génération explicite d'une base DEMO entièrement fictive.
- Tests automatisés et workflow GitHub Actions prêt pour un **nouveau dépôt**.

## Installation (Windows, Fedora, Linux, macOS)

Prérequis : **Python 3.10+**. Depuis le dossier de ce projet, lancer :

### Windows PowerShell

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m dcscore.cli serve
```

Si PowerShell bloque l'activation, utiliser directement `.venv\Scripts\python.exe -m pip install -e ".[test]"` puis `.venv\Scripts\python.exe -m dcscore.cli serve`.

### Fedora / Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m dcscore.cli serve
```

Ouvrir **http://127.0.0.1:8088**. Le serveur écoute seulement en local par défaut (pas de publication automatique sur Internet).

Pour éprouver immédiatement tout le circuit, cliquer sur **Charger la démo**, puis **Analyser ce match** et **Lancer le backtest**. Les clubs et scores de démonstration sont inventés. Ils ne fournissent **aucune prédiction réelle**.

## Passer à de vrais matchs

### Option A : API football-data.org (automatique)

1. Créer une clé personnelle sur https://www.football-data.org/client/register
2. Définir la variable d'environnement avant de lancer le serveur (ne jamais envoyer la clé dans un message ni la commiter dans Git) :

**PowerShell** :

```powershell
$env:FOOTBALL_DATA_TOKEN="VOTRE_JETON_PERSONNEL"
python -m dcscore.cli serve
```

**Fedora / Linux** :

```bash
export FOOTBALL_DATA_TOKEN="VOTRE_JETON_PERSONNEL"
python -m dcscore.cli serve
```

3. Dans l'interface, saisir le code du championnat (`PL`, `FL1`, `PD`, `BL1`, `SA`, etc.), choisir les années de début de saison, puis cliquer **Synchroniser**.
4. Choisir un match à venir et **Analyser ce match**. La prédiction enregistre l'heure du calcul, le nombre de matchs de formation et les 5 scores les plus probables.
5. Synchroniser à nouveau les résultats après le match pour mettre à jour le journal des réussites.

La disponibilité des anciennes saisons dépend du plan du fournisseur. En novembre 2026, le plan gratuit annonce 12 compétitions, scores en différé et 10 requêtes/minute. Le programme ne contourne aucune restriction d'accès; une saison refusée reste refusée.

**Important :** si le compte gratuit ne donne pas suffisamment d'historique, un CSV autorisé est l'alternative prévue. Sans clé ou historique, aucune prédiction de match réel n'est possible.

### Option B : CSV légalement obtenu

Le programme accepte un CSV UTF-8 dont les en-têtes comprennent :

```csv
date,home_team,away_team,home_goals,away_goals,competition,home_id,away_id,match_id
2025-09-01,Club Fictif A,Club Fictif B,2,1,EXM,A,B,exm1
2025-09-02,Club Fictif C,Club Fictif D,1,1,EXM,C,D,exm2
2025-09-08,Club Fictif B,Club Fictif A,0,2,EXM,B,A,exm3
```

**Ces trois lignes sont entièrement fictives et insuffisantes pour entraîner un modèle réel.** Ne pas les utiliser comme historique de football.

- Les colonnes obligatoires sont `date`, `home_team`, `away_team`, et les deux scores pour les matchs terminés. La colonne `competition` est recommandée ; sinon la compétition par défaut est utilisée.
- Pour les rencontres futures, laisser les **deux** colonnes de buts vides. Pour les rencontres créées dans l'interface, choisir le vrai coup d'envoi local.
- `home_id` et `away_id` sont fortement recommandés pour assurer la stabilité des identifiants lorsque les équipes changent de nom. Sans ces colonnes, les noms normalisés servent d'identifiants.
- `match_id` facultatif est utile aux mises à jour d'une même rencontre. Les identifiants restent séparés par compétition ; les importations ultérieures avec le même ID mettent à jour le match.
- Les dates sans heure sont considérées comme étant à **00:00 UTC** : pour le backtest, aucune rencontre du même jour n'est mise dans l'entraînement. Pour un match futur, utiliser la création manuelle si seule la date (sans heure) est disponible.
- Les dates `JJ/MM/AAAA` et `AAAA-MM-JJ` sont acceptées. Les dates/horaires complets doivent inclure `Z` ou un fuseau horaire explicite.
- Les CSV de type `Date,HomeTeam,AwayTeam,FTHG,FTAG,Div` sont également pris en charge si leur utilisation respecte leur licence.
- Les données d'API `fd:PL` et les CSV `csv:PL` ne sont **jamais mélangés automatiquement** ; cela évite de compter deux fois des matchs et de faire correspondre à tort les noms et identifiants d'équipes.
- Les équipes de compétitions différentes ne sont pas mises sur la même échelle sans résultats inter-compétitions appropriés.

## Console alternative

```bash
python -m dcscore.cli --help
python -m dcscore.cli demo
python -m dcscore.cli leagues
python -m dcscore.cli fixtures --competition demo:SIM
python -m dcscore.cli predict demo:tomorrow
python -m dcscore.cli backtest --competition demo:SIM --samples 12
python -m dcscore.cli import-csv chemin/fichier.csv --competition PL
python -m dcscore.cli sync --code PL --seasons 2024 2025 2026
```

Pour utiliser une base temporaire indépendante, ajouter `--db chemin/base.db` **avant** la commande.

## Fondement mathématique

**Papier original :** Dixon, M. J. & Coles, S. G. (1997), *Modelling Association Football Scores and Inefficiencies in the Football Betting Market*, JRSS Series C, 46(2), 265–280. DOI : https://doi.org/10.1111/1467-9876.00065

Pour la rencontre domicile `i` contre extérieur `j` :

- `λ = α_i × β_j × γ`
- `μ = α_j × β_i`
- `p(x,y) = Poi(x; λ) × Poi(y; μ) × τ(x,y)`.

Correction `τ` :

| Score (domicile, extérieur) | Correction |
|---|---|
| (0,0) | `1 - λ μ ρ` |
| (0,1) | `1 + λ ρ` |
| (1,0) | `1 + μ ρ` |
| (1,1) | `1 - ρ` |
| autres | `1` |

Les données antérieures au moment de la prédiction reçoivent un poids `w_k = exp(- ξ × âge_en_jours / 3.5)`. L'optimisation maximise la somme pondérée des log-vraisemblances, avec `mean(α)=1`.

### Choix d'ingénierie ajoutés explicitement

L'étude originale ne prescrit pas l'ensemble des sécurités informatiques ni la régularisation de ce code. Notre implémentation ajoute :

- Une régularisation `L2` configurable, par défaut `0.15`, afin de limiter les paramètres extrêmes lorsque peu de matchs sont disponibles. Mettre `0` pour la retirer.
- Une paramétrisation bornée de `ρ` pour que toutes les probabilités restent valides pour chaque paire d'équipes du championnat entraîné.
- Un intervalle raisonnable des intensités et des paramètres durant l'optimisation numérique (stabilité).
- Un nombre minimum de 80 matchs historiques et 5 matchs par équipe sélectionnée, modifiable. Ces minima sont des garde-fous pratiques, **pas** une preuve de suffisance statistique.
- Une grille de scores de 0 à au moins 8 buts, élargie automatiquement jusqu'à une masse > 99,99999 % lorsque possible, sans renormaliser artificiellement les probabilités tronquées.
- Les probabilités 1N2 sont calculées par distribution de Skellam avec la correction Dixon-Coles des quatre scores. L'absence de renormalisation évite la perte de probabilité dans les buts rares.

## Evaluation honnête

Le backtest reconstruit le modèle avant la date de chaque match et calcule : exact Top 1, Top 3, log loss et comparaison à Poisson avec les **mêmes intensités** (rho=0). Il ne prouve pas une supériorité sur les bookmakers ni une rentabilité financière. Les données manuelles ne constituent pas une vérification externe.

Pour une évaluation sérieuse, utiliser des centaines de matchs, contrôler les saisons et éviter le choix des paramètres sur la période finale de test. Le coefficient `ξ=0.0065` est la référence historique ; une optimisation réelle est désormais disponible et sa provenance est explicitement indiquée.

## Vérifier l'installation

```bash
python -m pytest -q
```

Les tests ne nécessitent aucun réseau et incluent un serveur FastAPI de test ainsi que des données purement fictives. Ils ne testent pas une authentification réelle à football-data.org (nécessite une clé et un accès utilisateur).

## Confidentialité, périmètre, limites

- Aucun accès au dépôt GitHub d'origine, aucune réutilisation de code, aucun secret importé de cet ancien projet.
- Ne jamais placer une clé API dans le navigateur, GitHub ou un CSV ; la clé est lue sur le serveur via une variable d'environnement.
- Le serveur est prévu pour un **usage local privé**. Il n'intègre **pas** l'authentification et le contrôle d'accès nécessaires pour l'exposer publiquement sur Internet.
- En cas d'erreur d'API, de mauvaise convergence, de manque d'historique, d'équipe inconnue ou de match commencé, il refuse explicitement la prévision plutôt que d'inventer des chiffres.
- Le code n'exécute pas de tâches automatiques quotidiennes et ne publie aucune prédiction sur les réseaux. Les synchronisations sont manuelles, à la demande.
- La prise en compte des blessures, xG, cotes et composition d'équipe ne fait **pas** partie du Dixon-Coles d'origine et n'est volontairement pas intégrée dans cette version.

## Structure

```text
dcscore/
  model.py      Calcul Dixon-Coles, optimisation et probabilités
  sources.py    CSV et football-data.org v4
  store.py      SQLite, stockage et suivi
  service.py    Prévisions, synchronisation, backtest
  api.py        Serveur HTTP FastAPI
  cli.py        Interface console
  demo.py       Génération explicite de données fictives
  domain.py     Validation des rencontres
  static/       Interface web autonome
tests/          Tests automatiques
.github/        Workflow de tests pour un nouveau dépôt
```


## Nouveau : optimisation automatique de ξ sur résultats réels

**Fonctionnalité disponible depuis la V1.1.** Le coefficient de décroissance `ξ`
peut être optimisé sur des scores réellement observés, au lieu de toujours
reprendre la valeur historique `0.0065`.

Source de démonstration réelle autorisée : les résultats **CC0**
[OpenFootball / football.json](https://github.com/openfootball/football.json),
accessibles sans clé API. Le logiciel importe ses saisons dans la compétition
`of:ENG-PL`. Les autres sources `fd:*` et `csv:*` restent prises en charge pour
calibrer leur championnat, sans croiser leurs bases ni réutiliser les anciens
moteurs du projet principal.

**Dans l'interface :** « Importer les résultats réels (CC0) », puis sélectionner
`of:ENG-PL` et « Optimiser ξ avec des scores réels ». Ensuite le mode
« Automatique » de la prédiction applique la dernière calibration enregistrée.

**Depuis la console :**

```bash
python -m dcscore.cli sync-openfootball --seasons 2021-22 2022-23 2023-24 2024-25 2025-26 2026-27
python -m dcscore.cli calibrate-xi --competition of:ENG-PL \
  --start 2024-08-01 --end 2025-06-01 \
  --block-months 2 --min-games 500 --min-team 5 \
  --min-folds 4 --min-scored 160 \
  --holdout-start 2025-08-01 --holdout-end 2026-06-01 \
  --output dcscore/calibrations/eng-premier-league.json
```

Pour une prédiction, l'argument `--xi` est désormais **facultatif** : sans
argument, `dcscore` applique d'abord le coefficient optimisé pour la
compétition. S'il n'existe pas, le programme indique clairement qu'il utilise
le coefficient historique **non optimisé**, `0.0065`.

Le rapport contient les performances **hors entraînement** des huit valeurs
candidates, le nombre de matchs évalués, les dates de validation, les
empreintes des données et un test final sur une saison postérieure, jamais
employée pour sélectionner le coefficient. Les prédictions portent leurs
métadonnées de calibration, notamment `xi_source` et `stale_data`.

Le workflow GitHub Actions dédié lance ce protocole sur le vrai championnat
et publie la valeur validée dans `dcscore/calibrations/` : elle peut donc être
utilisée même avec une base SQLite nouvellement créée. Le rapport publié
n'est pas une garantie de rentabilité ni de prédiction exacte.

**Voir le protocole intégral, ses contraintes et son périmètre :**
[Xi Calibration](XI_CALIBRATION.md).
