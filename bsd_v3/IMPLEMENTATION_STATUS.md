# BSD V3 — rapport de réception du développement

Projet : `MrXPRONOS/MrXPRONOS_App`
Branche : `feat/bsd-v3-shadow-engine`
Pull request : [#303](https://github.com/MrXPRONOS/MrXPRONOS_App/pull/303)

**Conclusion : implémentation technique avancée, validation réelle encore PARTIELLE.**
Le plan de 140 actions n'est pas honnêtement déclarable comme entièrement
terminé tant que les conditions dépendant de l'avenir (validation prospective,
cotes vérifiables, déploiement réel) n'ont pas été observées.

## Matrice de réception

| Groupe du plan | Réalisé en code | Validation vérifiée | Ce qui reste pour pouvoir dire « complet » |
|---|---|---|---|
| 1. Architecture (1–10) | Dossier V3 indépendant, aucune écriture V2, workflow et CI | Tests CI et diff PR ciblé | Vérifier manuellement l'installation et la continuité des artefacts lors de deux exécutions réelles |
| 2. Données (11–24) | Archive chiffrée réutilisée, contrôles doublons/IDs/scores/date, adaptateurs gratuits conservés | Cas synthétiques de conflits, archives et absence de fuite temporelle | Mesurer réellement la couverture et la provenance par champ ; les sources ne garantissent pas blessures et compositions |
| 3. Qualification (25–32) | Niveaux full/limited/rejected, motifs de refus, exigences d'historique et de fraîcheur | Tests de cas d'échec et de match analysable | Mesurer les taux de rejet par compétition sur les véritables archives |
| 4. Modèles (33–48) | Poisson/Dixon-Coles ; V3 Elo-goal avec sélection sur 2025 ; modèles 1X2, Over/Under, BTTS existants en challengers cohérents | Projection de probabilités et non-fuite des résultats futurs | Établir un gain quantitatif indépendant et une stabilité multi-compétitions ; refuser tout challenger non gagnant |
| 5. Calibration (49–60) | Calibration jointe, contraintes 1X2/BTTS/DC/totaux, garde chronologique, incertitude empirique | Tests d'invariants mathématiques et de seuils | Démontrer la calibration prospective sur des échantillons suffisants et des intervalles statistiques correctement caractérisés |
| 6. Sélection (61–69) | 16 marchés comparés sans quota ; qualité par candidat ; Pro/VIP et Value séparés ; absence de sélection autorisée | Tests familles, seuil 79%, conditions historiques, contrôles dérive | Vérifier la capacité et la qualité réelle par championnat et marché |
| 7. Cotes (70–83) | BSD gratuit multi-marchés ; tableau gratuit optionnel ; exactitude marchés, horodatage, origine, marges de sécurité | Tests d'API simulée, mauvais match, cote périmée, consensus indicatif | Mesurer la disponibilité réelle des cotes, la qualité et l'accès aux bookmakers au Togo ; l'accès à un prix n'est pas garanti |
| 8. Circuits (84–95) | Pro/VIP shadow, Value Shadow, deux familles, corrélation, anciens veto BTTS/H2H contrôlés | Tests prix réels/estimés, famille unique, interdiction de publication | Confirmer longitudinalement les seuils et les exclusions avant toute diffusion ; adapter le site/Telegram uniquement après validation |
| 9. Journal et résultats (96–107) | Journal SHA256 chaîné, décisions figées, règlement séparé, suivis par marché/famille/ligue, coupe-circuit | Tests immutabilité, duplications, règlement et monitor | Valider deux exécutions GitHub successives, conservation au-delà de 90 jours et récupération après panne |
| 10. Backtests (108–118) | Comparaison V2/V3 appariée, Brier/log-loss, Wilson, 2026 rétrospectif ; aucun ROI inventé | Test de comparaison sur historique synthétique | Rapport réel sur 2024–2026 déchiffré avec effectifs ; une période prospective indépendante reste obligatoire |
| 11. Tests (119–129) | CI indépendante : tests V3 et trois suites critiques V2 | **23 tests V3 + 38 tests V2 réussis** dans une exécution CI | Tests de charge/quotas réels, erreurs des fournisseurs, validation de toutes les fonctionnalités extérieures |
| 12. Observation et diffusion (130–140) | Workflow manuel V3 (shadow/evaluate/compare/settle) sans droit d'écriture dépôt et sans Telegram | Workflow YAML et tests hors réseau ; aucune modification de production V2 | Workflow secret-enabled non déclenché ; observation réelle, gain démontré, activation/rétrogradation publique non réalisées |

## Limites qui ne peuvent pas être « codées » ni déclarées réussies aujourd'hui

1. **Résultats futurs inconnus** : pour prouver qu'un modèle est mieux calibré ou moins risqué, il faut enregistrer maintenant ses pronostics puis attendre des matchs réels terminés. Les backtests rétrospectifs seuls ne suffisent pas.
2. **Cotes de vrais bookmakers** : BSD consensus et tableau public ne garantissent pas un prix accessible au Togo, une limite de mise ou la possibilité de parier. Les statistiques de ROI sont uniquement théoriques, basées sur cotes capturées, jamais sur une mise réellement effectuée.
3. **Historique chiffré** : les tests GitHub sur la PR ne déchiffrent pas les données privées sans `BSD_HISTORY_KEY`. Les évaluations de volume réel demandent une exécution d'un workflow autorisé avec les secrets.
4. **Mode public V3** : par choix de sécurité, il n'existe aucune commande pour écrire dans le site/Telegram. L'activation est une étape distincte, nécessitant une validation des performances et une décision de migration explicite.
5. **Persistance GitHub** : la chaîne d'artéfacts peut conserver les résultats entre exécutions, mais chaque artefact a une rétention de 90 jours. Une conservation permanente n'est pas prouvée.
6. **Données externes facultatives** : blessures, compositions, frais/bookmakers spécifiques, limites d'accès, coût des API ne sont pas inventés lorsqu'aucune source fiable et gratuite n'existe.

## Procédures de validation

- CI sur PR : syntaxe Python, tests V3 et sous-ensemble de non-régression V2.
- Modes manuels réservés à la branche principale après fusion du seul code V3 :
  - `shadow` : capturer des prévisions avant les rencontres ;
  - `evaluate` : rapports rétrospectifs ;
  - `compare` : comparaison V2/V3 à matchs identiques, sans inventer de cotes historiques ;
  - `settle` : vérifier le règlement des prévisions enregistrées et la dérive.
- La PR reste brouillon et non fusionnée. La fusion du code ne peut pas être interprétée comme une publication V3.

## État du code et des preuves

- Aucun nouveau service payant introduit.
- Aucun fichier du moteur BSD V2, du site ou de Telegram modifié.
- Les nouveaux modules ne revendiquent ni amélioration garantie ni taux de réussite de 79 %.
- Les protections BTC/BTTS/H2H, probabilités, cotations et qualité des rencontres sont testées en entrée.
- La preuve que V3 est meilleur que V2 est **non obtenue**, jusqu'aux rapports de validation réelle.

Pour chaque phase future, l'état « complet » devra reposer sur une preuve exécutable
avec un résultat observé, et pas uniquement sur la présence de code.
