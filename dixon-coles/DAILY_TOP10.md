# Mr XPRONOS — Top 10 quotidien / Dixon-Coles indépendant

## Périmètre de cette version

**Livré :** découverte des matchs du jour choisi, classement éditorial, contrôle des données,
prédiction exacte Top 5 avec probabilités, Top 10 retenu (ou nombre inférieur clairement indiqué),
préparation `predictions.json` et `video_payload.json`, automatisation GitHub Actions.

**Non livré à ce stade :** rendu MP4, voix off, intégration graphique des logos, comptes sociaux,
publication automatique. Ce sont les étapes suivantes. La simple présence du JSON ne publie rien.

## Sources de données

- **Prioritaire en production :** football-data.org API v4, avec variable privée `FOOTBALL_DATA_TOKEN`
  disponible dans le job GitHub Actions. Les rencontres sont identifiées par leur ID officiel
  et les historiques utilisent les mêmes IDs de clubs et la même compétition, sans mélanger les sources.
  Les saisons accessibles, certaines coupes et certains championnats dépendent du niveau d'abonnement.
  La version sans abonnement peut être limitée à 10 requêtes/minute ; le client espace ses appels.
- **Mode de secours, sans clé :** OpenFootball/football.json (CC0) pour Premier League,
  La Liga, Bundesliga, Serie A, Ligue 1, Eredivisie, Primeira Liga et Championship.
  Les matchs de ce flux ne sont **pas validés comme horaires officiels** et les résultats peuvent être
  anciens. Le système peut fournir une analyse exploratoire, mais **`ready_for_video=false`**
  si les seuls calendriers proviennent de cette source.
- **Nouveau mode automatique multi-sources :** si la clé est disponible, le programme interroge
  d’abord football-data.org, puis OpenLigaDB (Bundesliga, 2. Bundesliga, 3. Liga) et OpenFootball.
  Sans clé, il interroge les deux sources libres. Il choisit une seule source par championnat et par date,
  sans mélanger leurs équipes ni leurs historiques. Les échecs d'une source ne bloquent pas les autres.
