# Mr XPRONOS — Bot Telegram de coupons **cote 4.00+**

Ce projet remplace le système « Free Money » : **aucun FCFA, aucun transfert, aucun retrait.**
Les utilisateurs gagnent des **XP virtuels** et les échangent contre des coupons de pronostics, dont **la cote totale calculée est au minimum 4.00**.

> ⚠️ Les cotes sont indiquées par l'administrateur au moment de la publication, et **ne sont pas des cotes en direct**. Vérifier les rencontres, les sélections, les marchés, les cotes et leurs conditions sur le bookmaker. Les coupons ne garantissent aucun résultat. Accès 18+ selon la législation locale.

## 1. Fonctionnalités

- `/start` : bienvenue, identification d'un éventuel parrain, confirmation 18+ (déclarative).
- `✅ Vérifier` : vérification de l'appartenance aux canaux obligatoires si configurés.
- `🚩 Tâche` : missions d'abonnement vérifiées et gain unique en XP.
- `🎁 Bonus` : XP périodiques (par défaut 5 XP toutes les 2 h, limite de 10 XP/jour).
- `↗️ Partager` : URL personnelle, gain par filleul réel ayant rejoint les canaux requis. Désactivé sans canal requis.
- `⭐ Mes XP` : compte de points non monétisables.
- `🎟️ Coupons cote 4+` : coupons simples, Pro et VIP, **tous à cote totale >= 4.00**.
- `🎫 Mes coupons` : coupons déjà débloqués, toujours consultables dans l'historique.
- Admin : ajout de coupons, calcul strict des cotes, stock, date d'expiration, activation, missions, octroi XP, statistiques.
- SQLite et transactions atomiques pour empêcher doubles déblocages / doubles crédits.

## 2. Installation (Windows 11)

1. Créer un bot Telegram via `https://t.me/BotFather` : envoyer `/newbot`, choisir le nom et l'identifiant et copier le token.
2. Extraire le ZIP. Dans le dossier `telegram-coupons-bot`, copier `.env.example` en `.env`.
3. Modifier les variables `BOT_TOKEN` et `ADMIN_IDS` dans `.env`. Ne jamais publier le token dans GitHub.
4. Ouvrir PowerShell dans le dossier :

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python bot.py
```

Sur Linux :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

5. Envoyer `/start` en privé au bot, puis confirmer être majeur.

**Important :** le programme doit rester en exécution pour répondre aux utilisateurs. GitHub Pages est statique et ne peut pas exécuter ce serveur Python ; déployer sur un hôte d'applications ou un VPS pour du 24h/24.

## 3. Paramètres dans `.env`

```dotenv
BOT_TOKEN=TOKEN_SECRET_DE_BOTFATHER
ADMIN_IDS=123456789
BOT_TITLE=XPRONOS 4+
DB_PATH=./data/coupons_v4.db
REFERRAL_POINTS=30
BONUS_POINTS=5
BONUS_COOLDOWN_HOURS=2
BONUS_DAILY_CAP_POINTS=10
REQUIRED_CHANNELS_JSON=[]
```

Pour activer un canal obligatoire, configurer par exemple :

```dotenv
REQUIRED_CHANNELS_JSON=[{"id":"@mr_xpronos","url":"https://t.me/mr_xpronos"}]
```

Le bot **doit être administrateur** du canal pour pouvoir vérifier les abonnements. Pour un canal privé : utiliser comme `id` l'identifiant numérique `-100...`, pas l'URL d'invitation. Le lien va dans `url`.

**Attention :** `adult_confirmed` est une déclaration de l'utilisateur, pas une vérification documentaire de l'âge. Le bot ne remplace pas les procédures obligatoires éventuelles.

## 4. Publier un coupon de cote >= 4.00

L'administrateur utilise cette commande **dans le chat privé du bot** :

```text
/addcoupon PRO | 50 | 2026-10-30T18:00 | -1 | Coupon du soir | Arsenal - Chelsea ; Plus de 1,5 but ; 1.70 | Milan - Napoli ; Double chance 1X ; 2.40
```

**Démonstration de format uniquement : les rencontres et cotes ci-dessus sont fictives et ne constituent pas une recommandation.**

Signification des champs séparés par `|` :

1. `PRO` : type (SIMPLE, PRO ou VIP).
2. `50` : prix en XP, jamais en FCFA.
3. `2026-10-30T18:00` : expiration, en **UTC**.
4. `-1` : stock illimité ; sinon choisir un entier positif (par exemple `100`).
5. `Coupon du soir` : titre.
6. Une ou plusieurs sélections sous forme `Match ; Marché ; Cote`, chacune séparée par `|`.

Le bot calcule `1.70 × 2.40 = 4.08`. **Une cote de 3.99 est refusée** et le seuil s'applique *avant* les arrondis d'affichage (3.999 est refusé même si arrondi à 4.00). Une sélection unique à 4.00 est acceptée. Jusqu'à 10 sélections sont autorisées.

Le bot affiche aux utilisateurs uniquement la cote totale et le prix en XP avant déblocage. Après paiement en XP (virtuel), les détails des rencontres et marchés sont accessibles dans `🎫 Mes coupons`.

Les **cotes ne sont pas automatiquement récupérées** auprès d'un bookmaker. Elles sont saisies par l'administrateur et peuvent changer. Ne publier que des coupons validés par des données réelles.

## 5. Commandes administrateur

| Commande | Fonction |
|---|---|
| `/admin` | Liste des commandes admin |
| `/addcoupon ...` | Publier un coupon de cote >= 4.00 |
| `/listcoupons` | Voir les coupons et les stocks |
| `/delcoupon 1` | Désactiver le coupon #1 |
| `/activatecoupon 1` | Réactiver le coupon #1 s'il n'a pas expiré |
| `/addtask @canal https://t.me/canal 15` | Mission d'abonnement, 15 XP |
| `/listtasks` | Voir les missions en cours |
| `/deltask 1` | Désactiver la mission #1 |
| `/grantxp 123456789 30` | Créditer 30 XP à un membre existant |
| `/stats` | Statistiques : membres, missions, coupons, XP |

