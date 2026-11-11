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
  --data-urlencode 'allowed_updates=["message","business_message"]'
unset TG_TOKEN TG_SECRET
```

**Si OpenClaw ou un autre programme interroge le même bot avec `getUpdates`, l'arrêter avant ce basculement.** Telegram ne permet qu'un récepteur d'updates par jeton.

## Ce que fait la V2

- Répond en privé aux messages textuels adressés au bot via Telegram Bot API.
- Récupère les pronostics du site dans `data.json` (uniquement catégorie Pro/VIP, date valide, éligibilité publiée, rencontres futures) et les scores exacts dans les fichiers journaliers.
- Affiche les liens officiels; ne fabrique ni rencontres, ni performances, ni conditions VIP.
- Utilise NVIDIA NIM pour les questions générales et conserve une mémoire de conversation isolée.
- Prend en charge la notification et la reprise humaine avec `/reply`, `/pause`, `/resume`.
- Ne touche pas aux mécanismes d'envoi automatique des coupons du canal.

## Limites importantes

- Ce bot ne voit pas automatiquement les messages **du compte Telegram personnel** du propriétaire. Pour cela, il faut connecter explicitement un bot aux conversations **Telegram Business** (avec les droits nécessaires), ou renvoyer les clients vers le bot.
- Le canal des coupons doit être confirmé par le propriétaire. Le lien `https://t.me/mr_xpronos` est publié comme contact officiel, pas nécessairement comme canal des coupons.
- En cas de demande de pronostics, le bot utilise seulement les publications accessibles et valides. Il ne génère pas des pronostics à partir de matchs imaginés.
- L'âge des utilisateurs et les règles locales relatives aux paris doivent être respectés. Aucun pronostic n'est garanti.
- L'API NVIDIA doit être autorisée pour le volume et l'usage de production souhaités.
- Cette fonction est **un déploiement de test** tant que les secrets, le webhook et les essais de bout en bout ne sont pas validés.
