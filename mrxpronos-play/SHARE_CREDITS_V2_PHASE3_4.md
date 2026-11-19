# Mr XPRONOS Play V2 — Phases 3 et 4

## Phase 3 — Cartes officielles de profil

**Objectif :** partager son identité de joueur sans photo Telegram ni informations privées, avec une preuve vérifiable des statistiques confirmées par Cloudflare D1.

### Parcours joueur
1. Ouvrir **Profil → Partager mon profil**.
2. Choisir `vertical` (1080 × 1920 : statut WhatsApp / Story) ou `carré` (1080 × 1080 : publication).
3. Choisir explicitement **Afficher mon nom Telegram** ou **Masquer mon nom** (pseudonyme neutre `Joueur MRXP`). Aucun identifiant numérique Telegram ni @username n'est inclus dans la carte.
4. Appuyer sur **Créer ma carte officielle**. La Mini App demande un snapshot signé au serveur, charge l'avatar déjà débloqué et produit un fichier PNG sur l'appareil.
5. Prévisualiser, enregistrer le PNG, partager le fichier via le partage natif quand le terminal le supporte, ou partager dans Telegram **un lien de vérification**.
6. **Copier la preuve** : un lien ouvre une page présentant le niveau, l'avatar, les XP confirmés, les missions et les défis exactement au moment de la génération.

### Autorité et vérification
- `POST /api/share/profile` exige la signature Telegram et un booléen obligatoire `hide_name`. Aucune valeur de niveau, XP ou avatar envoyée par le client n'est utilisée.
- Le serveur contrôle `players.confirmed_xp`, `player_progress_v2`, `mission_claims` et `player_avatar_prefs`.
- Le snapshot comprend le nom public choisi, XP de carrière confirmés, rang officiel, niveau, missions confirmées, maîtrises confirmées et avatar déjà acquis.
- Le token est signé avec HMAC SHA-256 et la clé propre au bot, jamais envoyée au client.
- `GET /api/share/verify?token=...` renvoie un résultat JSON vérifié ; `GET /share/verify?token=...` présente une page publique de vérification.
- Les preuves expirent **30 jours après leur émission** ; une carte enregistrée est une photo historique et ne garantit pas que les statistiques n'ont pas changé depuis.
- Le service statique `/share/avatar/1` à `/share/avatar/11` renvoie uniquement les portraits WebP officiels, pour permettre le dessin Canvas sans problème CORS.
- Une image PNG peut être modifiée par son destinataire ; **seule la page de vérification signée fait foi**. Le client ne peut pas produire une preuve valide en modifiant les statistiques localement.
- Les PNG ne sont pas enregistrés dans D1 ni envoyés sur un service tiers pour être générés.
- L'interface est provisoire (Canvas, CSS, emojis), conformément au choix de développer les fonctions avant les visuels définitifs.

### Partage
- **Partager l'image** appelle `navigator.share({files})` quand le terminal prend en charge le partage de fichiers.
- **Partager le lien Telegram** ouvre `https://t.me/share/url` avec la preuve officielle. Ce bouton **partage un lien**, pas automatiquement un PNG.
- **Enregistrer PNG** fonctionne comme repli si le partage natif du fichier est indisponible.
- En cas de portrait non chargé, la génération échoue explicitement au lieu de publier une carte incomplète ou trompeuse.

## Phase 4 — Crédits MRXP gratuits

**Objectif :** introduire une monnaie **virtuelle gratuite**, distincte de l'expérience et non convertible en FCFA, crypto ou argent. Les crédits ne sont pas transférables et ne peuvent pas être dépensés tant que la phase 5 (boutique/boosts) n'est pas publiée.

### Barème initial validé pour les tests V2

