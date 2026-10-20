# BSD V2 — robustesse du volume sans abaisser la qualité

Corrections du 20 octobre 2026 :

1. Le filtre de sélection football applique dès l'étape pré-cotes la règle V2.1 de probabilité conservatrice minimum de **85 %** pour `OVER_15`. Si cette option échoue, un autre marché **déjà admissible selon l'analyse footballistique** peut devenir premier dans le classement. Aucune cote ne choisit le marché.
2. Les contrôles de prix restent après le choix fixe : source reconnue, cote réelle ou estimation explicitement identifiée, cote de publication >= 1,20, marge de valeur selon le marché. Aucune substitution de cote d'un marché voisin n'est autorisée. Le diagnostic `quote_audit` explique le marché demandé et les réponses reçues.
3. La publication journalière est réévaluée deux fois supplémentaires (11:17 et 16:17 UTC), en complément des déclenchements externes déjà existants. Aucun événement antérieurement publié n'est remplacé : même identifiant et même sélection dans le registre immuable, et les résultats restent mis à jour.
4. La collecte multisource est **strictement conditionnelle** : confirmation calendrier CC0, identité officielle BSD, cote réelle du marché précis, règles V2.1 et valeur. En cas de zéro rapprochement, le diagnostic public `bottleneck_stage` identifie l'étape manquante, sans fabriquer de pronostics. La couverture du calendrier CC0 reste limitée à huit championnats nationaux, ce qui ne prouve pas l'absence d'autres matchs.
5. Les tests de non-régression contrôlent l'élimination précoce des marchés non conformes, la stabilité du classement, et les motifs de blocage multisource.

Les conditions de publication n'ont pas été abaissées. Une journée avec peu ou zéro pronostic qualifié demeure un résultat possible.
