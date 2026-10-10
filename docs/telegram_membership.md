# Adhésion Telegram — Mr XPRONOS

Le même bot Telegram gère les trois canaux :

- Bot : `@mrxpronos_canal_bot`
- Webhook : `telegram-membership` sur Supabase

## Canaux publics

### 1. Pronos Live
- Canal : `@mr_xpronos_vip`
- URL publique : https://t.me/mr_xpronos_vip
- Lien demande d'adhésion : https://t.me/+jfv6ZnqgG9FiMTY0
- Message public épinglé : ID `8318`

### 2. Coupons du jour
- Canal : `@mrxpronosfr`
- URL publique : https://t.me/mrxpronosfr
- Lien demande d'adhésion : https://t.me/+0JhboHktv2s2YWU0
- Message public épinglé : ID `6690`

### 3. Actu Foot
- Canal : `@actufoot_mrxp`
- URL publique : https://t.me/actufoot_mrxp
- Lien demande d'adhésion : https://t.me/+SVA8F6PGw8YyNjBk
- Message public épinglé : ID `348`

## Fonctionnement

1. Un visiteur arrive directement sur un canal public :
   - il peut voir le contenu du canal ;
   - le message CTA épinglé lui propose de rejoindre ;
   - le bouton utilise le lien spécial de demande d'adhésion.

2. Un visiteur arrive depuis une publicité / le site / WhatsApp :
   - utiliser de préférence le **lien demande d'adhésion** correspondant ;
   - Telegram crée alors une demande d'adhésion.

3. Le webhook Telegram envoie automatiquement un petit message privé au demandeur :
   - confirmation de réception ;
   - rappel d'activer la cloche / notifications.

4. Le bot approuve ensuite automatiquement la demande.

## Sécurité

Le bot n'auto-approuve que les demandes provenant des liens créés par Mr XPRONOS, dont le nom Telegram commence par :

`MX_ADHESION_`

Une demande provenant d'un autre lien est ignorée par le webhook.

Le webhook vérifie également l'en-tête secret Telegram dérivé du token du bot.

## Fichiers

- `scripts/telegram_membership_setup.py`
- `supabase/functions/telegram-membership/index.ts`
- `.github/workflows/telegram-membership-setup.yml`

Le workflow d'installation est **manuel uniquement** et démarre en mode vérification par défaut afin d'éviter la création accidentelle de nouveaux liens.
