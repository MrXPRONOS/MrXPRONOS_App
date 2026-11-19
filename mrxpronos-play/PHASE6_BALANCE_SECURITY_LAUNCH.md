# Mr XPRONOS Play — V2 phase 6 : équilibrage, sécurité et lancement

## Portée

Cette phase clôt le plan V2 défini après les phases 1 à 5 :
- simulation des niveaux, des crédits et des boosts sur plusieurs profils ;
- administration privée pour modifier prix, récompenses et règles de lancement ;
- protections contre la fraude, les relectures de requêtes et les entrées malformées ;
- essais multi-comptes avec identités Telegram cryptographiquement signées ;
- activation progressive avec possibilité de suspendre uniquement les nouveaux achats.

Les icônes et illustrations définitives restent hors périmètre ; les emojis/boutons provisoires sont conservés.

## Administration du bot

Le compte Telegram figurant dans `bot_admins` ouvre `/admin → ⚖️ Équilibrage V2` :

1. **🛡 Sécurité et déploiement :** `shop_enabled` (0 fermé, 1 ouvert) ; `shop_rollout` (0–100 % de joueurs, répartition stable par identifiant Telegram), `shop_daily_limit` (1–100 achats maximum par joueur et par jour UTC, défaut 30).
2. **🛍 Prix :** les six SKU `tap-110`, `tap-120`, `tap-150`, `tap-200`, `energy-100`, `energy-250`. Prix entre 1 et 10 000 MRXP ; valeurs initiales respectivement 25, 45, 100, 180, 20, 45.
3. **🎁 Récompenses :** `daily_base` 5, `daily_quest` 5, `wheel_quest` 5, `tap_quest` 5, `mission` 10, `weekly` 30, `ordinary_level` 10 ; `rank_scale` 100 % des bonus de rang existants. Limites de sécurité : 1–500 par événement (hebdomadaire 1–2 000), bonus de rang 10–300 %.
4. **🔎 Audit :** nombre de comptes avec un total MRXP théorique négatif, achats récents, historique des huit derniers changements.

Pour éditer : toucher la valeur dans le menu, puis envoyer **un entier** en message privé dans les dix minutes. Le bot refuse les valeurs non autorisées, et `/cancel` abandonne. La vérification `bot_admins` et le contrôle de conversation privée précèdent chaque action. L'utilisateur de la Mini App n'a **aucune route publique pour modifier l'économie**.

Les paramètres sont enregistrés en D1 dans `bot_settings` avec le préfixe `mrxp_balance_`. Les modifications sont consignées dans `mrxp_balance_audit` avec l'identifiant de l'administrateur, l'ancienne et la nouvelle valeur et la date. Le couple (journal + réglage) est écrit dans un même lot D1 transactionnel.

## Politique de rétroactivité et achats

- Les événements MRXP déjà enregistrés dans `mrxp_credit_events` **ne sont jamais recalculés**.
- Pour une récompense quotidienne, de roue, de tapotage ou de mission confirmée avant un changement de tarif, le Worker conserve l'ancien barème par défaut si l'événement n'avait pas encore été crédité ; les clés uniques empêchent tout double crédit.
- Le bonus hebdomadaire utilise désormais l'instant réel de confirmation du quatrième jour, et non l'instant de consultation du portefeuille.
- Pour les niveaux et nouveaux rangs non encore crédités, la récompense est fixée au moment où elle est attribuée par le serveur ; elle ne change plus ensuite.
- Les prix ajustés concernent les **nouveaux achats**. Un article déjà payé conserve son prix d'achat (`mrxp_boost_inventory.cost`) et ses effets permanents propres à son SKU.
- Les plafonds de dépense et le solde MRXP sont vérifiés par le serveur **dans le même `D1.batch` atomique** qui crée l'inventaire et le débit. Une autre requête concurrente ne doit pas contourner ce plafond.
- En cas de fermeture de la boutique ou d'une ouverture progressive ne couvrant pas le joueur, les **nouveaux achats sont bloqués**, mais les boosteurs acquis restent consultables et activables.

## Protection et suivi

