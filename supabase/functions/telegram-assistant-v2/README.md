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
