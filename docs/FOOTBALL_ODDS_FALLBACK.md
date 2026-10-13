# Mr XPRONOS — chaîne de cotes à cinq sources (branche de validation)

## Statut
**Code raccordé**, **sources externes à valider avant mise en production**. 
Aucun jeton d'accès n'est inclus dans le dépôt. Aucun bookmaker n'est présenté comme
la source d'un prix sans correspondance stricte du marché.

## Ordre de repli
Le quotidien BSD V2 tente GoalDir/BSD consensus (déjà présent), puis
PinnWire, OddsLink, MoviOdds et l'instantané local OddsHarvester.
Une réponse vide, un mauvais match, un refus ou une erreur n'efface
pas les pronostics ; sans prix réel le moteur conserve ses règles
actuelles pour les estimations explicitement identifiées.

Le LIVE essaie MoviOdds, PinnWire, OddsLink, GoalDir, OddsHarvester
puis le fournisseur LIVE_PROP_ODDS_URL déjà configuré (s'il existe).
Les fournisseurs non compatibles avec les paris in-play sont ignorés en l'absence
d'un pont HTTP explicite et valide.

## Configuration GitHub Actions (quotidien)
- PINNWIRE_API_KEY : secret facultatif ; s'il manque, source ignorée.
- ODDSLINK_API_KEY : secret facultatif ; s'il manque, source ignorée.
- BSD_API_KEY : secret existant, conservé.
- ODDSHARVESTER_JSON : chemin facultatif d'une extraction JSON autorisée, contenant
  une date de capture et l'identité des équipes. **Aucun scraping automatique ajouté**.
- MoviOdds : lecture publique expérimentale ; vérifier l'API et les droits de
  réutilisation commerciale avant son activation en production.

Les URL fournisseurs sont expérimentales et nécessitent une vérification avec des
réponses JSON réelles avant de les utiliser pour valider des coupons.

## Configuration Supabase Edge (LIVE)
Pour les fournisseurs activés, configurer la paire de variables d'environnement
`LIVE_ODDS_{PROVIDER}_URL` et, si nécessaire, `LIVE_ODDS_{PROVIDER}_TOKEN`.
PROVIDER = MOVIODDS / PINNWIRE / ODDSLINK / GOALDIR / ODDSHARVESTER.
Une URL doit pointer vers un endpoint HTTPS JSON qui renvoie **une cote de match
vérifiée**, normalisée avec :

```json
{
  "match_id": "id-identique-a-celui-du-live",
  "market": "total_corners",
  "line": 8.5,
  "odds": 1.8,
  "phase": "live",
  "updated_at": "2026-10-13T15:00:00Z"
}
```
À défaut de match_id exact, fournir home_team, away_team et kickoff
(UTC) pour vérification des identités. L'heure d'observation doit dater de
120 secondes ou moins. Cotes sans ligne explicite, suspendues, trop
anciennes ou de marché différent sont refusées.

Limites prudentes configurables : `LIVE_ODDS_{PROVIDER}_DAILY_LIMIT`.
Le suivi des appels LIVE est **par instance Edge**, pas global :
pour un budget strict mondial, remplacer ce compteur par un quota atomique
Supabase ou un proxy centralisé avant production.

**Attention :** ce routeur ne crée pas les cinq comptes, ne génère aucune clé,
et n'active pas des endpoints non vérifiés. OddsLink gratuit n'est pas une
source in-play ; la gratuité de MoviOdds peut être temporaire.

## Tests
`python -m unittest discover -s bsd -p 'test_odds_fallback.py' -v`

## Déploiement
Conserver cette branche en revue jusqu'à réception de sorties réelles pour les
fournisseurs prévus. Ne pas fusionner avant que l'intégration live, les
statuts HTTP, le rapprochement des événements et les quotas partagés aient
passé une vérification en environnement de test.
