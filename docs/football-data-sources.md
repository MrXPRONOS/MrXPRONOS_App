# Sources de données football — Mr XPRONOS

Mise à jour : 13 octobre 2026.

## Principe

Mr XPRONOS utilise plusieurs fournisseurs et choisit la source **par type de donnée**. Aucun fournisseur gratuit n'est supposé complet sur tous les championnats. Les identifiants BSD historiques restent ceux du moteur de calibration ; les autres sources servent à réduire les appels BSD, enrichir les données, confirmer les faits et assurer les fallbacks.

## Classement global actuel

| Rang | Source | Qualité globale | Live | Détail match | Couverture | Cotes automatisables |
|---|---|---:|---:|---:|---:|---:|
| 1 | ESPN | 98 | 99 | 99 | 91 | Non |
| 2 | SportScore | 92 | 95 | 93 | 96 | Non documenté |
| 3 | BSD V2 | 89 | 91 | 91 | 98 | Oui |
| 4 | TheSportsDB | 79 | 55 | 82 | 73 | Non |
| 5 | OpenLigaDB | 76 | 66 | 69 | 54 | Non |

Ces notes sont des poids internes de routage Mr XPRONOS, pas des scores officiels des fournisseurs.

## Ordre de préférence par donnée

- Score / état live : ESPN → SportScore → BSD → TheSportsDB → OpenLigaDB.
- Timeline, buteurs, minute du but : ESPN → SportScore → TheSportsDB → BSD.
- Compositions : ESPN → SportScore → TheSportsDB. Publication uniquement avec 11 titulaires confirmés de chaque côté.
- Statistiques live : ESPN déjà présent dans le scoreboard → SportScore detail → TheSportsDB event stats → BSD /stats/.
- Programme éditorial : fusion ESPN + SportScore + TheSportsDB + OpenLigaDB ; BSD devient fallback si la couverture gratuite est insuffisante.
- Forme récente : SportScore en premier, BSD en fallback.
- H2H avant-match : SportScore en premier lorsqu'au moins trois confrontations fiables sont disponibles ; BSD/historique local en fallback.
- Historique de calibration et IDs du modèle : BSD reste la référence.
- Cotes pré-match validées : BSD reste la source automatisée.
- Cotes live : uniquement une source explicitement configurée et documentée dans LIVE_PROP_ODDS_URL.

## Réduction des appels BSD

1. Une journée éditoriale utilise d'abord les quatre fournisseurs gratuits.
2. Le refresh LIVE récupère ESPN, SportScore, TheSportsDB et OpenLigaDB avant l'appel BSD.
3. L'appel BSD /events/live/ peut être évité lorsque ESPN **et** SportScore couvrent chacun au moins le nombre total de matchs live annoncé par le endpoint de couverture BSD.
4. Pour les stats détaillées, SportScore puis TheSportsDB sont essayés avant BSD /events/{id}/stats/.
5. Les appels BSD de forme récente sont évités si SportScore fournit au moins cinq matchs terminés pertinents.
6. Les appels BSD H2H sont évités si SportScore fournit au moins trois confrontations fiables.
7. Le cache reste prioritaire pour ne pas rappeler un fournisseur inutilement.

## SportScore et les cotes

Le site SportScore affiche des informations de paris et des cotes sur certaines pages. Cependant, au 13 octobre 2026, le contrat REST public documente les fixtures, résultats, détails de match, lineups, timeline, H2H, équipes, classements et meilleurs buteurs, mais **pas un endpoint ou un schéma de cotes**.

Mr XPRONOS inspecte donc les réponses match SportScore pour détecter explicitement des sections `odds`, `markets`, `betting_markets`, `live_odds` ou `prematch_odds`. Cette détection est diagnostique uniquement :
- `contract_verified = false`;
- elle ne peut pas alimenter automatiquement un pari ;
- l'activation expérimentale nécessite `SPORTSCORE_ALLOW_UNDOCUMENTED_ODDS=1`.

Tant qu'un contrat API de cotes n'est pas documenté et vérifié, BSD ou un fournisseur de cotes explicitement configuré reste la source de prix.

## Limites gratuites connues

- SportScore : accès REST public sans clé avec attribution visible obligatoire ; cache edge et limites d'usage du fournisseur.
- TheSportsDB : clé publique V1 `123`, 30 requêtes/minute pour le tier gratuit, plusieurs endpoints limitent le nombre de résultats.
- OpenLigaDB : sans clé ; politique d'usage raisonnable autour de 60 requêtes/minute/IP.
- ESPN : endpoints publics utilisés sans contrat commercial ; ils doivent rester protégés par cache, retry, budgets et fallbacks.
- BSD : quota à préserver ; utilisé en dernier recours quand les sources gratuites suffisent.

## Attribution SportScore

Les pages publiques utilisant les données partagées affichent un lien visible **Powered by SportScore** vers https://sportscore.com/. Le lien n'est pas marqué nofollow.
