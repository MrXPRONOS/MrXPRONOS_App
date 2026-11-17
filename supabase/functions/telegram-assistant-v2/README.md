# Mr XPRONOS — Telegram Assistant V2 (NVIDIA NIM)

## Statut

Fonction Supabase `telegram-assistant-v2` déployée dans le projet `nhwafcpndlufzzxexikh`. **Aucun webhook Telegram n'est basculé automatiquement.** Le bot de coupons reste indépendant.

Cette version s'inspire du bot conversationnel Supabase existant `telegram_webhook`, sans modifier son code, sa configuration ou son jeton Telegram. Le code n'utilise pas Claude/OpenClaw.

## Configuration obligatoire

Dans Supabase > Edge Functions > Secrets, renseigner :

| Variable | Description |
| --- | --- |
| `MX_ASSISTANT_TELEGRAM_TOKEN` | Token BotFather du bot **assistant**, distinct du bot coupons |
| `MX_ASSISTANT_TELEGRAM_WEBHOOK_SECRET` | Secret aléatoire de 32+ caractères A–Z a–z 0–9 _ - |
| `MX_ASSISTANT_NVIDIA_KEY` | Clé personnelle NVIDIA NIM, jamais en clair dans GitHub |
| `MX_ASSISTANT_NVIDIA_MODEL` | `mistralai/mistral-large-4-1t-a52b` |
| `MX_ASSISTANT_ADMIN_ID` | ID Telegram du propriétaire/administrateur |
| `MX_ASSISTANT_COUPONS_CHANNEL_URL` | Lien **vérifié** du canal qui diffuse effectivement les coupons (facultatif jusqu'à confirmation) |
| `MX_ASSISTANT_ENABLE_BUSINESS` | `true` seulement après validation des tests et autorisation sur Telegram Business ; désactivé par défaut |
| `MX_ASSISTANT_BUSINESS_OWNER_ID` | ID numérique du compte Telegram Business propriétaire (défaut : `MX_ASSISTANT_ADMIN_ID`) |

Supabase injecte automatiquement `SUPABASE_URL` et `SUPABASE_SECRET_KEYS` / `SUPABASE_SERVICE_ROLE_KEY`.

## Contrôles avant ouverture

1. Ouvrir l'URL de la fonction en GET : `https://nhwafcpndlufzzxexikh.supabase.co/functions/v1/telegram-assistant-v2`. Confirmer tous les indicateurs `configured` sauf éventuellement `channel`.
2. Envoyer `/status` au bot depuis **le compte administrateur** après activation du webhook.
3. Envoyer `/start`, « coupons du jour », « scores exacts », « comment rejoindre le canal ? », puis « parler à un responsable » depuis un second compte.
4. Tester `/chats`, `/reply <chat_key> Bonjour`, `/pause <chat_key>` et `/resume <chat_key>`.
5. Tester le webhook : `getWebhookInfo`, vérifier l'URL active et les erreurs éventuelles.

Pour activer le webhook en utilisant le *token du bot assistant* (ne pas partager la sortie, protéger le fichier) :

```bash
read -rsp 'Token Telegram assistant: ' TG_TOKEN; echo
read -rsp 'Secret webhook (identique à MX_ASSISTANT_TELEGRAM_WEBHOOK_SECRET): ' TG_SECRET; echo
curl -sS -X POST "https://api.telegram.org/bot${TG_TOKEN}/setWebhook" \
  --data-urlencode 'url=https://nhwafcpndlufzzxexikh.supabase.co/functions/v1/telegram-assistant-v2' \
  --data-urlencode "secret_token=${TG_SECRET}" \
  --data-urlencode 'allowed_updates=["message","business_connection","business_message"]'
unset TG_TOKEN TG_SECRET
```

**Si OpenClaw ou un autre programme interroge le même bot avec `getUpdates`, l'arrêter avant ce basculement.** Telegram ne permet qu'un récepteur d'updates par jeton.

## Ce que fait la V2

- Répond en privé aux messages textuels adressés au bot via Telegram Bot API.
- **Telegram Business (opt-in)** : après connexion explicite du bot dans les réglages Business du compte, répond dans les conversations privées autorisées. Les réglages Telegram doivent cibler les **non-contacts / nouvelles discussions**. Le code vérifie à chaque message l'identité du compte, `is_enabled`, `rights.can_reply` et la fenêtre de réponse de 24 h ; les messages hors champ sont ignorés.
- Accueille une seule fois un nouvel interlocuteur, puis analyse les messages suivants (intentions : pronostics, scores, liens, historique, conseils, demande humaine), sans envoyer de message spontané.
- Récupère les pronostics du site dans `data.json` (uniquement catégorie Pro/VIP, date valide, éligibilité publiée, rencontres futures) et les scores exacts dans les fichiers journaliers.
- Affiche les liens officiels; ne fabrique ni rencontres, ni performances, ni conditions VIP.
- Utilise NVIDIA NIM pour les questions générales et conserve une mémoire de conversation isolée.
- Prend en charge la notification et la reprise humaine avec `/reply`, `/pause`, `/resume`.
- Ne touche pas aux mécanismes d'envoi automatique des coupons du canal.

## Activer sur le compte Telegram personnel sans perturber les coupons

1. Garder le **bot assistant** distinct du bot qui publie les coupons.
2. Configurer le bot via @BotFather (mode Business), et sur le compte personnel dans **Telegram > Paramètres > Telegram Business > Chatbots** (libellés selon version). Telegram peut exiger un abonnement Premium pour les fonctions Business.
3. Choisir uniquement les catégories de conversations autorisées, idéalement **non-contacts** et **nouvelles discussions** ; conserver les droits de réponse nécessaires. Le périmètre est contrôlé par les paramètres Telegram et non par une liste de contacts accessible au serveur.
4. Vérifier les identifiants `MX_ASSISTANT_ADMIN_ID` et `MX_ASSISTANT_BUSINESS_OWNER_ID`, puis tester une conversation depuis un autre compte.
5. **Seulement après validation**, définir `MX_ASSISTANT_ENABLE_BUSINESS=true`, configurer le webhook de ce bot et relancer les vérifications.
6. Tester une discussion existante, un nouveau contact, une conversation interdite, une discussion mise en pause, puis la révocation du bot. Les messages autorisés pourront recevoir une réponse, mais le bot ne doit pas écrire à ceux qui ne l'ont pas contacté.

## Limites importantes

- Sans connexion explicite dans **Telegram Business**, le bot ne voit pas les messages du compte personnel et ne répond qu’aux utilisateurs qui lui écrivent directement.
- Le canal des coupons doit être confirmé par le propriétaire. Le lien `https://t.me/mr_xpronos` est publié comme contact officiel, pas nécessairement comme canal des coupons.
- En cas de demande de pronostics, le bot utilise seulement les publications accessibles et valides. Il ne génère pas des pronostics à partir de matchs imaginés.
- L'âge des utilisateurs et les règles locales relatives aux paris doivent être respectés. Aucun pronostic n'est garanti.
- L'API NVIDIA doit être autorisée pour le volume et l'usage de production souhaités.
- Cette fonction est **un déploiement de test** tant que les secrets, le webhook et les essais de bout en bout ne sont pas validés.

## Version de développement du 14 novembre 2026

Le code de cette branche inclut désormais les contrôles Telegram Business et les tests correspondants. Le PR reste en brouillon ; **aucun changement de webhook ni de secrets de production n’est réalisé par ce commit**. Les tests de bout en bout dans Telegram restent obligatoires avant activation. Les commandes `/reply`, `/pause` et `/resume` restent réservées à l'administrateur.

## Messages enrichis et boutons colorés (16 novembre 2026)

Les réponses du bot utilisent désormais une mise en forme HTML sûre : gras, italique, souligné, barré, citation, spoiler et code. Le texte de l'IA est échappé avant que les marqueurs **gras**, *italique*, __souligné__, ~~barré~~, ||spoiler|| et `> citation` soient convertis.

- Les liens officiels de la réponse sont convertis en boutons inline Telegram **sous** le texte du message. Les boutons ne peuvent pas être placés au milieu d'une phrase dans un message standard.
- Couleurs de boutons : `primary` (bleu) pour le site et les pronostics ; `success` (vert) pour le canal vérifié et les conseils ; `danger` (rouge) pour une assistance urgente, une réclamation ou un signalement. L'apparence dépend du thème et du client Telegram.
- Les URL non vérifiées ne sont ni affichées ni proposées comme boutons. Les doublons sont supprimés. Sans valeur validée pour `MX_ASSISTANT_COUPONS_CHANNEL_URL`, aucun bouton « rejoindre le canal » n'est inventé.
- Pour vérifier le rendu dans Telegram, envoie `/format` au bot. Il présente les principales mises en forme et trois boutons de liens (bleu, vert et rouge).
- Le texte d'action « Clique sur le bouton ci-dessous » apparaît immédiatement au-dessus des boutons.
- Les commandes existantes, la configuration Business et les webhooks du bot coupons ne sont pas modifiés par cette fonctionnalité.

Une réponse de secours sans formatage ou sans couleurs personnalisées est prévue si un ancien client ou l'API rejette une option.

## Base de connaissances et concision (17 novembre 2026)

Les faits sont centralisés dans `PROJECT_KNOWLEDGE` du fichier `index.js`, en se fondant sur les pages `index.html`, `pronos.html`, `bonus.html`, `historique.html` du dépôt :

- Code partenaire **XPVIP** ; uniquement lorsque le bookmaker accepte ce code, conditions à vérifier.
- Pronostics **Pro** et **VIP** gratuits ; seuil de **79 % de confiance estimée** publié sur la page pronostics (pas une probabilité de gain certaine ni un taux de réussite historique).
- Sélections selon disponibilité des données du jour, jamais de promesse d’un coupon tous les jours. Les réponses sur les coupons et scores exacts lisent toujours les fichiers publics publiés plutôt que d’inventer des matchs.
- Résultats : sélections gagnées, perdues, en attente ; chiffres de réussite calculés sur les seules sélections évaluées.
- Canal indiqué par la page d’accueil : `https://t.me/mrxpronosfr`. Une URL valide en secret `MX_ASSISTANT_COUPONS_CHANNEL_URL` peut la remplacer après vérification.
- Pronostics LIVE temporairement suspendus. Aucune offre VIP payante, promesse de gains ni demande de données sensibles.

**Politique de réponse :** une phrase de 10 à 35 mots par défaut pour NVIDIA NIM, deux phrases si nécessaire ; développement uniquement sur demande explicite. Le bot ne répète pas les salutations, les promotions ou les liens inutilement. Les FAQ connues sont répondues directement, de façon concise.

**Politique des boutons :** les boutons ne sont plus ajoutés sur les salutations, conversations générales, simples conseils ou questions « quel est le code promo ? ». Ils apparaissent seulement sur des demandes de pronostics, scores, résultats, canal, accès au site ou liens/conditions d’offres. Le rendu `/format` reste une démonstration volontaire. Les liens hors de ce contexte sont masqués, y compris s’ils ont été ajoutés par l’IA.

**Ne pas activer Telegram Business pendant les essais.** Garder le webhook et les bots de coupons existants isolés. Pour tester : `/start`, `Quel est ton code promo ?`, `Les pronostics sont gratuits ?`, `Vous publiez chaque jour ?`, `Je veux les coupons du jour`, `Comment rejoindre votre canal ?`, `Merci`.

## Correctifs de conversation, inscriptions et sitemap — 17 novembre 2026

- Réponses naturelles aux messages courants : `Merci !`, `D'accord`, `Parfait`, sans requête NVIDIA ni bouton superflu.
- Un message `Je veux m'inscrire sur 1xBet` ouvre un guide neutre avec conditions d'âge/législation locale, démarches générales et utilisation éventuelle du code XPVIP, uniquement si accepté. Aucune promesse de promotion ni de gains.
- Liens partenaires tirés **exactement** de `assets/js/bonus-catalogue.js` dans le dépôt (1xBet, 1win, Betwinner, Melbet, Linebet, Betclic). Les redirections et conditions doivent être vérifiées régulièrement ; ne jamais inventer un lien partenaire. Les liens sont proposés en boutons seulement en cas de demande d'inscription ou de lien.
- Le sitemap `https://mrxpronos.github.io/MrXPRONOS_App/sitemap.xml` sert de carte officielle pour la navigation ; analyse des URL autorisée uniquement sur `mrxpronos.github.io/MrXPRONOS_App/`, et pages essentielles indexées (accueil, aujourd'hui, pronostics, scores exacts, résultats, analyses, infos, conseils, bonus, contact).
- Quand une personne relance avec `ensuite ?`, `je suis bloqué`, la fonction utilise l'historique récent pour contextualiser sa réponse, sans inventer la navigation réelle de l'interface tiers.
- En cas de réponse NVIDIA vide ou d'erreur, le bot répond de façon adaptée à ce qu'il sait au lieu de demander systématiquement de préciser. Pour le modèle `mistralai/mistral-large-4-1t-a52b`, le nombre de jetons est augmenté et `reasoning_effort: none` est demandé.
- Déduplication des pronostics affichés : même match, même date et même marché/sélection = une ligne seulement.
- La commande administrateur `/diagnostic` vérifie la réponse NVIDIA sans révéler la clé. Elle est réservée au propriétaire via `MX_ASSISTANT_ADMIN_ID`.

### Essais recommandés

`Merci !` ; `daccord` ; `je veux m'inscrire sur 1xbet aide moi` ; `ensuite ?` ; `je suis bloqué` ; `donne ton lien affilié Melbet` ; `quel est ton code promo ?` ; `où trouver l'historique ?` ; `plan du site` ; `je veux les coupons du jour` ; `/diagnostic` depuis le compte administrateur.

Le bot personnel Telegram Business demeure désactivé tant que son propriétaire n'autorise pas cette étape.
