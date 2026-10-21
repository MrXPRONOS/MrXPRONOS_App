# Mr XPRONOS — inventaire et contrôle de migration LIVE Render

Date : 2026-10-21. Référence : `main:supabase/functions/live/index.ts`.
Blob Git GitHub d'origine : `36c0f2b2b9c4a24e62e03e83f5f4818849af16e2`.
Moteur source : environ 9 422 lignes / 249 fonctions nommées.
**Invariance :** `render/live/verify_engine.ts` reconstitue le fichier d'origine en retirant l'unique adaptation de transport interne Render. Il compare le SHA-1 Git blob au code `main`. Tout changement supplémentaire de règle échoue le build.

## Statuts (à ne pas confondre)

- **CODE CONSERVÉ** : implémentation d'origine strictement identique, contrôlée au build.
- **TEST À EFFECTUER** : code transporté, mais pas de test réel bout en bout validé sur Render.
- **NON BASCULÉ** : production utilise encore les anciennes routes et les anciens crons.
- **NON INCLUS** : autre Edge Function indépendante non comprise dans ce service.

## A — Moteur statistique, modèles et règles

| ID | Fonctions / règle contrôlable | Valeur / comportement exact | État du code | Test réel Render |
|---|---|---|---|---|
| A01 | `computeMomentum` | tirs ×2, tirs cadrés ×3, corners ×1,5, possession ×0,15 ; domination 58% | CODE CONSERVÉ | À EFFECTUER |
| A02 | `getMatchFlow` | pression 2×tirs cadrés + 1,4×corners + 0,08×écart possession + 0,12×momentum ; rythme/minute | CODE CONSERVÉ | À EFFECTUER |
| A03 | `conservativeProjection` | vitesse observée extrapolée jusqu'à 90'; coef offensif 0,82, neutre 0,70, défensif 0,52 ; pénalité 70' et 78' ; plancher 0,35 ; cap corners +4, tirs/fautes +8 | CODE CONSERVÉ | À EFFECTUER |
| A04 | `poissonTail` | probabilité de dépasser le seuil selon moyenne des événements restants ; borne [0,005, 0,995] | CODE CONSERVÉ | À EFFECTUER |
| A05 | `candidateProbability` | Poisson 72% + heuristique 18% + neutre 10%; recalage avec fiabilité; borne [0,18, 0,94] | CODE CONSERVÉ | À EFFECTUER |
| A06 | `estimatedModelOdds` | 1 / probabilité; **jamais étiqueter comme cote bookmaker réelle** | CODE CONSERVÉ | À EFFECTUER |
| A07 | `LIVE_MARKET_LINES` | Corners 7,5→13,5 ; tirs 15,5→33,5 ; fautes 17,5→31,5 selon grilles originales | CODE CONSERVÉ | À EFFECTUER |
| A08 | `getLineCandidates` | différence seuil − actuel ≥2 et seuil ≤ projection + buffer (corners 1,5, tirs 6, fautes 3) | CODE CONSERVÉ | À EFFECTUER |
| A09 | `legacyBaselineThreshold` | référence historique obligatoire pour tirs et corners ; `projected >= threshold + 0.5` | CODE CONSERVÉ | À EFFECTUER |
| A10 | `historicalUpliftCap` | tirs : +6 avant 30', +5 avant 45', +2 avant 60', +1 avant 75', sinon 0 ; corners : +1 à 30–44', sinon 0 ; fautes null | CODE CONSERVÉ | À EFFECTUER |
| A11 | `playabilityUpliftCap`, `minimumPlayableProbability`, `minimumPlayableHeadroom` | plafonds/qualité/headroom par minute et marché | CODE CONSERVÉ | À EFFECTUER |
| A12 | `buildPlayabilityEnvelope` | élimination des lignes dépassant plafonds, probabilités minimum, marge projection, fiabilité/qualité | CODE CONSERVÉ | À EFFECTUER |
| A13 | `selectMarketFacingCandidate` | ligne la plus haute restante dans l'enveloppe jouable | CODE CONSERVÉ | À EFFECTUER |
| A14 | `signalTierFromModelOdds` / `passesTierQuality` | Quality 1,45–1,75 (P≥56%, fiab≥68, qual≥67) ; Value >1,75–2,30 (P≥43%, fiab≥72, qual≥67) ; High Value >2,30–3,20 (P≥31%, fiab≥78, qual=100) | CODE CONSERVÉ | À EFFECTUER |
| A15 | Restrictions niveau | High Value interdit pour corners/fautes en attente de calibration | CODE CONSERVÉ | À EFFECTUER |
| A16 | `predictTotalCorners` | seulement données corners des deux équipes ; minute 18–82 ; déjà ≥3 corners ; fiabilité minimale 63, 78 en 45'–59' | CODE CONSERVÉ | À EFFECTUER |
| A17 | `predictTotalShots` | tirs complets ; minute 15–83 ; déjà ≥6 tirs ; fiabilité ≥64 | CODE CONSERVÉ | À EFFECTUER |
| A18 | `predictTotalFouls` | fautes complètes ; minute 18–84 ; déjà ≥6 fautes ; fiabilité ≥62 | CODE CONSERVÉ | À EFFECTUER |
| A19 | `predictionDataQuality`, `applyPredictionQualityContext` | score de complétude par marché ; accord et confiance sources ; pénalité si âge >180 s / >300 s ; requalification du tier | CODE CONSERVÉ | À EFFECTUER |
| A20 | `computeAiScore`, `computeValueScore`, `computeHeatLevel` | scoring heuristique, valeur, niveaux heat dans le site | CODE CONSERVÉ | À EFFECTUER |
| A21 | `LIVE_VALUE_MODEL_VERSION` | `live-value-v2.3-playability-envelope` | CODE CONSERVÉ | À EFFECTUER |
| A22 | `fetchExternalLivePropOdds`, `alignPredictionToAvailableBookmakerLine`, `computeLiveCouponPricing` | Cotes externes facultatives ; edge + EV ; fallback cote modèle ; distinguées | CODE CONSERVÉ | À EFFECTUER |

