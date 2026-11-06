# BSD V3 - audit d'implementation au 6 novembre 2026

Statut global: **PARTIEL - version initiale de recherche sur branche dédiée**.
Le plan de 140 actions ne peut pas être déclaré entièrement exécuté.
Aucune publication sur le site et aucun envoi Telegram depuis BSD V3.

| Phase du plan | État | Livré sur la branche | Reste non démontré / non achevé |
|---|---|---|---|
| 1. Architecture 1-10 | Partiel avancé | Package séparé, branche, CI, workflow manuel en lecture seule | Intégration de stockage persistant inter-exécutions, audit de toutes dépendances |
| 2. Données 11-24 | Partiel | Historique chiffré BSD réutilisé, client BSD et sources gratuites conservés, index temporel V2 | Provenance historique fine par champ, nettoyage multi-fournisseurs, autres caractéristiques optionnelles |
| 3. Qualification 25-32 | Partiel | Refus forme courte, ancienneté, historique ligue; niveaux full/limited/rejected | Validité fournisseur par fournisseur et couverture explicite de chaque caractéristique |
| 4. Modèles 33-48 | Partiel | Poisson/Dixon-Coles, modèles V2 spécialisés en challengers diagnostics facultatifs | Gains prédictifs 1X2/Over/BTTS démontrés, nouveaux modèles entraînés et acceptés |
| 5. Calibration 49-60 | Partiel | Calibration 2025 chronologique avec garde, projection jointe, vérifications cohérence | Intervalles statistiques rigoureux, tests de stabilité et validation multi-ligues |
| 6. Sélection 61-69 | Avancé (non homologué) | 16 sélections, familles distinctes, critères Pro/VIP 79 % + exigences historiques, Value séparé | Validation quantitative du comportement sur grands historiques |
| 7. Cotes 70-83 | Partiel | API BSD gratuite par match multi-marchés, contrôles prix/temps/origine | Comparaison exhaustive des fournisseurs gratuits, disponibilité pratique des cotes, volume suffisant de cotes bookmaker nommées |
| 8. Circuits 84-95 | Partiel | Pro/VIP shadow, Value Shadow uniquement cotes bookmaker nommées, contrôle corrélation | Publication approuvée, mesure prospective de qualité, coupons et seuil Telegram |
| 9. Historique 96-107 | Partiel | JSON d'observation, journal JSONL append-only chaîné, règlement séparé, Brier et ROI sur cotes réellement enregistrées | Persistance durable entre workflows, règlement automatique, tableau de bord complet |
| 10. Backtests 108-118 | Partiel | Test chronologique 2026 vs baseline cohérente, Brier/log-loss, aucun ROI fictif | Comparaison complète V2 en conditions identiques, mesures de significativité et observation indépendante |
| 11. Tests 119-129 | Partiel | Tests hors-ligne et CI GitHub pour cohérence, prix, politiques, anti-fuite temporelle, immutabilité | Tests de charge, panne API réelle, grands échantillons, non-régression exhaustive V2 |
| 12. Observation / déploiement 130-140 | Partiel (laboratoire) | Workflow manuel shadow, artifact 90 jours, permissions read-only | Exécution réelle avec secrets, suivi régulier, contrôle des dérives, activation contrôlée et retour arrière en production |

## Travaux réellement validés
- La CI du moteur V3 compile Python et lance les tests hors ligne.
- Les fichiers originaux de BSD V2 ne sont pas modifiés dans cette PR.
- Les écritures expérimentales sont limitées à bsd_v3/artifacts ; les données historiques déchiffrées restent hors des artefacts.
- La sortie V3 affiche experimental=true, published=false.

## Travaux non validés
- Le déclenchement manuel avec clés GitHub et archive privée n'a pas encore été exécuté depuis cette PR.
- Le chiffre de 79 % est un critère de confiance déclaré, et NON un taux de réussite garanti.
- Aucun résultat économique réel ou rendement historique n'a été établi.
- La conformité complète aux 140 actions du cahier des charges n'est pas démontrée.

## Politique de livraison
Conserver la PR en brouillon, sans fusion automatique. Chaque action restante doit être livrée avec preuve vérifiable (test, diagnostic ou résultat prospectif), pas seulement une description de ce qui devrait exister.
