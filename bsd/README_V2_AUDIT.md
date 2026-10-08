# BSD V2 — Audit de finalisation (8 octobre 2026)

V2 est un moteur **expérimental indépendant** de SportData, du site et de Telegram.
Les fichiers sont poussés sur GitHub. Les **nouveaux workflows doivent encore être exécutés** : aucun nouveau taux de réussite n'est annoncé tant que la validation n'est pas terminée.

## État des huit améliorations

| N° | Amélioration | Implémentation technique | Vérification/limite |
|---|---|---|---|
| 1 | Séparer fiabilité et valeur | **Complète dans le code** | En fiabilité, choisir la probabilité la plus élevée (pas de seuil de cote théorique); valeur exige une cote réelle |
| 2 | Calibrer les probabilités | **Complète dans le code** | Nouveau V2Calibration par marché+tranche; entraînement janvier–août 2025; contrôle septembre–décembre 2025; il reste à valider l'amélioration réelle |
| 3 | Puissance attaque/défense/adversaire | **Complète dans le code** | Pondération récence/adversaire/domicile-extérieur; aucune supériorité statistique garantie |
| 4 | Ajustements par championnat | **Complète dans le code** | Priors league-specific avec shrinkage; faible couverture filtrée |
| 5 | Dixon-Coles vs Poisson | **Complète dans le code** | Ajustement et validation du rho sur deux périodes 2024 séparées; test hors échantillon 2026 |
| 6 | Walk-forward et suivi prospectif | **Complète techniquement, validation terrain en cours** | Fenêtres point-in-time + délai de disponibilité 4h; snapshots horodatés et règlement quotidien; les futures observations restent nécessaires |
| 7 | Contrôle de qualité | **Complète dans le code** | Contrôles ligue, forme, fraîcheur, surconfiance par marché depuis 2025 |
| 8 | Cotes réelles et valeur attendue | **Partielle selon l'accès externe** | Cotes consensus BSD implémentées avec source et timestamp; cotes 1xBet et marché Over/Under 4.5 via per-event exigent plan/endpoint adéquat; aucun code de coupon bookmaker inventé |

## Pipeline isolé

- .github/workflows/bsd-v2-validation.yml : tests unitaires, comparaison V1/V2 sur mêmes matchs, comparaison avec Under 4.5, calibration 2025 + qualité, test 2026.
- .github/workflows/bsd-v2-shadow.yml : cron quotidien 06:15 UTC et lancement manuel, génération de V2 à l'avance, cotes d'avant-match si disponibles, artefact privé GitHub 90 jours.
- .github/workflows/bsd-v2-settlement.yml : cron quotidien 07:50 UTC et lancement manuel, télécharge des prédictions enregistrées ≥30h auparavant, vérifie leur empreinte puis les règles sur scores confirmés; artefact 90 jours.
- Le rapport comparatif n'est pas comparable au précédent tant que le nouveau filtre qualité + calibration 2025 n'a pas été exécuté.
- Les rapports JSON dérivés ne contiennent pas l'archive de matchs BSD brute; les matchs historiques demeurent chiffrés.

## Limites importantes

1. Cotes **consensuelles** BSD du plan gratuit : elles ne représentent PAS un bookmaker unique, ni un prix garanti disponible. Le plan bookmaker nommé peut retourner «bookmakers_not_entitled» (403). Le collecteur ne change pas de source en secret.
2. Le flux /api/v2/odds/ est pré-match, sans reconstruction complète des cotes historiques. **Aucun backtest avec cotes réelles d'époque** n'est revendiqué.
3. Le flux legacy permet over_under_15/25/35 et pas toujours over_under_45 ; ce dernier a besoin d'un autre endpoint et n'a **pas** d'intégration complète dans le collecteur actuel.
4. Aucune preuve de rentabilité, de rendement assuré ou de fiabilité absolue.
5. La confirmation statistique dépend d'échantillons futurs : ce n'est pas une fonctionnalité qui peut être achevée immédiatement par écriture de code.

## Guide

1. Actions → BSD V2 - Validation experimentale → Run workflow; vérifier 2026 et quality-policy.
2. Actions → BSD V2 - Shadow daily (experimental) → Run workflow en mode reliability.
3. Le lendemain ou après maturation, Actions → BSD V2 - Settle shadow predictions; vérifier les résultats.
4. Si le compte a accès au multi-bookmaker BSD, choisir la source bookmaker explicite; sinon conserver «consensus».
5. Ne basculer sur le site qu'après comparaison stable de résultats prospectifs et contrôles de cotes.

Aucune commande de publication n'est ajoutée à ces workflows.
