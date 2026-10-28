# BSD V2 — hiérarchie des sources de cotes (28/10/2026)

**Critère de classement :** provenance identifiable, correspondance exacte avec le match et le marché, fraîcheur contrôlable, couverture et disponibilité constatées. Ce classement est une **politique prudente de priorité**, et non un taux de réussite statistique des pronostics ni une garantie de prix exécutable.

La prédiction choisit d'abord son marché à partir de l'historique football. Elle demande ensuite une cotation **du même marché et du même match** dans l'ordre ci-dessous. Une source qui ne couvre pas le marché, est périmée ou échoue est ignorée. L'algorithme ne retient plus arbitrairement la cote maximale d'une source moins traçable. Une source haute priorité indisponible n'empêche jamais un prix inférieur dans la hiérarchie.

| Priorité | Origine (`odds_source`) | Base du classement et conditions |
|---|---|---|
| 1 | `pinnwire` | Flux prématch des prix Pinnacle, via PinnWire. Exige `generated_at` racine du snapshot REST datant de 120 s maximum, phase prématch et marché temps plein explicite. L'heure individuelle du dernier changement de prix n'est **pas connue** ; l'étiquette `quote_timestamp_type=provider_snapshot` le précise. |
| 2 | `oddslink` | Cotes décimales d'un bookmaker déclaré et horodatées par bookmaker/marché. API avec clé actuellement configurée sur l'EPL uniquement. |
| 3 | `oddslink_public` | Tableau sans clé, bookmaker de type `sportsbook` avec `last_update` connu, cote américaine convertie en décimale. Couverture limitée à 60 matchs / fenêtre de 36 h. |
| 4 | `moviodds` | API publique, nom d'équipes, horaire, phase prématch, catégorie et horodatage du relevé exigés ; origine du bookmaker moins précisément documentée. |
| 5 | `goaldir` | Source historique BSD / consensus, marché et timestamp connus ; agrégation plutôt qu'offre d'un bookmaker individuel. Retourne `bsd_consensus` ou `bsd_bookmaker`. |
| 6 | `oddsharvester` | Snapshot local facultatif; aucune extraction automatique; le fichier doit être explicitement configuré, horodaté et associé au même match. |
| 7 — **dernier recours** | `mrxpronos_model` | Cote estimée par les probabilités du modèle + hypothèse de marge, **pas** une cotation bookmaker. Toujours signalée `estimated_odds=true`. |

## Mesures HTTP réellement observées

Le 28/10/2026, workflow GitHub Actions `40707142651` : HTTP 200 pour 4 fournisseurs; sur les fixtures échantillonnées (au plus 250 par fournisseur), OddsLink public : 5 prix frais, MoviOdds : 474, OddsLink avec clé : 79, PinnWire : 2161 prix décodés mais **aucun validé** par l'ancien adaptateur (celui-ci cherchait `last_odds_update` par match, absent du schéma documenté). Le nouveau code vérifie le snapshot racine `generated_at`. **La validation du nouveau code exige un nouveau smoke-test réel**, avec un compteur distinct des prix fondés sur un snapshot versus une modification de cote propre à un marché.

Les nombres ci-dessus mesurent disponibilité et parsing, **pas** la proximité des prix avec les bookmakers locaux (1xBet, etc.), la stabilité chronologique ni les performances économiques.

## Mesures et garde-fous en production

- Chronométrage : comparer les prix à l'heure de la requête réelle, et non à l'heure de démarrage d'une génération qui peut durer plusieurs minutes.
- Refus : HTTP 401/403/429, mauvais match, heure d'événement non concordante, marché ou seuil non identique, match en cours, prix absent ou hors plage, horodatage trop ancien.
- PinnWire : un snapshot récent n'est **pas** une preuve que le prix individuel a changé récemment. Le champ `per_market_update_verified=false` est conservé.
- Ne jamais confondre rang de source, probabilité de réussite du pari et rendement attendu.
- Observer en production : nombre de cotes exploitables par fournisseur, part des matchs qualifiés avec chaque source, taux de repli sur le modèle, quotas, erreurs réseau et prix qui cessent d'être disponibles.

Documentation officielle de référence : https://pinnwire.com/docs.html et https://oddslink.app/docs/api-reference/operations/publicboard/
