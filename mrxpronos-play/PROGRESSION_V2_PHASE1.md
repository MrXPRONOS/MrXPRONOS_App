# Mr XPRONOS Play V2 — Phase 1 : progression hybride et espace Jeux

**État de livraison :** développement de phase 1. **Aucune création de nouveaux avatars ni de badges définitifs.** Le catalogue complet d'avatars 1–11 est conservé.

## 1. Règle officielle des niveaux

- 50 niveaux ; le niveau 50 est **Souverain MX**.
- L'expérience de carrière est exactement `players.confirmed_xp` (XP cumulés confirmés par le Worker). Cette valeur ne se dépense jamais.
- Les XP provisoires, les tapotages locaux, l'heure du téléphone ou les valeurs modifiées dans un navigateur ne font **jamais** progresser un niveau officiel.
- XP nécessaires pour passer du niveau `L` au niveau `L+1` : `Math.round(200 + 100 * L ** 1.4)`.
- Les seuils sont cumulés depuis le niveau 1 ; exemples exacts :

| Niveau obtenu | XP de carrière cumulés nécessaires |
|---:|---:|
| 1 | 0 |
| 2 | 300 |
| 3 | 764 |
| 4 | 1 430 |
| 5 | 2 326 |
| 10 | 11 037 |
| 15 | 28 311 |
| 20 | 55 762 |
| 30 | 146 172 |
| 40 | 290 665 |
| 50 | 496 000 |

## 2. Défis de maîtrise (30 défis, validés par le serveur)

Les défis n'attribuent pas de XP additionnels. Leur récompense est de rendre possible le passage de certains rangs lorsque les XP nécessaires sont réunis.

| Famille | Jalons confirmés | Source d'autorité |
|---|---|---|
| Tapotages (12) | 50, 200, 500, 1 000, 2 500, 5 000, 10 000, 20 000, 50 000, 100 000, 200 000, 400 000 | `players.confirmed_taps` |
| Bonus quotidiens (7) | 2, 5, 10, 20, 40, 80, 160 | Nombre de lignes `daily_claims` |
| Tours de roue (7) | 2, 5, 10, 20, 40, 80, 160 | Nombre de lignes `wheel_claims` |
| Missions (4) | 1, 2, 3, 4 missions gratuites réclamées | `mission_claims`, **hors** `join_main` et `join_foot` |

Les quatre familles progressent simultanément. Les deux missions de canaux rapportent leurs XP habituels mais **ne sont pas requises** dans le calcul des défis de maîtrise.

### Passages conditionnels

| Entrée au niveau | Défis de maîtrise distincts nécessaires |
|---:|---:|
| 5 | 2 |
| 10 | 3 |
| 15 | 5 |
| 20 | 7 |
| 30 | 10 |
| 40 | 14 |
| 50 | 18 |

Tous les autres niveaux exigent uniquement le seuil d'XP. Si un joueur possède suffisamment de XP pour franchir un rang mais pas assez de défis, ses XP continuent de s'accumuler : le rang reste verrouillé jusqu'à validation des défis requis. La vérification intervient lors de la consultation de la progression ou après des gains confirmés.

## 3. Migration non destructive de la V1

- La migration `migrations/002_hybrid_progression.sql` ajoute uniquement `player_progress_v2` et un index.
- **Ne pas supprimer** `players`, `mission_claims`, `sync_receipts`, `daily_claims` ou `wheel_claims`.
- La migration D1 initialise immédiatement le niveau historique de **tous les comptes déjà présents** à partir des tapotages confirmés. Pour les comptes arrivant plus tard ou non initialisés, le Worker possède aussi un mécanisme de rattrapage au premier accès. Ce niveau est enregistré comme `legacy_level_floor`, plafonné à 50.
- Ce niveau historique est un plancher définitif : un recalcul XP ne peut jamais rétrograder l'ancien joueur.
- Le premier enregistrement de progression (s'il manque après la migration) est effectué **avant** toute mise à jour des tapotages par une nouvelle synchronisation, même si le joueur n'a pas appelé le bootstrap.
- Les niveaux débloqués ultérieurement respectent les nouveaux seuils et défis de maîtrise.
- Les XP et tapotages en attente sur le téléphone restent en attente selon les règles existantes ; leurs futurs crédits sont traités normalement par `/api/sync`.
- La transition est transparente : aucun achat, réinitialisation, transfert ou création d'un deuxième compte n'est nécessaire.

Le recalcul est déterministe et ne crée pas de récompenses artificielles. La valeur `current_level` dans la base ne peut qu'augmenter.

## 4. API

L'API nécessite toujours `x-telegram-init-data` signé par Telegram.

- `GET /api/progression` retourne les niveaux, seuils, rang, défis, blocage éventuel et prochaine condition de rang.
- `GET /api/bootstrap` renvoie en plus la progression officielle.
- `GET /api/missions` renvoie en plus la progression officielle et les défis vérifiables.
- `POST /api/missions/claim` inclut la progression une fois le crédit réellement confirmé.
- `POST /api/sync` renvoie la progression après attribution, y compris lors des rejouements idempotents.

Aucune route publique ni paramètre `level` contrôlé par l'utilisateur ne peut attribuer un rang.

## 5. Interface mobile

- Le niveau et l'avatar de rang sont désormais affichés d'après la réponse du serveur, pas d'après le compteur de tapotages local.
- **Profil** : jauge XP, rang officiel, XP restants, état des défis et bouton d'actualisation.
- **Missions** : les 30 défis de maîtrise sont consultables dans une zone repliable, avec barre et condition de passage.
- Les icônes des nouvelles fonctions sont **provisoires** (emoji / CSS). Les visuels définitifs seront réalisés seulement après le développement de la V2.

## 6. Espace « Jeux » (ancien onglet « Roue »)

- Le cinquième système existant n'est pas supprimé : le bouton de navigation `wheel` est simplement libellé **JEUX**.
- Le nouvel écran affiche une sélection de jeux.
- La **Lucky Wheel** y reste jouable sous une carte dédiée ; elle conserve ses règles de gains et son contrôle d'un tour par jour.
- **Snake** apparaît comme **en développement** (carte désactivée) et n'annonce aucune partie jouable non déployée.
- Le bandeau de l'accueil ouvre directement la Lucky Wheel ; l'onglet Jeux ouvre le catalogue.
- Un prochain jeu pourra avoir sa propre carte, logique et route sécurisée, sans remplacer l'onglet existant.

## 7. Vérifications obligatoires avant publication

1. Migration D1 idempotente et table `player_progress_v2` présente.
2. Ancien joueur : XP, tapotages, missions et niveau historique conservés.
3. Nouveau joueur : niveau 1 à 0 XP ; niveau 2 dès 300 XP.
4. Passage niveau 5 bloqué s'il manque des défis ; débloqué après actions confirmées.
5. Niveau 50 n'est jamais dépassé.
6. Canaux Telegram non obligatoires pour progresser.
7. Une requête non authentifiée ne peut pas accéder au profil ou aux défis.
8. Les 12 heures de synchronisation restent en vigueur ; aucune progression sur XP provisoires.
9. La Lucky Wheel, l'administration, les missions et les avatars restent fonctionnels.
10. Tous les tests GitHub Actions passent, puis contrôle de production Cloudflare.

## 8. Hors périmètre volontaire de la phase 1

Les **crédits MRXP gratuits**, la boutique, les boosts, les cosmétiques, la refonte complète du profil et les cartes de partage officielles seront développés dans les phases 2 à 5. Les avatars officiels 1–11 sont déjà disponibles : inutile de les régénérer.
