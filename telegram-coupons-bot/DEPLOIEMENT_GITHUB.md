# XPRONOS 4+ — mise en service depuis GitHub Actions

Ce nouveau déploiement **webhook** s'ajoute au bot Python historique sans démarrer ce dernier. Il utilise une **Edge Function Supabase** et des tables PostgreSQL isolées. Le site, ses autres fonctions et les workflows Telegram existants ne sont pas modifiés. Le programme Python `bot.py` peut toujours être utilisé en local mais **ne doit pas être lancé avec le même token** qu'un webhook actif.

## 1. Créer un NOUVEAU bot

Dans Telegram, ouvre [@BotFather](https://t.me/BotFather) : `/newbot` → nom **XPRONOS 4+**, username libre terminant par `bot` (ex. `XPronos4Bot` si disponible). Copie son token. Il **ne faut pas** réutiliser `TELEGRAM_BOT_TOKEN` déjà utilisé par les autres workflows.

## 2. Secrets GitHub (obligatoires : réutiliser celui de Supabase)

Sur [le dépôt](https://github.com/MrXPRONOS/MrXPRONOS_App/settings/secrets/actions) : Settings → Secrets and variables → Actions → **New repository secret**.

| Nom exact | Valeur | Où l'obtenir |
| --- | --- | --- |
| `XPRONOS_COUPON_BOT_TOKEN` | Token complet de **ce nouveau** bot | `@BotFather` (`/newbot` ou `/token`) |
| `SUPABASE_ACCESS_TOKEN` | Jeton d'accès personnel Supabase **déjà référencé par les autres workflows** de ce dépôt. Ne le recrée pas s'il existe. Il doit autoriser `database:write` pour la création des tables. | https://supabase.com/dashboard/account/tokens |

**Aucun nouveau secret de connexion PostgreSQL n'est nécessaire.** Le workflow utilise l'API de gestion Supabase et le secret existant `SUPABASE_ACCESS_TOKEN` pour appliquer uniquement le SQL du bot. Cette API est expérimentale (Beta) et peut changer. En cas d'erreur 401/403, vérifie les droits de ce token : un droit `database:write` peut être exigé. Le connecteur GitHub permet de lire les noms référencés dans les workflows, **pas de lister les noms réellement enregistrés dans les paramètres Secrets** : vérifie donc sa présence dans GitHub Settings.

**Important** : aucun mot de passe, token, lien de connexion secret ou URI PostgreSQL ne doit être écrit dans le code ou dans une discussion publique.

## 3. Variables GitHub (obligatoire + optionnelles)

Settings → Secrets and variables → Actions → **Variables** → New repository variable.

| Nom exact | Valeur |
| --- | --- |
| `XPRONOS_COUPON_ADMIN_IDS` | Obligatoire : ton ou tes identifiants Telegram **numériques**, séparés par une virgule ; tu peux les connaître avec `@userinfobot` |
| `XPRONOS_COUPON_CHANNELS_JSON` | Optionnel : `[{"id":"@mr_xpronos","url":"https://t.me/mr_xpronos"}]` si le bot est administrateur du canal, ou `[]` pour démarrer sans canal obligatoire |
| `XPRONOS_COUPON_DEPLOY_ENABLED` | Optionnel : `true` pour que les changements futurs du code déclenchent automatiquement le déploiement. Sans cela, l'action reste **manuelle**. |

Pour un canal privé, `id` est son identifiant numérique `-100...` **encodé comme chaîne JSON**, et `url` est son lien d'invitation.

## 4. Démarrer depuis GitHub

1. Ouvre https://github.com/MrXPRONOS/MrXPRONOS_App/actions/workflows/xpronos-coupon-bot-deploy.yml
2. Clique **Run workflow**, branche **main**, puis lance.
3. Le workflow : teste le calcul des cotes, initialise les tables isolées via l'API Supabase avec `SUPABASE_ACCESS_TOKEN`, déploie **une** fonction, lui configure les secrets, génère un secret webhook aléatoire, configure Telegram et vérifie l'URL enregistrée.
4. Ouvre ton bot sur Telegram, envoie `/start`, valide 18+, rejoins les canaux requis, puis `/admin` et `/addcoupon ...`.
5. Pour vérifier les abonnements Telegram, **ajoute le bot en tant qu'administrateur** dans chaque canal obligatoire ou utilisé comme mission.

Aucun secret `SUPABASE_SERVICE_ROLE_KEY` à créer dans GitHub : Supabase fournit automatiquement une clé serveur à ses propres Edge Functions. Les fonctions SQL atomiques sont réservées au rôle `service_role` et les tables ont leur RLS activée.

## 5. Commandes

`/start`, `/xp`, `/tasks`, `/bonus`, `/coupons`, `/mine`, `/share`, `/verify`, `/help`.

Admin : `/admin`, `/addcoupon`, `/listcoupons`, `/delcoupon`, `/activatecoupon`, `/addtask`, `/listtasks`, `/deltask`, `/grantxp`, `/stats`.

Exemple **fictif** :

```text
/addcoupon PRO | 50 | 2099-01-01T18:00 | -1 | Coupe test | Équipe A - Équipe B ; Plus de 1.5 but ; 1.70 | Équipe C - Équipe D ; 1X ; 2.40
```

Cote totale calculée : 4.08. Le bot refuse toute cote strictement inférieure à 4.00 **avant arrondi**. Les XP sont virtuels, non convertibles en argent, et les coupons ne garantissent aucun gain. L'accès 18+ reste déclaratif. Aucune cote en direct n'est récupérée automatiquement.

## 6. Dépannage

- Échec HTTP 401/403 de l'API de gestion Supabase : contrôler que `SUPABASE_ACCESS_TOKEN` existe dans GitHub et possède le droit `database:write`. L'API d'exécution SQL est en Beta et peut ne pas être disponible selon le compte.
- **HTTP 402 Supabase (observé le 22 octobre 2026)** : Telegram atteint bien le webhook, mais la passerelle Supabase refuse les requêtes. Les autres endpoints REST et Edge du projet renvoient aussi 402 : ce n'est pas un bug du bot ni un nom de secret GitHub. Sur le projet `nhwafcpndlufzzxexikh` (organisation actuellement Free), ouvre **Supabase Dashboard → Organization → Usage**, puis **Billing** : identifie le motif exact (`exceeded_*` ou `overdue_payment`) et traite la restriction via le compte Supabase. Tu peux consulter https://supabase.com/docs/guides/troubleshooting/http-status-codes et https://supabase.com/docs/guides/platform/billing-faq. Une fois l'accès rétabli, relance ce workflow, puis teste `/start`.
- Le déploiement vérifie désormais la réponse HTTP de la passerelle **avant de remplacer le webhook** ; `404` sur GET est attendu (la fonction accepte seulement POST), tandis que `402` bloque le workflow avec un message explicite.
- `Webhook invalid token` : token `BotFather` invalide ou révoqué.
- Le bot répond, mais `Check` échoue : bot absent des admins du canal, ou `id` du canal erroné.
- Pas de bonus par parrainage avec `[]` : **normal**, les primes de parrainage sont désactivées sans vérification d'un canal obligatoire.
- 500 sur webhook : vérifier Logs > Edge Functions dans Supabase et la sortie du workflow GitHub.
- Ne pas lancer simultanément `python bot.py` avec le même token : le webhook remplace le polling sur ce token.

**Réserve** : le service est dépendant des limites, de la disponibilité et de la tarification de Supabase. Il n'est pas hébergé dans GitHub Pages.
