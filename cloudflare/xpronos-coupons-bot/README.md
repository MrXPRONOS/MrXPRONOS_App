# Free Pronos — Bot Telegram et Mini App Cloudflare

Ce bot Telegram fonctionne sans Supabase. Il utilise un Worker Cloudflare et une base D1 indépendante pour les comptes, les XP, les missions, le parrainage et les coupons de cote totale minimum 4.00. Les XP sont virtuels, non convertibles en argent. Accès réservé aux 18 ans ou plus ; aucun résultat sportif n'est garanti.

## Infrastructure déjà préparée

- Compte Cloudflare connecté : Ananiolivier52@gmail.com's Account.
- D1 : **xpronos-coupons-bot** ; identifiant et binding DB renseignés dans wrangler.toml.
- Worker à déployer : **xpronos-coupons-bot**.
- URL préconfigurée : https://xpronos-coupons-bot.cinecanaux-xpronos.workers.dev
- Webhook Telegram : cette URL suivie de /telegram.
- Le workflow Supabase du bot a été désactivé pour empêcher un retour involontaire de l'ancien webhook.
- Le site Mr XPRONOS et les autres workflows ne changent pas.

## Étape 1 : obtenir un jeton Cloudflare (distinct de l'accès plugin)

Va sur https://dash.cloudflare.com/profile/api-tokens puis **Create Token** et **Create Custom Token**.

Nom proposé : **GitHub XPRONOS 4+**.

Permissions sur le compte Cloudflare concerné :
- Account → **Workers Scripts → Edit**
- Account → **D1 → Edit**
- Restriction : seulement ce compte Cloudflare.

Puis **Continue to summary → Create Token**, et copie la valeur. Le plugin Cloudflare connecté à ChatGPT n'envoie pas automatiquement ses autorisations à GitHub Actions.

## Étape 2 : ajouter exactement 2 secrets GitHub

Ouvre https://github.com/MrXPRONOS/MrXPRONOS_App/settings/secrets/actions → onglet **Secrets** → **New repository secret**.

| Nom exact | Valeur |
| --- | --- |
| **CLOUDFLARE_API_TOKEN** | Le nouveau jeton d'API Cloudflare obtenu à l'étape 1 |
| **XPRONOS_CF_BOT_TOKEN** | Le jeton du bot Telegram depuis @BotFather → /mybots → API Token |

Le token Telegram **peut être le même** que celui du nouveau bot existant : tu dois seulement l'enregistrer sous le nouveau nom, indépendant de l'ancien secret GitHub. Si tu préfères le renouveler, révoque-le dans @BotFather et place uniquement le nouveau token dans ce secret ; sa révocation coupe immédiatement les anciens programmes qui l'utilisent.

**Ne crée pas de nouveaux secrets** SUPABASE_ACCESS_TOKEN, SUPABASE_DB_URL, SUPABASE_SERVICE_ROLE_KEY, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_D1_DATABASE_ID ni CF_BOT_WEBHOOK_SECRET. Le compte et la base sont configurés dans wrangler.toml (identifiants non secrets), et le secret de webhook est généré automatiquement.

Les anciens secrets GitHub restent en place mais ne sont plus utilisés par ce bot.

## Étape 3 : vérifier les variables GitHub existantes

Dans **Settings → Secrets and variables → Actions → Variables**, vérifie :

| Nom | Valeur |
| --- | --- |
| **XPRONOS_COUPON_ADMIN_IDS** | Identifiant numérique Telegram de l'administrateur ; obtenu avec @userinfobot (ex. 123456789) |
| **XPRONOS_COUPON_CHANNELS_JSON** | [ ] sans canal obligatoire (écrire sans espace : []) ou [{"id":"@mr_xpronos","url":"https://t.me/mr_xpronos"}] |

Le bot doit être administrateur des canaux vérifiés.

La variable **XPRONOS_CF_AUTO_DEPLOY** à true est facultative ; elle permet les futurs redéploiements automatiques. Sans elle, utilise Run workflow.

## Étape 4 : lancer le déploiement

Ouvre https://github.com/MrXPRONOS/MrXPRONOS_App/actions/workflows/xpronos-cloudflare-bot-deploy.yml

Choisis **Run workflow**, branche **main**. Le pipeline :

1. Contrôle la configuration sans révéler les tokens.
2. Exécute les tests (calcul strict des cotes et SQL D1).
3. Applique les migrations uniquement à D1.
4. Déploie le Worker.
5. Enregistre les secrets directement dans Cloudflare.
6. Crée un secret webhook aléatoire et remplace le webhook Telegram pour pointer vers Cloudflare.
7. Vérifie la santé du bot et le webhook.