## B — Acquisition / consolidation / filtrage des données

| ID | Fonction | Code | Test réel |
|---|---|---|---|
| B01 | Source BSD : événements live + stats détaillées, contrôle quotas / réserve / TTL | CODE CONSERVÉ | À EFFECTUER |
| B02 | ESPN : scoreboard date(s), résumés, cache partagé, budget et backoff (module partagé) | CODE CONSERVÉ | À EFFECTUER |
| B03 | SportScore live + détails, temporisations entre rafraîchissements | CODE CONSERVÉ | À EFFECTUER |
| B04 | TheSportsDB, OpenLigaDB et sources de fallback gratuites | CODE CONSERVÉ | À EFFECTUER |
| B05 | MoviOdds statistiques observées, caches API Football, données cotes directes/agrégées facultatives | CODE CONSERVÉ | À EFFECTUER |
| B06 | Normalisation des statistiques : `null` ≠ 0, paires home/away, totaux | CODE CONSERVÉ | À EFFECTUER |
| B07 | Match canonique, similarité équipes/ligue/date, refus d'inversion des équipes | CODE CONSERVÉ | À EFFECTUER |
| B08 | Priorités statistiques BSD/ESPN, merge multisource, accord, source confidence | CODE CONSERVÉ | À EFFECTUER |
| B09 | Déduplication des sources et lignes fusionnées avant UPSERT PostgreSQL | CODE CONSERVÉ | À EFFECTUER |
| B10 | Stockage `matches_live`, `live_stats_sources`, `live_stats_merged`, `espn_match_map` et snapshots | CODE CONSERVÉ | À EFFECTUER |

## C — Transaction, qualité et distributions

