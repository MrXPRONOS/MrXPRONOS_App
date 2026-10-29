# Mr XPRONOS — Protocole enregistré pour scores exacts groupés 1xBet
**Date d'enregistrement : 20 octobre 2026.** Recherche isolée `feature/exact-score-v1-20261019` ; aucun impact production. Ce document fixe les comparaisons à effectuer, il ne certifie pas une réussite ni une rentabilité.

## Objet mesuré
Pari **Correct Score – Group Bet** sur UN match, avec les compositions G1 à G9 exactes telles que définies dans `bsd/grouped_correct_score.py`. Les groupes peuvent se recouper, et les neuf templates ne prouvent PAS leur disponibilité chez 1xBet sur une rencontre donnée. Le résultat est le score à 90 minutes selon les règles du marché. Ne pas confondre pari groupé et coupon multi-matchs, ni avec score exact unique, ni avec Under 2,5 comme pari séparé.

## Population indépendante future
- Fenêtre primaire : prévisions **capturées à partir du 21 octobre 2026 00:00 UTC**, avant le coup d'envoi avec au moins 30 minutes d'avance ; utiliser le champ `captured_utc` du registre immuable.
- Modèle figé : `mrx-grouped-score-dc-shadow-2026-10-20-v1`, paramètres FROZEN et groupes du commit de base. En cas de changement de code, de données d'entrée ou de calibration, ouvrir une **cohorte/version distincte** et ne jamais écraser les anciennes prévisions.
- Les matchs historiques 2025 et 2026 jusqu'au 20 octobre ont déjà été explorés, donc ne constituent pas une confirmation indépendante.
- Consigner les rencontres capturées, celles rejetées et leur raison, celles dont le résultat est manquant, celles dont l'identité change, les annulations et l'âge du résultat. Ne pas remplacer rétroactivement une sélection après connaissance du score.
- Les archives chiffrées, horodatages et empreintes sont la source de vérité. Aucune prédiction rétro-créée après match ne compte comme prospective.

## Politiques prédéfinies, sans optimisation sur cette cohorte
1. `baseline` : groupe le plus probable, tous les matchs admissibles.
2. `with_double_chance` : même univers, orientation issue du modèle dédié ; mesurer **les groupes réellement changés** et les résultats discordants sur mêmes matchs.
3. `ceiling_under_25` : filtre total-buts déjà codé ; **le pari reste le groupe de trois scores, pas l'Under 2,5**.
4. `with_h2h_under` : filtre strict déjà codé, sans assouplissement opportuniste.
5. `G1 AND ceiling_under_25` : sous-population pré-enregistrée à titre de recherche, **sans modifier le groupe sélectionné par la règle 3**.
6. G1–G9 évalués **sur la même population de matchs**, à titre contrefactuel descriptif uniquement si les groupes ne sont pas explicitement observés chez le bookmaker.

## Métriques obligatoires
- Pour chaque politique : univers admissible, n sélectionné, n terminé, n annulé/absent, n gagné, réussite, Wilson 95 %, Brier, prévision moyenne, écart de calibration et taux de couverture.
- Fournir la répartition mensuelle, semestrielle, et par `league_key` stable, avec libellé de championnat si disponible. Toute analyse par championnat avec **moins de 100 matchs terminés** est marquée exploratoire ; pour les sous-groupes H2H, mentionner les faibles effectifs.
- Comparer `baseline` à chaque variante **sur les mêmes rencontres effectivement sélectionnées** avant d'attribuer un gain à un changement de groupe. Pour des prédictions différentes sur les mêmes matchs, conserver les paires de gains/pertes discordantes pour un test apparié.
- Publier la distribution des refus de chaque filtre : forme insuffisante, absence de H2H, moins de 3 rencontres H2H, H2H non stable, probabilité Under insuffisante, inadéquation directionnelle, absence de groupe réellement offert.
- Éviter de déclarer « meilleur championnat » en testant beaucoup de ligues : min. 100 résultats réglés **par ligue, période et politique** pour une comparaison candidate ; vérifier la répétition dans des fenêtres successives. Les comparaisons exploratoires de nombreuses ligues ne valident pas un modèle.

## Critères de lecture fixés avant les résultats
- Vérification initiale après **au moins 300 sélections réglées** pour `ceiling_under_25` sur la fenêtre prospective. Si ce volume n'est pas atteint, afficher seulement des intervalles de confiance et les comptes.
- Aucune performance réelle ou rentabilité n'est annoncée tant que les résultats ne sont pas réglés et que les cotes exécutables n'ont pas été archivées.
- Définir l'efficacité comme une **frontière précision/couverture**, pas seulement le taux maximum. Comparer aussi le nombre de sélections par semaine.
- Les décisions opérationnelles resteront soumises à une nouvelle évaluation indépendante ; aucun déploiement automatique en production par ce protocole.

## Valeur économique : données qui manquent
Une cote n'est « observée » que si elle se rapporte au **même match, au même marché de scores groupés, à la même sélection et avant coup d'envoi**, avec identité bookmaker, horodatage, source et capture. Les cotes modèles ou du score exact isolé ne sont PAS des cotes groupées. Calculer, quand elles existent, le seuil `1 / p_calibrée`, puis `p_calibrée × cote - 1` et des rendements hypothétiques à mise fixe ; ces valeurs ne sont **pas** une preuve de ROI réalisé. L'estimation de probabilité doit être validée hors échantillon.

## Confidentialité et sécurité
Exécuter le backtest à partir de l'historique BSD déchiffré uniquement dans le runner privé ; publier seulement des agrégats. Ne jamais publier les listes de prévisions futures, les clés, les données de comptes, ni les cotes inventées.
