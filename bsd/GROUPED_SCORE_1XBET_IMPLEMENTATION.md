# Mr XPRONOS — Correct Score – Group Bet (1xBet)

**État : implémentation expérimentale, non fusionnée avec la production.** Aucune mise, aucun coupon automatique, aucun message Telegram. L'intégration au site est une prévisualisation et n'autorise pas encore une publication de paris réels.

## Les huit améliorations demandées

| # | Exigence | Implémentation | Limite |
|---|---|---|---|
| 1 | Répertorier les groupes 1xBet par match | `grouped_correct_score.py`: G1–G9 observés et validation d'un catalogue **par match** | La liste observée ne prouve pas une disponibilité identique sur chaque rencontre |
| 2 | Probabilité du groupe | Somme des probabilités des scores distincts dans la matrice BSD | Somme des probabilités **à l'intérieur** du groupe ; les groupes se recoupent |
| 3 | H2H + Under 2,5 + forme/domicile/buts attendus | `grouped_correct_score_engine.py` utilise BSD V2 + H2H + Under 2,5 | Les signaux H2H n'ont pas un taux garanti |
| 4 | Double Chance V2 : 1X/X2/12 | Modèle `bsd_v2_double_chance.py` entraîné sur 2024, distinction P(1), P(X), P(2), filtrage de cohérence | 1X n'affirme jamais une victoire domicile ; 12 n'indique pas un camp |
| 5 | Cotes réelles 1xBet, valeur estimée | `validate_1xbet_snapshot` accepte seulement la photo/trace **documentée** du marché exact pour le match, avec ID bookmaker, URL, horodatage et mise en correspondance BSD ; calcul P×cote−1 | **Flux automatique 1xBet non connecté**. Les archives BSD ne contiennent pas ces cotes. Les captures apportées par un opérateur ne sont pas vérifiées indépendamment par l'application |
| 6 | Backtest par groupe / variantes | `grouped_correct_score_backtest.py` : baseline, Double Chance, H2H+Under, groupe avec prix documenté, mêmes matchs et suivi mensuel | Historique 2026 déjà exploré ; cotes historiques 1xBet non disponibles, ROI non calculable |
| 7 | Affichage des scores groupés / historique | `scores-groupes.html` et CSS/JS responsive avec filtre camp, À venir/Historique, 3 scores, probabilité, cote documentée | Preview sur branche expérimentale ; aucun pari public activé |
| 8 | Validation prospective | `grouped_correct_score_prospective.py` : registre Fernet séparé, capture avant le match, empreinte SHA-256, règlement après 4 h, agrégats et flux de revue | Les performances futures doivent être mesurées sans modifier les pronostics déjà capturés |

## Groupes observés

- G1 : 0-0 / 1-0 / 0-1
- G2 : 0-1 / 0-2 / 0-3
- G3 : 0-4 / 0-5 / 0-6
- G4 : 1-0 / 2-0 / 3-0
- G5 : 1-2 / 1-3 / 1-4
- G6 : 2-1 / 3-1 / 4-1
- G7 : 2-3 / 2-4 / 3-4
- G8 : 3-2 / 4-2 / 4-3
- G9 : 4-0 / 5-0 / 6-0

Source de l'exemple de marché : https://1xbet.bet.br/en/line/football/21317-africa-cup-of-nations/756687632-ghana-republic-of-the-gambia

Les règles officielles 1xBet distinguent **Correct Score – Group Bet** (dont les issues live évoluent selon le score courant) de **TOTO Correct Score**. Ne jamais les mélanger : https://1xbet.com/en/information/rules/9

## Cotes réelles — procédure pour un match

Le fichier local (non committé) est un tableau JSON de **captures observées par un opérateur** :

- `bookmaker` : `1xbet`
- `bsd_event_id` : ID exact du match BSD
- `bookmaker_event_id` : ID numérique visible dans l'URL du match 1xBet
- `market` : `Correct Score - Group Bet`
- `period` : `FT` (90 minutes, sans prolongation)
- `kickoff_utc` : date officielle de départ + fuseau UTC
- `captured_utc` : horodatage réel avant le match
- `source_url` : URL HTTPS du **même match** sur 1xBet, contenant l'ID bookmaker
- `capture_reference` : identifiant du relevé ou capture conservée séparément
- `selections` : tableau de `{"group_id": "G4", "scores": ["1-0","2-0","3-0"], "odds": <cote décimale relevée>}`

Si aucune cote n'est documentée, `odds=null` et `expected_value=null`. Le système **ne récupère pas une cote d'un autre marché** et ne fabrique aucune cote. La date, les équipes, le match et le regroupement doivent être vérifiés avant affichage. Toute cote est susceptible de changer.

Avec une capture locale validée, lancer `python bsd/grouped_correct_score_prospective.py --quotes-json /chemin/privé/quotes.json` dans un environnement chiffré ayant l'historique BSD et ses secrets. Aucun cookie, identifiant ou mot de passe 1xBet n'est requis.

## Déploiement et validation

1. Préproduction : `python -m unittest bsd/test_grouped_correct_score.py -v` et `python -m unittest bsd/test_exact_scores_prospective.py -v`.
2. Backtest rétrospectif sans cotes : `python bsd/grouped_correct_score_backtest.py` (archives BSD restaurées sur runner privé).
3. Suivi prospectif : produire `bsd/grouped_1xbet_shadow_ledger.enc.json` et le rapport `tmp/grouped-correct-score/prospective-report.json`.
4. Créer l'aperçu `tmp/grouped-correct-score/scores-groupes-review.json` ; **ne jamais le déployer directement** sans approbation de provenance et validation.
5. Préparer une connexion sous licence/capable de fournir spécifiquement les lignes « Correct Score – Group Bet » de 1xBet, avec ID de sélection, cotes horodatées et identifiants de match.
6. Évaluer Top groupe, couverture, Brier, performances par ligue et période, risques de faible échantillon et résultats prospectifs ; ajouter les cotes uniquement si elles sont authentifiées.
7. Débloquer le site public uniquement après validation de ces contrôles et de la conformité applicable.

**Attention :** une plus forte précision n'implique pas nécessairement un pari rentable. Les cotes reflètent la marge du bookmaker et il faut vérifier l'espérance de valeur avec un calibrage indépendant.