| Action confirmée par le serveur | Crédits MRXP |
|---|---:|
| Bonus quotidien synchronisé | +5 |
| Défi quotidien : bonus confirmé | +5 |
| Défi quotidien : tour de Lucky Wheel confirmé | +5 |
| Défi quotidien : lot de 50 tapotages ou plus confirmé | +5 |
| Mission permanente réussie | +10 |
| 4 jours distincts de bonus confirmé pendant une même semaine UTC | +30 |
| Passage de niveau ordinaire après activation | +10 |
| Passage rang Sentinelle, niveau 5 | +40 |
| Passage rang Élite, niveau 10 | +50 |
| Passage rang Maître, niveau 15 | +70 |
| Passage rang Champion, niveau 20 | +90 |
| Passage rang Légende, niveau 30 | +110 |
| Passage rang Mythique, niveau 40 | +140 |
| Passage rang Souverain MX, niveau 50 | +180 |

Les 5 crédits du bonus quotidien et les 5 crédits du défi quotidien correspondant sont deux récompenses distinctes, attribuées une seule fois chacune.

**Important :** les défis sont basés sur des écritures **confirmées** dans les tables serveur ; une action locale en attente de synchronisation 12 h ne génère **aucun crédit**.

### Migration
`migrations/004_free_mrxp_credits.sql` ajoute :
- `player_credit_state` : niveau historique et date d'activation de l'économie.
- `mrxp_credit_events` : journal append-only `(user_id,event_key)` unique, `amount`, `event_type`, `label`, `created_ms`.
- Index d'historique et enregistrement des comptes existants sans modifier les XP, missions, niveaux, avatars ou gains antérieurs.

Les actions accomplies **avant l'activation** n'apportent pas rétroactivement de crédits. Les nouveaux utilisateurs commencent au niveau 1. Les niveaux obtenus depuis l'activation sont récompensés une seule fois.

### APIs et sécurité
- `GET /api/credits` (identité Telegram signée) : solde, 50 dernières opérations, objectifs du jour et de la semaine, politique de récompenses.
- `GET /api/bootstrap` : inclut le solde serveur.
- `POST /api/missions/claim` et `POST /api/sync` : réconcilient le journal après la confirmation serveur, quand applicable.
- Chaque événement possède une clé stable : `daily:YYYY-MM-DD`, `quest:daily:YYYY-MM-DD`, `quest:wheel:YYYY-MM-DD`, `quest:taps:YYYY-MM-DD`, `mission:<clé>`, `weekly:<lundi>`, `level:<n>`.
- Une double requête ou une synchronisation répétée ne doit **jamais créer un deuxième crédit** pour la même clé.
- Les crédits sont calculés depuis `daily_claims`, `wheel_claims`, `sync_receipts`, `mission_claims`, les niveaux vérifiés, jamais depuis une quantité déclarée par l'utilisateur.
- L'argent, les achats par carte, les transfers, l'OTC, les retraits et Telegram Stars **ne font pas partie de cette phase**.
- Les crédits sont indépendants des XP : aucune dépense de crédits n'enlève d'expérience.

### Interface
- **Missions :** solde, règles de gains, trois objectifs quotidiens, progression hebdomadaire et bouton de rechargement.
- **Profil :** solde MRXP et journal consultable, sans remplacer la section XP.
- Le portefeuille n'est pas considéré comme fiable lorsqu'il vient de sauvegardes locales ; il est chargé par une réponse authentifiée du serveur.
- Toutes les icônes de cette phase sont temporaires ; aucune génération définitive d'images n'a été effectuée.

## Contrôles avant déploiement
- [ ] Tests des signatures et de la vie privée pour les cartes.
- [ ] Vérification de la route publique de preuve (tokens valides, invalides, modifiés et expirés).
- [ ] Validation des deux formats PNG et du repli sans Web Share API.
- [ ] Tests d'absence d'autorisation pour les routes privées.
- [ ] Tests de récompenses basées sur de vraies écritures serveur.
- [ ] Tests d'idempotence de crédits, de changement de joueur et de non-rétroactivité.
- [ ] Migration D1 additive vérifiée avec les totaux des comptes et XP avant/après.
- [ ] 11 avatars et fonctions de jeu/mission intacts.
- [ ] CI GitHub entièrement verte.
- [ ] Mise en production Cloudflare avec conservation de la base D1 et des secrets.

**Prochaine étape :** phase 5 : boutique gratuite, inventaire, activation et expiration des boosts avec transactions négatives contrôlées.
