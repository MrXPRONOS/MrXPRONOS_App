# Montante quotidienne BSD V2 + NVIDIA NIM

Ce moteur classe **au plus une sélection par jour (UTC)** parmi les pronostics **déjà publiés** par BSD V2 dans `data.json`. Il n'envoie pas de message Telegram et **ne place aucun pari réel**. Un jour sans sélection est normal lorsque les preuves sont insuffisantes.

## Univers des marchés

Le moteur relit **toutes les sélections primaires et secondaires publiées par BSD V2**, sans préférence imposée pour un marché : résultat 1/X/2, double chance 1X/X2, BTTS oui/non et totaux de buts Over/Under. Il exclut les marchés interdits par la politique BSD V2 (dont 12 et UNDER_45). Les **totaux par équipe** et **totaux de mi-temps** existent dans la PR expérimentale #272, mais **ne sont pas actuellement publiés dans le moteur de production** : ils ne seront donc considérés qu'après leur intégration, leur cotation réelle et la vérification complète des garde-fous.

## Filtre statistique, inchangé

- Uniquement catégorie PRO/VIP, confiance publiée ≥79 %, recommandé, avant coup d'envoi et au moins 60 min avant le match.
- Cote **strictement >1,20**, source BSD V2 vérifiée (jamais cote `mrxpronos_model`), mise à jour ≤6 heures.
- Probabilité conservatrice ≥82 %, écart ≥2,5 points sur `1/cote`, garde-fous V2.1 de prix, drift et calibration. Pas de combiné.
- Le classement numérique n'est qu'une comparaison de qualité relative et **ne donne aucune certitude de victoire**.

## Relecture NVIDIA NIM

**Modèle retenu :** `nvidia/nemotron-3-ultra-550b-a55b` (API hébergée `https://integrate.api.nvidia.com/v1/chat/completions`). Le workflow envoie les **16 meilleures candidatures statistiques au maximum** à l'API dans une même requête; le champ `limited_to_top_n_candidates` signale les autres candidatures non analysées. La réponse vérifie chacune des sélections du lot, plutôt que de conseiller un nouveau marché.

L'analyse reçoit des **agrégats point-in-time** de l'archive chiffrée BSD : dernières rencontres terminées, buts marqués/encaissés, scores des confrontations directes, domicile/extérieur, tendances BTTS/totaux et modèles de buts BSD. Les 4 heures de délai de clôture BSD sont respectées. Seuls les matchs déjà terminés au moment de l'analyse sont utilisés. L'archive en clair ne quitte pas le runner : elle est effacée immédiatement après la sélection. Le modèle ne dispose **pas** des blessures ni des compositions vérifiées, et doit le signaler au lieu de les inventer. Vérifier les conditions d'utilisation de BSD et celles de NVIDIA avant d'exploiter commercialement ces données dérivées.

NIM émet pour chaque candidat un verdict `approve/reject/uncertain`, un risque qualitatif `low/medium/high` et des drapeaux de risque, **pas** une nouvelle probabilité. Seul un candidat `approve` + `low` peut passer. Une absence de clé, d'historique, d'éléments vérifiables, un défaut d'API ou une réponse JSON incohérente conduit à `no_pick` (*fail closed*). NIM ne peut ni modifier le marché, ni inventer la cote, ni passer outre un refus BSD V2.

Le premier choix est figé par date UTC dans `montante/ledger.json`. Les sorties `montante/daily.json` et `montante/du-jour.md` contiennent uniquement des diagnostics non sensibles. **Une sélection figée ne justifie jamais de miser sur une cote expirée ou un match commencé.**

## Configuration nécessaire

Dans **Settings → Secrets and variables → Actions** du dépôt GitHub, configurer `NVIDIA_API_KEY` obtenu sur <https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b> et vérifier l'existence de `BSD_HISTORY_KEY`. Ne jamais stocker les clés dans le code ni dans un fichier publié.

Une fois la PR fusionnée, le workflow `.github/workflows/bsd-v2-montante.yml` se déclenche après la production BSD V2 réussie et à 06:35, 12:35 et 18:35 UTC, ou manuellement. Sur les PR, seuls les tests **sans réseau ni secrets** sont exécutés.

## Limites

NIM n'est pas un modèle spécifiquement entraîné et calibré sur la réussite des paris football : son avis est **une revue qualitative**, non une probabilité validée. Le modèle et le prix du marché peuvent être tous les deux erronés. Les cotes consensus ne sont pas des offres fermes chez 1xBet/Melbet. Vérifier la même sélection et la cote réelle chez le bookmaker avant toute mise. L'API hébergée nécessite des crédits/quota et sa disponibilité doit être testée avec une clé fonctionnelle.