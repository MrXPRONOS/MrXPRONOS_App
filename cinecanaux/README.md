# CinéCanaux — Telegram Bot sur Cloudflare

Service: `cinecanaux-bot` · D1: `cinecanaux-directory`

## Fonctionnalités
Menu Films/Séries/Animés par genres, recherche sur canaux approuvés, propositions modérées, vérification d'abonnement aux canaux officiels via `getChatMember`. Aucun lien de diffusion ne doit être publié sans autorisation.

## Mise en service Telegram
1. Créer le bot avec [@BotFather](https://t.me/BotFather), conserver le jeton privé.
2. Dans Cloudflare Workers > `cinecanaux-bot` > Settings > Variables and Secrets, ajouter deux secrets: `TELEGRAM_TOKEN` (jeton BotFather) et `TELEGRAM_WEBHOOK_SECRET` (chaîne aléatoire d'au moins 32 caractères, lettres/chiffres/_/-).
3. Configurer le webhook Telegram vers `https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/telegram` avec `secret_token` égal à `TELEGRAM_WEBHOOK_SECRET`. Ne jamais mettre les secrets sur GitHub.
4. Ajouter le bot comme administrateur de chacun de tes canaux obligatoires. Insérer les canaux dans D1:
```sql
INSERT INTO owned_channels(chat_id,title,link) VALUES ('@nomducanal','Nom du canal','https://t.me/nomducanal');
```
5. Insérer des canaux validés uniquement après vérification des droits:
```sql
INSERT INTO channels(title,link,description,content_type,genre,status,rights_confirmed)
VALUES ('Canal autorisé','https://t.me/exemple','Films du domaine public','films','action','approved',1);
```
6. Tester `/health` et `/start` depuis Telegram.

## Déploiement
`npx wrangler deploy` depuis le dossier `cinecanaux/`. Schéma initial dans `schema.sql` ; exécuter les migrations uniquement si nécessaire.

## Limitations
Recherche dans la base D1 uniquement; découverte externe automatisée et inspection historique des vidéos non intégrées. Le bot n'est pas utilisable dans Telegram tant que les secrets et le webhook ne sont pas configurés. Éviter les doublons et les canaux sans droits de diffusion.

## Provision automatique du webhook
Le Worker possède un handler `scheduled` déclenché par Cloudflare toutes les cinq minutes. Tant que le webhook n'est pas installé, il tente `setWebhook` directement depuis le Worker avec les secrets `TELEGRAM_TOKEN` et `TELEGRAM_WEBHOOK_SECRET`; aucune valeur n'est exportée ni ajoutée au dépôt GitHub. Le statut de cet enregistrement est conservé dans `bot_webhook_status` (table créée dans D1). Après succès, les exécutions suivantes s'arrêtent après le contrôle de la base. Si les secrets changent, remettre cet état à jour via `DELETE FROM bot_webhook_status WHERE id=1;` pour redéclencher l'installation.


## Réutilisation du moteur de découverte CinéX (22 octobre 2026)

Le workflow existant `.github/workflows/telegram-discovery-daily.yml` et le script `telegram-film-relay/scripts/discovery_daily.py` conservent leur fonctionnement actuel : recherche via **la session personnelle Telegram déjà définie dans GitHub**, lecture publique sans rejoindre les canaux, digest privé dans « Messages enregistrés » et état sauvegardé dans `telegram-film-relay/state/discovery_daily_state.json`.

**Aucun nouvel identifiant Telegram ou GitHub n'est requis pour cette synchronisation.** Le Worker Cloudflare lit le fichier JSON public du dépôt via HTTPS, toutes les quatre heures (cron `0 */4 * * *`, heure UTC) et l'importe dans **Cloudflare D1**. Le code n'importe jamais les jetons ou les messages privés.

- `discovery_candidates` : table dédiée aux canaux détectés, dédoublonnés par nom d'utilisateur.
- `technical_status=qualified` : canal public et non protégé, avec au moins 2 couples affiche/vidéo vérifiés par le moteur existant.
- `technical_status=rejected_format` : format non suffisamment confirmé.
- `rights_status=unverified` : droits non validés, même quand une vidéo est présente.
- `discovery_sync_status` : horodatage du dernier scan et compteurs d'import.

Le bot Telegram lit uniquement la table `channels` **où `status='approved' AND rights_confirmed=1`** : un canal découvert automatiquement n'est jamais publié sur ce seul critère. Pour publier un canal, il faut avoir établi les droits de diffusion, puis l'approuver dans D1. Par exemple, **après vérification et validation effective des droits** (adapte le nom d'utilisateur) :

```sql
INSERT INTO channels(title,link,description,content_type,genre,status,rights_confirmed)
SELECT title,link,'Canal autorisé',content_type,genre,'approved',1
FROM discovery_candidates
WHERE username='NOM_CANAL_A_VERIFIER' AND technical_status='qualified'
ON CONFLICT(link) DO UPDATE SET
 status='approved',rights_confirmed=1,updated_at=CURRENT_TIMESTAMP;
```

Pour examiner les nouveaux canaux :

```sql
SELECT username,title,content_type,genre,matching_pairs,technical_status,
       rights_status,last_scan
FROM discovery_candidates ORDER BY last_seen DESC LIMIT 50;
```

Les catégories reconnues par l'ancien moteur sont Films, Comédie, Romance/Désir et Animés. Une vraie classification détaillée des séries et des sous-genres nécessitera des critères ou recherches supplémentaires. La détection d'une pièce jointe vidéo et d'une affiche ne garantit ni le titre du film ni sa légalité.


## Design Telegram et parrainage (22 octobre 2026)

- Tous les messages utilisent `parse_mode: HTML` : gras, italique, citations `<blockquote>` et échappement HTML des données provenant des utilisateurs ou du catalogue.
- Les boutons utilisent `style: primary` (bleu) et `style: success` (vert), pris en charge depuis Telegram Bot API 9.4 (couleurs adaptées par le client et son thème).
- Le menu inclut **🎁 Parrainage** et **📊 Mes filleuls**. Les commandes correspondantes sont `/parrainage`, `/inviter`, `/mesparrainages` et `/aide`.
- Chaque utilisateur peut générer un lien individuel `https://t.me/<bot-username>?start=ref_<code>` dont le code personnel est enregistré dans `referral_codes`.
- Le bot envoie **deux messages séparés** : une invitation élégante à transférer avec son lien, puis les consignes réservées au parrain. Pour préserver les textes en gras, en italique et en citation, transférer nativement le **premier** message Telegram.
- Le bouton de partage `t.me/share/url` est une alternative simplifiée ; Telegram ne garantit pas qu'il conserve les mises en forme du message original.
- Le suivi des filleuls évite les doublons et le parrainage de soi-même. Les accès confirmés sont enregistrés après validation de l'abonnement aux canaux officiels, s'ils sont configurés.
- Les tables `referral_codes` et `referral_visits` sont définies dans `schema.sql` et déployées dans D1. Aucun jeton Telegram n'est ajouté au dépôt.


## Ciné Radar V2 (22 octobre 2026)

- Rebranding « Ciné Radar » : textes, menu, aide et descriptions programmées du bot.
- Navigation dans un seul message par callbacks Telegram, pagination 5 canaux/page, filtres Films/Séries/Animés et sous-genres.
- Formatage HTML Telegram : gras, italique, citations, statuts colorés et messages d'accueil plus courts.
- Favoris personnels, « Nouveautés », recommandations basées sur catégorie choisie et populaires par favoris.
- Recherche insensible aux accents et tolérance à 1 faute de frappe dans un mot suffisamment long.
- Préférences VF, VOSTFR, VO et notifications strictement volontaires (cron 08:00 UTC).
- Vérification périodique prudente : accessibilité HTTP du site public d'une chaîne Telegram ; HTTP 403/429/inconnu n'implique pas le retrait automatique.
- Signalements dédoublonnés et tableau d'administration privé accessible aux comptes ajoutés explicitement dans \`admin_users\`. AUCUN administrateur n'est créé par défaut.
- Pour activer l'administration, récupérer son propre identifiant via la commande \`/monid\`, puis l'inscrire dans D1 :
\`\`\`sql
INSERT OR IGNORE INTO admin_users(user_id,role) VALUES(123456789,'owner');
\`\`\`
- Validation des droits à effectuer explicitement, via justificatif enregistré avant publication.
- Référencement des liens après droits établis uniquement (\`status='approved'\` + \`rights_confirmed=1\`).
- Mini App responsive à l'adresse \`https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/app\`, accessible depuis le menu Telegram. Elle présente le catalogue avec recherche, filtres, favoris, navigation et profil. Les API vérifient cryptographiquement \`Telegram.WebApp.initData\` et l'appartenance aux canaux obligatoires.
- Le lien du bot existant ne change pas automatiquement : son **nom affiché** est modifié par l'API Telegram, mais son **@username** se modifie uniquement dans BotFather.
- La bannière SVG est servie sur \`/assets/banner.svg\` ; le message d'accueil du bot reste textuel en attendant une version JPEG/PNG.
- Mini App, recherches et notifications nécessitent une validation réelle sur Telegram avant de déclarer l'ensemble « entièrement testé en production ».