| ID | Fonction | Code | Test réel |
|---|---|---|---|
| C01 | `savePrediction` INSERT-only, idempotence, collision unique, snapshot valeur/cote/score/minute | CODE CONSERVÉ | À EFFECTUER |
| C02 | Vérification / correction instantanée des seuils réalisés en cours de match | CODE CONSERVÉ | À EFFECTUER |
| C03 | Résolution résultats finaux ESPN/BSD, validations différées + backlog, règlement et notifications | CODE CONSERVÉ | À EFFECTUER |
| C04 | `claim_live_refresh`, `renew_live_refresh`, `release_live_refresh` : bail anti-chevauchement DB | CODE CONSERVÉ | À EFFECTUER |
| C05 | 5 matchs par lot ; maximum 20 lots par défaut ; curseur sauvegardé / reprise | CODE CONSERVÉ | À EFFECTUER |
| C06 | **Seul changement de moteur :** `invokeRefreshBatch` peut cibler `LIVE_BATCH_ENDPOINT` local. Auth et tous les calculs inchangés | TRANSPORT ADAPTÉ | À EFFECTUER |
| C07 | Envoi image Telegram + texte secours, deux canaux, reprises/anti-doublon et suivi des tentatives | CODE CONSERVÉ | À EFFECTUER |
| C08 | Polices locales et rendus Resvg/Satori, bannières sponsors, logos et images | CODE CONSERVÉ | À EFFECTUER |
| C09 | Routes public `/matches`, `/opportunities`, `/today`, `/predictions/history`, `/predictions/by-id`, `/notifications` | CODE CONSERVÉ | À EFFECTUER |
| C10 | `/refresh`, `/refresh/batch`, `/validate`, `/telegram/process-one`, `/daily/generate`, `/daily/validate` | CODE CONSERVÉ | À EFFECTUER |
| C11 | `/daily/today`, backtest headroom, statistiques sources et agrégation, synchronisation des rencontres à venir | CODE CONSERVÉ | À EFFECTUER |
| C12 | Fonction Edge indépendante `telegram-live` : même code, port local 8001, route `/telegram-live` | TRANSPORT ADAPTÉ ; code métier conservé | À EFFECTUER |
| C13 | Site GitHub Pages et six workflows Cron externes actuels | NON BASCULÉ | NON BASCULÉ |

## D — Architecture de bascule

- Image : `render/live/Dockerfile` utilisant Deno ; les sources originales et polices sont copiées sans modification.
- Façade HTTP `render/live/server.ts` : proxy transparent 10000 → Deno original sur 8000, avec `/healthz` et `/audit`.
- **Standby par défaut** : ne jamais produire de prédiction ou envoyer Telegram tant que `RENDER_LIVE_ENABLED=1` et quatre variables obligatoires ne sont pas configurées. Même après activation technique, `RENDER_LIVE_READONLY=1` bloque les POST jusqu’à la bascule explicitement choisie.
- Fonction indépendante `telegram-live/index.ts` : port interne 8001, via `RENDER_DEDICATED_TELEGRAM` (actif par défaut si moteur activé) ; ses règles sont intactes sauf la ligne de bind. Un second SHA Git strict est contrôlé au build.
- Variables minimales à configurer dans Render (en secret, jamais dans GitHub) : `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `BSD_API_TOKEN`, `CRON_SECRET`.
- Variables fonctionnelles à reproduire selon configuration en production : `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_CHAT_ID_SECONDARY`, `DEBUG_KEY`, `SITE_URL`, `BSD_TZ`, `ENABLE_ESPN_MERGE`, `LIVE_PROP_ODDS_URL`, `LIVE_PROP_ODDS_TOKEN`, `LIVE_REQUIRE_BOOKMAKER_LINE`, `LIVE_ODDS_*`, `MOVIODDS_API_KEY` et réglages de quotas/TTL/batches.
- Le stockage PostgreSQL, les tables et fonctions RPC restent chez Supabase (cela déplace le moteur de calcul, pas la base de données).
- En production, déplacer chaque **appel cron** vers le service Render seulement après test exhaustif ; éviter double rafraîchissement Supabase Edge + Render.
- Render Free : la suspension après inactivité et les plafonds CPU/RAM empêchent de garantir 24/7 une cadence d'une minute. Un appel entrant cron toutes les minutes doit être piloté de l'extérieur et surveillé.
- Tests de recette bloquants : import Deno et dépendances, port web, environnement secret, DB lecture, 1 lot en préproduction sans Telegram, >50 matchs et statistiques, calculs équivalents, inserts / anti-doublons, Telegram x2, validation et site, failover & backout.
- **Ne pas activer les écritures ou les crons tant que les tests de recette ne sont pas réussis.**