## Étape 5 : vérifier sur Telegram

Envoie /start puis confirme être majeur. Teste /admin, /bonus, /xp, /tasks, /coupons, /mine, /share.

Exemples de commandes administrateur :

    /addtask @mr_xpronos https://t.me/mr_xpronos 15
    /listtasks
    /addcoupon PRO | 50 | 2099-01-01T18:00 | -1 | Test | Équipe A - Équipe B ; Plus de 1.5 but ; 1.70 | Équipe C - Équipe D ; 1X ; 2.40
    /listcoupons
    /grantxp USER_ID 30
    /stats

L'exemple est **fictif**, uniquement destiné aux tests (1.70 × 2.40 = 4.08). Le parrainage accorde 30 XP une seule fois après validation d'un canal obligatoire ; il est désactivé si aucun canal obligatoire n'est configuré. Bonus 5 XP toutes les 2 h, maximum 10 XP/jour UTC.

## Dépannage

- URL /health → 503 : secrets Worker ou administrateur non configurés.
- URL /health → 200 / ready : Worker prêt à recevoir Telegram.
- Le bot ne répond pas : vérifier l'étape de basculement setWebhook dans GitHub Actions.
- /admin refuse l'accès : vérifier la variable XPRONOS_COUPON_ADMIN_IDS.
- Check canal échoue : ajouter le bot comme administrateur au canal.
- Logs : Cloudflare Dashboard → Workers & Pages → xpronos-coupons-bot → Observability.

Le bot ne dépend plus du quota Egress Supabase, mais les quotas propres à Cloudflare restent applicables.


## V3 — finalisation des améliorations visuelles et fonctionnelles

**Nom public : Free Pronos.** Les identifiants historiques du dépôt, du Worker et de D1 restent inchangés pour protéger les données et le webhook.

- **Logo :** `assets/free-pronos-emblem.svg`; `GET /brand.svg` sur le Worker ; affiché dans l'en-tête et l'accueil de la Mini App. Le workflow peut définir la photo Telegram `setMyProfilePhoto` en JPEG à partir de ce SVG lors d'une fusion marquée `[set-free-pronos-avatar]`.
- **Coupons enrichis :** Mini App affiche équipe domicile/extérieur, compétition, écussons ESPN lorsque le match est référencé et réellement identifié. Le formulaire de publication est dans l'onglet *Admin* pour les identifiants administrateurs autorisés.
- **Résultats automatiques prudents :** scores finaux ESPN uniquement ; marchés supportés : HOME/DRAW/AWAY, OVER_1_5/OVER_2_5/UNDER_2_5, BTTS_YES/BTTS_NO. Les corners, cartons, cotes dynamiques et autres marchés **ne sont jamais évalués à partir du seul score**. Si ESPN est inaccessible ou ne confirme pas la fin du match, aucun résultat gagné/perdu n'est inventé.
- **Résultats manuels :** toujours possibles dans le tableau Admin, avec une source HTTPS ; les URLs des preuves sont visibles dans le bot.
- **Alertes :** opt-in explicite, contrôle des envois via `delivery_audit`, test de livraison à l'administrateur par le workflow `[verify-free-pronos-alerts]`, aucune modification des XP pendant un test.
- **Support :** tickets et réponses via bot ou Mini App, avec état et contrôle des droits.
- **Tableau de bord Admin :** statistiques, publication coupon (IDs ESPN), contrôle des résultats, suivi tickets, bouton test notification, relance manuelle limitée de la vérification des matchs. Sécurisé par la validation cryptographique `Telegram.WebApp.initData`.

### Limites importantes

- Les logos ne peuvent pas être rattachés automatiquement aux anciens coupons dont le modèle ne contient aucun identifiant fiable de match ou équipe : les modifier avec une référence ESPN correcte si nécessaire.
- ESPN n'offre pas nécessairement une couverture complète de toutes les compétitions, catégories et marchés. Le moteur échoue prudemment et garde la revue humaine en secours.
- Un test `sendMessage` accepté prouve que Telegram a reçu le message, **pas** que l'utilisateur l'a ouvert. Les alertes des membres nécessitent leur accord explicite.
- La photo de profil Bot API doit être confirmée via l'étape correspondante du déploiement, et le rendu des boutons peut dépendre de la version de l'application Telegram.

### Commandes et vérifications

`/admin`, `/support`, `/mytickets`, `/results`, `/alerts` et menu Mini App.
`/health`, `/app` et `/api/me` (sans initData → HTTP 401) sont vérifiés par le smoke test du déploiement.
