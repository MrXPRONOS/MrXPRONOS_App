# Audit de correction des 6 anomalies — Dixon-Coles V1.2

**Périmètre** : `dixon-coles/` uniquement, dépôt `MrXPRONOS/MrXPRONOS_App`.
**Principe** : aucun fichier ou moteur de l'ancien système de pronostics n'est réutilisé ni modifié.

| Nº | Anomalie identifiée | Correction apportée | Vérification | Limite restante |
|---|---|---|---|---|
| 1 | Un import pouvait rétrograder `FINISHED` et supprimer le score | Mise à jour atomique avec préservation du score final, refus d'un score contradictoire, journal de correction explicite et migration SQLite | Tests « finished never downgraded », « rollback », « audited correction », « migration » | Les corrections légitimes doivent être approuvées manuellement, par conception |
| 2 | Serveur exploitable sans authentification | Authentification des routes API distantes, mode public nécessitant jeton fort, contrôle de l'origine, limite simple par IP, en-têtes de sécurité, refus de liaisons externes mal configurées | Test `DCSCORE_PUBLIC_MODE=1`, accès anonyme 401, jeton valide 200, Origin/cross-site 403 | Pour Internet : proxy HTTPS, pare-feu, rate limiting distribué et secrets d'hébergement à configurer ; **aucun serveur public n'est déployé** |
| 3 | Données réelles non encore validées | OpenFootball CC0, historique réel et source identifiable, avertissement de fraîcheur ; workflow dédié d'import et backtest réels | Calibration xi antérieure : import public réussi sur GitHub ; nouveau workflow effectue 500 matchs réels | Validé pour OpenFootball Premier League uniquement ; `football-data.org` exige une clé privée pour un test réel ; actualisation dépend du fournisseur |
| 4 | Backtest limité à 30 matchs et benchmark biaisé | De 1 à 3000 matchs, refits mensuels strictement chronologiques, Poisson *séparément optimisé* avec `rho=0`, log loss, Top1/Top3, Brier 1N2, tranches de calibration | Test 40 matchs sans fuite, tests du modèle indépendant, workflow de 500 matchs réels | Les performances historiques ne garantissent pas les performances futures ; des compétitions nécessitent des données suffisantes |
| 5 | `ξ` historique jamais optimisé sur des résultats réels | Fonction déjà publiée précédemment : 8 candidats testés, 374 matchs de validation 2024-25, 374 en holdout 2025-26, rapport versionné et application aux prédictions | GitHub Actions réel terminé avec succès, 35 tests puis 47 tests locaux incluant le rapport | `ξ` optimisé pour la Premier League seulement. Optimisation à refaire championnat par championnat |
| 6 | Provenance de scores et terrains neutres mal représentés | `result_provenance` pour chaque score, propagation au journal et backtest, booléen `neutral_venue` importable par CSV/sélection, `γ=1` pour terrain neutre ; rectification de lieu auditée | Tests de provenance, CSV, modèle neutre et correction de lieu avec historique | Si le fournisseur ne signale pas un terrain neutre, le logiciel ne peut pas le deviner |

## Vérification locale

Exécuter depuis `dixon-coles/` :

```bash
python -m pip install -e '.[test]'
python -m pytest -q
node --check dcscore/static/app.js
```

Le contrôle avant publication compte **47 tests réussis localement**. Ce rapport ne doit pas être confondu avec le contrôle GitHub distant, à vérifier depuis l'onglet Actions du dépôt.

## Principes de sécurité et d'interprétation

- Les sources tierces fournissent des scores *déclarés*, **pas certifiés indépendamment**.
- En mode local, le programme reste une application privée ; pour une connexion via un proxy sur le même hôte, définir explicitement `DCSCORE_PUBLIC_MODE=1` et un jeton fort pour éviter le contournement par l'IP locale du proxy.
- L'ancien workflow des prédictions du dépôt principal n'est pas modifié.
- Le rapport `ξ` versionné vérifie le coefficient **pour la Premier League seulement**.
- La protection contre les corrections silencieuses est délibérée : lorsqu'une source change un résultat, un administrateur doit corriger avec une raison plutôt que d'accepter silencieusement un nouveau score.