## 6. Réglages et limites importantes

- Aucun lien de pari bookmaker préchargé, et aucun ticket réellement placé.
- Aucun programme de création automatique de comptes Telegram, aucune génération de faux filleuls.
- Lorsque le bot est administrateur d'un canal, la vérification utilise l'API `getChatMember`, pas une simple déclaration du membre.
- La vérification d'appartenance ne constitue pas une preuve d'identité unique ; surveiller les abus et fraude multi-comptes.
- Le code de la base de données est **distinct de la version Free Money**, qui stockait des balances financières. Ne pas réutiliser l'ancienne base : la migration de solde FCFA vers XP est volontairement interdite.
- Le bot doit faire l'objet d'un contrôle de conformité avant publication selon les règles applicables à l'audience, aux paris sportifs et à la publicité.

## 7. Tests

Depuis le dossier :

```bash
python -m unittest discover -s tests -v
```

Les tests comprennent la cote 4.00 exacte, le refus de la cote 3.99, le refus de 3.999 arrondie, le déblocage unique, le stock concurrent, le bonus, la mission et les parrainages, ainsi que le rejet d'une ancienne base monétaire.

## 8. Fichiers

- `bot.py` : commandes et menus du bot Telegram.
- `db.py` : stockage SQLite, XP, historique des coupons et transactions.
- `odds.py` : validation et calcul exact de la cote totale.
- `.env.example` : configuration modèle, sans token réel.
- `requirements.txt` : bibliothèques Python.
- `tests/test_coupons.py` : tests automatiques.


## 9. Intégration au dépôt officiel Mr XPRONOS

Ce bot est installé dans `telegram-coupons-bot/` du dépôt `MrXPRONOS/MrXPRONOS_App`. Il est volontairement **isolé** des workflows Telegram existants du site pour ne pas provoquer d'envois supplémentaires ou de doublons. Il ne récupère pas automatiquement les pronostics du site : un administrateur doit créer chaque coupon via `/addcoupon`.

Le workflow GitHub Actions `.github/workflows/xpronos-coupon-bot-tests.yml` lance les tests à chaque modification de ce dossier. **Il ne lance pas le bot Telegram en continu et n'a pas besoin de secrets.**

### Déploiement permanent

Un hôte qui exécute Python en continu est nécessaire : par exemple un worker Render, un VPS ou un serveur équivalent. Commandes à utiliser à la racine du dossier `telegram-coupons-bot` :

```bash
pip install -r requirements.txt
python bot.py
```

Avec Docker :

```bash
docker build -t xpronos-coupons-bot .
docker run --rm --env-file .env -v xpronos_coupon_data:/app/data xpronos-coupons-bot
```

Définir `BOT_TOKEN` (nouveau bot créé avec BotFather), `ADMIN_IDS` et `REQUIRED_CHANNELS_JSON` dans les **variables d'environnement du serveur**, jamais dans le dépôt. Rendre le bot administrateur de chaque canal vérifié. La base SQLite dans `/app/data` doit être stockée sur un disque persistant et sauvegardée régulièrement ; sans stockage persistant, les XP et les coupons seront perdus au redémarrage. N'exécuter qu'une instance en `run_polling()` avec la même clé Telegram.

Ce bot est distinct de la publication de coupons-images déjà présente sur les canaux du dépôt. Aucune publication ni lancement automatique ne s'active à l'intégration du code.