- **OpenLigaDB :** données de la communauté sous **Open Database License 1.0 (ODbL)**.
  Attribution : [OpenLigaDB](https://openligadb.de/). API sans clé ; respect des limites
  d’accès et des obligations de licence pour une réutilisation commerciale. Les écussons des clubs
  ne sont pas couverts par cette licence. Le calendrier communautaire reste non corroboré,
  donc il ne suffit pas, à lui seul, à autoriser la création automatique d'une vidéo.
- **Condition de publication :** sans calendrier fiable et sans 10 matchs admissibles,
  le système produit un rapport explicatif et bloque `ready_for_video`. Ne jamais fabriquer
  des matchs ou des probabilités pour arriver à dix.
- Le programme **n'emprunte aucune donnée ni algorithme** aux anciens moteurs de Mr XPRONOS.
- Les paramètres de la Premier League calibrés sur la source `of:ENG-PL` ne sont **pas**
  appliqués à d'autres ligues, ni à `fd:PL`. Les autres ligues utilisent actuellement
  le Dixon-Coles original avec `xi=0.0065` (sans prétendre à une calibration locale).

## Classement des matchs

Le score de prestige est déterministe et auditable ; ce n'est **pas** la probabilité de victoire.
Il combine : importance du championnat, poids éditorial de chaque club reconnu,
bonus si deux grands clubs s'affrontent, rivalités identifiées et bonus des phases finales.
Les finales reçoivent le plus gros bonus. Le système tente de diversifier les compétitions
(maximum 4 par ligue au premier passage, puis complète si nécessaire).

Il parcourt les rencontres par prestige et retient **au maximum dix** matchs compatibles avec les
contrôles de données, **jamais des matchs inventés pour remplir la liste**. Seuls les matchs
`SCHEDULED` et `TIMED` avec coup d'envoi **strictement dans le futur** sont admissibles.
Les matchs terminés, en cours, reportés, sans horaire ou hors du jour local sont exclus.

## Vérifications avant prédiction

- Historique propre à une compétition et à un fournisseur, pas de fusion inter-ligues.
- Au moins **80 résultats historiques**, et **6 par équipe**, valides avant l'instant du calcul.
- Dernier résultat de la ligue vieux de **21 jours maximum** (réglable), pour éviter les sources gelées.
- Refus explicite si données insuffisantes, clubs absents, modèle non convergent ou résultats périmés.
- Les cinq scores les plus probables sont fournis avec leurs probabilités exactes ; le score modal n'est
  **pas** une certitude ni une recommandation de pari. Si Top 1 et Top 2 diffèrent de moins d'un point
  de pourcentage, un avertissement est enregistré.
- Pour une finale sans lieu vérifié, le programme compare **deux scénarios** (avantage domicile / terrain
  neutre) et met `ready_for_video=false` tant que le lieu n'est pas confirmé.
- Aucun automatisme social ne doit publier si `ready_for_video=false`.

## Exécution quotidienne

Le workflow indépendant est `.github/workflows/dixon-coles-daily-top10.yml`.

- **Programmation :** tous les jours à **21 h UTC = 21 h à Lomé**, pour les matchs **du lendemain**.
- Lancement manuel via **Actions → Dixon-Coles - top 10 quotidien - préparation vidéo → Run workflow**.
  Choisir `today` ou une date `YYYY-MM-DD` pour une exécution manuelle.
- Les sorties de chaque exécution sont conservées dans un **artifact** GitHub Actions (90 jours),
  sous `results/daily/YYYY-MM-DD/` ; elles ne sont **pas ajoutées au dépôt à chaque cron**.
  Cela évite des conflits de commits avec les autres workflows du dépôt.
- Le workflow exécute également les tests du module avant chaque collecte.

### Secret GitHub requis pour les matchs officiels

Dans **Settings → Secrets and variables → Actions → New repository secret** :

`FOOTBALL_DATA_TOKEN` = clé API personnelle fournie par football-data.org.

Ne pas placer la clé dans le code, un fichier JSON, une vidéo, ou la conversation.
Vérifier les droits d'usage et de redistribution des données, noms et écussons, surtout en vidéo
sponsorisée/commerciale.

En l'absence du secret, le workflow utilise le flux CC0 de secours : il peut rendre le résultat
**PARTIAL** ou **NO_ELIGIBLE_MATCHES** et n'autorise pas la suite vidéo.

### Commande manuelle

```bash
cd dixon-coles
python -m pip install -e '.[test]'
python -m dcscore.daily --day tomorrow --source auto --count 10
python -m dcscore.daily --day today --source openfootball --count 10
python -m dcscore.daily --day tomorrow --source openligadb --count 10
python -m pytest -q tests/test_daily_pipeline.py
```

## Format JSON pour automatiser la vidéo ensuite

`predictions.json` : intégralité des candidats, matchs rejetés, rang éditorial, date,
qualité de données, probabilités, 1N2, score modal et Top 5, nombre d'observations, avertissements.

`video_payload.json` : contrat d'entrée indépendant pour la future étape vidéo :

```json
{
  "schema_version": 1,
  "ready_for_video": true,
  "date_local_africa_lome": "YYYY-MM-DD",
  "format": "9:16",
  "language": "fr",
  "clips": [
    {
      "order": 1,
      "headline": "CLUB A - CLUB B",
      "display_score": "1-0",
      "display_probability_percent": 12.7,
      "top_3": [],
      "narration_fr": "..."
    }
  ]
}
```

*Cet exemple est un **schéma illustratif** et non une prévision de matchs réels.*

La future étape vidéo devra vérifier `ready_for_video`, la validité du jour, l'heure des matchs et
l'absence de vidéo déjà publiée, puis composer un format vertical 1080×1920 avec l'identité Mr XPRONOS,
les logos autorisés, une voix française, une musique libre de droits, les probabilités et un rappel 18+.
Avant d'appeler les API YouTube/TikTok/Meta, il faudra régler leurs accès et conditions de publication.
Pour éviter des publications non désirées, la première phase vidéo devrait produire un **MP4 de validation**
seulement, avant d'activer les envois automatiques.

## Interprétation des états

- `READY` : dix matchs, sources de calendrier du fournisseur officiel, historique admissible,
  aucun doute de lieu de finale. **Préparation possible** pour le futur moteur vidéo.
- `PARTIAL` : un ou plusieurs matchs calculés, mais moins de dix, ou provenance/lieu insuffisant.
- `NO_ELIGIBLE_MATCHES` : aucun match admissible ; pas de fausse donnée publiée.

Ce système ne prétend pas garantir dix grands matchs **chaque jour** : certains lundis ou trêves
internationales ne comportent pas dix affiches de ce niveau.
