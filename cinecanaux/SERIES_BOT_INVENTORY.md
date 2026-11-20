# CinéX — Inventaire des canaux privés Séries (Bot API uniquement)

## 1. Variable GitHub

Dans `MrXPRONOS/MrXPRONOS_App` > **Settings** > **Secrets and variables** > **Actions** > **Variables**, créer une variable de dépôt :

- **Name** : `CINEX_SERIES_CHANNEL_IDS`
- **Value** : `-1001234567890 -1009876543210 -1005555555555`

Coller les vrais identifiants des canaux privés des séries séparés par **un espace**. Les retours ligne, virgules et points-virgules sont aussi reconnus. Jusqu'à 50 canaux, doublons ignorés. Chaque identifiant doit commencer par `-100`.

## 2. Lancer la vérification

Ouvrir **Actions** > **CineX Séries — inventorier les canaux avec les bots uniquement** > **Run workflow**.

Le job utilise seulement `FOOTBALL_NEWS_BOT_TOKEN` (ou `TELEGRAM_BOT_TOKEN` comme fallback) pour vérifier l'accès à chaque canal. `TELEGRAM_BOT_TOKEN` est utilisé pour identifier et confirmer le vrai bot Ciné Radar. **Aucune variable `TG_SESSION_STRING`, `TG_API_ID`, `TG_API_HASH` n'est chargée.** Aucun appel Telethon, aucune authentification utilisateur, aucune publication, aucun transfert ou suppression.

Télécharger l'artifact `cinex-series-bot-inventory`. Pour chaque canal : nom, ID, accès du bot publicateur, accès du bot Radar, existence éventuelle d'une affiche épinglée, statut de configuration.

## 3. Limite Telegram importante

Un ID de canal **ne suffit pas** à relire ses anciens messages avec la **Telegram Bot API**, même si le bot en est administrateur. `getChat` peut retourner le **message épinglé**, pas nécessairement le premier message de l'historique. Impossible de promettre « feuilleter tous les anciens messages » via une simple liste d'IDs.

Pour les couvertures et épisodes passés, les options **sans session personnelle** sont :
1. épingler l'affiche dans chaque canal ; `getChat` pourra éventuellement fournir son identifiant ;
2. republier ou transférer au bot les affiches déjà existantes, afin qu'elles soient reçues par le webhook ;
3. fournir explicitement les identifiants des messages existants pour les copier ultérieurement via `copyMessage`, sous réserve des permissions et droits.

Le rapport est **un inventaire**, pas une autorisation de republication. Le système de téléchargement existant conserve ses vérifications de droits et d'intégrité des saisons et sa suppression des copies privées après 24h.

## 4. Canal de secours

La configuration D1 de secours consultée pour les **films** existe. Aucune configuration de secours **Séries** n'a été constatée. Il faudra créer et configurer ce canal avant d'ajouter les boutons de secours dans les publications séries ; le workflow d'inventaire n'envoie rien et n'en crée aucun.
