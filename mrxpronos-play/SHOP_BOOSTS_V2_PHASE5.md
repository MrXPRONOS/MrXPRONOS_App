# Mr XPRONOS Play V2 — Phase 5 : boutique et boosts gratuits

## Fonctionnalités livrées

La boutique permet uniquement l'utilisation de **crédits MRXP gratuits**, déjà gagnés en jouant. Les boosts n'ont pas de valeur monétaire et ne sont pas échangeables, convertibles, revendables ou transférables. Aucun paiement réel, wallet blockchain, Telegram Stars ou token n'est impliqué.

La Mini App présente la boutique accessible depuis **Jouer**, **Missions** et **Profil** ; le solde MRXP, les six articles du catalogue, les coûts, l'inventaire propre au compte Telegram, l'activation, l'état de chaque boost et la durée restante.

## Catalogue contrôlé par le serveur

| Code | Article | Coût MRXP | Effet | Durée |
|---|---|---:|---|---|
| `tap-110` | Boost Découverte | 25 | ×1,1 XP par tapotage confirmé | 24 heures après la première synchronisation validée |
| `tap-120` | Boost Guerrier | 45 | ×1,2 XP par tapotage confirmé | 24 heures après la première synchronisation validée |
| `tap-150` | Boost Champion | 100 | ×1,5 XP par tapotage confirmé | 24 heures après la première synchronisation validée |
| `tap-200` | Boost Souverain | 180 | ×2 XP par tapotage confirmé | 24 heures après la première synchronisation validée |
| `energy-100` | Recharge énergie 100 | 20 | +100 énergie, plafonnée à 500 dans l'interface | 72 heures pour être prise en compte à la prochaine synchronisation |
| `energy-250` | Recharge énergie 250 | 45 | +250 énergie, plafonnée à 500 dans l'interface | 72 heures pour être prise en compte à la prochaine synchronisation |

**Le catalogue et les montants viennent du Worker** : envoyer un prix modifié ou un multiplicateur forgé depuis le navigateur ne modifie jamais le coût ou l'effet. Les valeurs pourront être ajustées ultérieurement après des mesures réelles de l'économie.

## Parcours d'achat

1. Le joueur gagne des crédits MRXP déjà **confirmés** dans D1.
2. Il ouvre **Boutique**, consulte les prix et clique **Acheter**. Le Worker vérifie l'identité Telegram signée et le solde de ce seul compte.
3. L'achat est consigné atomiquement : un objet en inventaire et **un débit négatif** dans `mrxp_credit_events`.
4. L'ID de transaction UUID est idempotent : une nouvelle tentative du même achat (réseau instable, double clic) ne débite jamais deux fois.
5. L'article apparaît « Disponible à activer ». Le joueur choisit quand il veut l'activer.
6. Un multiplicateur activé passe en « En attente ». Un seul multiplicateur peut être actif ou en attente. L'énergie fonctionne indépendamment mais ne peut avoir qu'une recharge « chargée » en même temps.

## Synchronisation des XP et limites exactes

Le moteur préexistant autorise la confirmation des tapotages **au minimum toutes les 12 heures**. Pour ne pas perdre un boost expirant avant la première synchronisation, un boost de type `tap` activé se met en file `queued` :

- La **première synchronisation réussie contenant des tapotages** active le boost pour **24 heures** et applique son multiplicateur à ce lot.
- Les synchronisations ultérieures peuvent bénéficier du multiplicateur tant qu'elles sont confirmées avant l'expiration.
- Les XP de base et les récompenses quotidiennes/roue continuent selon les règles normales : **seuls les XP de tapotages sont multipliés**.
- Pour ×1,1 : 21 clics rapportent 23 XP, avec un report de 0,1 XP ; neuf clics supplémentaires dans une synchronisation admissible rapportent 10 XP (le report fractionnaire est soldé).
- Les fractions sont conservées dans `carry_milli` de l'inventaire côté D1, jamais déclarées par le téléphone.
- Après expiration, le multiplicateur ne peut pas être réactivé gratuitement. Un nouvel article doit être acheté et activé.