Contrôles vérifiés automatiquement :
- authentification signée Telegram, refus des signatures forgées ;
- isolation de solde, inventaire et activation entre comptes ;
- aucun prix, multiplicateur, crédits ou statut d'objet fourni par le navigateur n'est pris comme vérité ;
- idempotence des achats (UUID), synchronisations (batch_id), défis et missions ;
- limites serveur des lot de tapotages et de l'énergie autorisée ;
- recharges consommables une seule fois et expiration ;
- refus des corps JSON non structurés et des payloads trop volumineux (4 Kio pour la boutique et 16 Kio pour la synchronisation) ;
- contraintes strictes de modification des prix et récompenses ;
- contrôle des comptes présentant un solde négatif pour diagnostic.

La boutique reste sans paiement réel, sans blockchain, sans échange de jetons et sans transfert d'objets.

## Simulations de charge et d'équilibrage (365 jours)

**Scénarios synthétiques**, non issus de l'activité réelle. Hypothèses : bonus quotidien +100 XP ; roue (gain théorique simplifié de 25 XP lorsqu'elle est jouée) ; quatre missions permanentes obtenues au fil de l'année ; maîtrise calculée avec les seuils actuellement codés ; crédits gratuits selon le barème initial ; option boost ×2 un jour environ tous les 30 jours si le portefeuille le permet. Le nombre d'activations réelles peut varier selon la synchronisation toutes les douze heures.

| Profil | Taps/jour | Tours de roue | Niveau sans boost | Niveau avec boosts | XP sans boost | XP avec boosts |
|---|---:|---|---:|---:|---:|---:|
| Occasionnel | 30 | 1 jour sur 3 | 19 | 19 | 50 475 | 50 835 |
| Régulier | 150 | 1 jour sur 2 | 25 | 25 | 95 800 | 97 600 |
| Actif | 450 | Chaque jour | 34 | 35 | 209 875 | 215 275 |
| Intensif | 950 | Chaque jour | 45 | 45 | 392 375 | 403 775 |

Le niveau 50 demande **496 000 XP** plus les défis de maîtrise. Ces simulations vérifient surtout que la montée est monotone, que les sept passages de maîtrise ne sont jamais contournés et que les soldes ne deviennent pas négatifs. Les résultats ne constituent pas des promesses de progression.

## Déploiement

1. Vérifier le dernier commit GitHub et les tests `node --test mrxpronos-play/tests/telegram-bot.test.mjs`.
2. Relever les totaux des joueurs, XP, tapotages, événements MRXP et boosts ; créer un point de restauration D1.
3. Appliquer uniquement `migrations/006_balance_audit.sql`. La migration est **additive**, sans suppression ni réinitialisation des tables de joueurs.
4. Fusionner la PR après CI verte.
5. Déployer la version Cloudflare en préservant `BOT_TOKEN`, `WEBHOOK_SECRET`, `DB` et `DEV_MODE`. Vérifier explicitement le **déploiement**, pas seulement le téléversement d'une version.
6. Publier progressivement si souhaité avec les pourcentages Cloudflare, puis confirmer 100 % ; l'option `shop_rollout` donne en plus un déploiement applicatif stable par compte.
7. Vérifier en production les routes privées de la boutique, leur blocage sans authentification, le bot /start, les avatars et les cartes, ainsi que les compteurs D1 avant/après.
8. Tester manuellement depuis Telegram : **deux comptes réels différents**, achat, reconnexion, activation, expiration, synchronisation et refus du double débit. Ces essais réels nécessitent l'intervention de joueurs connectés et ne peuvent pas être certifiés par les tests simulés.

En cas d'anomalie pendant les tests : via `/admin → ⚖️ Équilibrage V2 → 🛡 Sécurité`, fixer `shop_enabled=0` pour arrêter immédiatement les nouveaux achats sans retirer les articles déjà acquis.

## Modifications de schéma

`migrations/006_balance_audit.sql` :
- nouvelle table `mrxp_balance_audit`, index par date ;
- aucune modification de `players`, `sync_receipts`, `mrxp_credit_events`, `mrxp_boost_inventory`, `bot_admins` ou des avatars.

Les autres modules et les 11 portraits de rang restent inchangés.