**Important :** ce fonctionnement reprend le système de synchronisation historique. La valeur des bonus confirmés dépend du moment de synchronisation, pas de timestamps déclarés par le navigateur. Les tapotages en attente affichent leur XP de base, sans présenter le bonus éventuel comme déjà gagné.

## Recharges d'énergie

- Activation immédiate sur le téléphone, plafonnée à **500 unités**. L'interface empêche d'activer une recharge si l'énergie disponible ne laisse pas assez de place pour recevoir son montant intégral, pour éviter de gaspiller des crédits.
- Le serveur conserve la recharge dans l'état `charged` et augmente uniquement le plafond anti-triche du **premier lot de tapotages accepté pendant la validité de 72 heures**.
- Après cette synchronisation, l'inventaire passe à `used`. L'avantage ne peut pas être attribué une deuxième fois, même en rejouant le même lot.
- Lorsqu'une recharge n'est pas utilisée dans les 72 heures, le Worker la marque `expired`.
- Le téléphone mémorise uniquement les identifiants de recharges déjà appliquées localement pour éviter d'augmenter l'énergie deux fois après un redémarrage. Cela ne lui donne aucun droit supplémentaire côté serveur.

## Tables et API

Migration additive obligatoire : `migrations/005_boost_store.sql` :
- `mrxp_boost_inventory`, clef `(user_id,purchase_id)` ; `sku`, `kind`, `cost`, `state`, `bought_ms`, `activated_ms`, `expires_ms`, `carry_milli`.
- Index utilisateur/état/expiration. Les tables existantes restent inchangées.
- Le journal MRXP de phase 4 `mrxp_credit_events` conserve les débits avec la clé unique `buy:<purchase_id>`.

API privées, uniquement avec l'identité Telegram signée :

- `GET /api/shop` : catalogue réel, solde MRXP confirmé, inventaire et états.
- `POST /api/shop/buy` : corps `{sku,purchase_id}`, achat transactionnel à prix serveur.
- `POST /api/shop/activate` : corps `{purchase_id}`, vérification de propriété et protection d'activation concurrente.
- `POST /api/sync` : application du multiplicateur au nombre de tapotages admis ; prise en compte d'une recharge énergie, report de fractions et mise à jour des états dans le lot D1 atomique.
- `GET /api/bootstrap` : inclut maintenant le catalogue et l'inventaire pour éviter un chargement supplémentaire à l'ouverture.

## Sécurité et non-régression

- Aucune route ne permet d'attribuer arbitrairement des MRXP, de modifier les prix ou d'appliquer un boost appartenant à un autre joueur.
- Vérification par l'ID Telegram signé : le client ne choisit jamais son propre `user_id`.
- Les achats dépassant le solde sont refusés sans créer d'inventaire ou de débit.
- Les doublons de `purchase_id` ne facturent pas deux fois ; un ID réutilisé pour un autre article est refusé.
- Le crédit de bonus XP est calculé côté serveur, seulement après validation du lot.
- Les limites historiques anti-triche (taille de lot, énergie régénérée, synchro 12 heures, XP contrôlés) restent actives.
- Un boost n'altère pas l'XP historique, les rangs et avatars déjà débloqués, les gains passés, les missions existantes, les cartes publiques, le bot /start ou l'espace Jeux.

## Contrôles de publication

- [x] Migration SQL additive prévue et versionnée.
- [x] Six SKU à tarifs immuables côté serveur.
- [x] Séparation dépenses MRXP et gains XP.
- [x] Achat idempotent et atomique.
- [x] États d'inventaire et vérification des appartenances.
- [x] Activation exclusive par type.
- [x] Multiplication décimale et report de fraction côté serveur.
- [x] Recharge d'énergie à usage unique et expiration.
- [x] Catalogue et inventaire affichés dans Mini App.
- [x] Tests automatisés de non-régression et du panier.
- [ ] Contrôle de la migration réelle Cloudflare D1, avant/après.
- [ ] CI verte sur la version finale.
- [ ] Fusion GitHub et déploiement Worker à 100 %.
- [ ] Contrôle après déploiement et test utilisateur dans Telegram.

Toutes les icônes de boutique sont **provisoires** (CSS/emoji), comme souhaité. Les visuels définitifs seront traités séparément.
