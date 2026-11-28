# MR X ACADEMY — Bot V1.3.1

Module autonome du dépôt `MrXPRONOS/MrXPRONOS_App`, dossier `academy/`. Worker `mr-x-academy-bot`, compte Cloudflare Personnel de Ciné Radar, base D1 `mr-x-academy`. Aucun PDF ni secret dans le dépôt public. Aucun R2 requis. Mini App et synchronisation Ficsell hors périmètre V1.

## Configuration et connexion

Dans Workers & Pages > mr-x-academy-bot > Settings > Variables and Secrets, ajouter les valeurs (type Secret) :

- `BOT_TOKEN` : token du nouveau bot BotFather, jamais celui de Ciné Radar.
- `WEBHOOK_SECRET` : chaîne aléatoire distincte, 32–256 caractères URL-safe. Générer localement avec `node -e "console.log(require('node:crypto').randomBytes(32).toString('hex'))"`.
- `ADMIN_IDS` : votre identifiant Telegram numérique, obtenu avec `/id` après activation du webhook ; séparer plusieurs IDs par des virgules.
- `STORAGE_CHANNEL_ID` : identifiant numérique `-100...` du canal privé de stockage. Facultatif pour l'envoi direct au bot, indispensable pour importer les publications du canal.
- `SUPPORT_HANDLE` : facultatif, contact public de l'assistance.

La connexion utilise `https://mr-x-academy-bot.ananiolivier44.workers.dev/telegram/webhook` (vérifier l'URL effective du Worker). Ne pas placer les secrets dans un URL de navigateur, GitHub, un fichier public ou une conversation. Le script `scripts/setup-webhook.mjs` configure `message`, `callback_query`, `chat_member`, `my_chat_member` et `channel_post` et ne supprime pas les mises à jour en attente.

PowerShell (Node 22) depuis `academy/` :

```powershell
$env:BOT_TOKEN = Read-Host 'Token BotFather' -MaskInput
$env:WEBHOOK_SECRET = Read-Host 'Secret webhook identique à Cloudflare' -MaskInput
$env:WORKER_URL = 'https://mr-x-academy-bot.ananiolivier44.workers.dev'
node scripts/setup-webhook.mjs
Remove-Item Env:BOT_TOKEN, Env:WEBHOOK_SECRET
```

Ouvrir le bot, `/start`, puis `/id`. Enregistrer `ADMIN_IDS` dans Cloudflare. Pour découvrir un ID de canal, transférer une publication du canal au bot en privé depuis le compte administrateur (les transferts doivent être autorisés). Le bot affiche l'identifiant si Telegram transmet `forward_origin` du canal. Sinon récupérer l'ID depuis le lien d'une publication privée (`t.me/c/1234567890/1` correspond à `-1001234567890`).

## Stockage Telegram privé

1. Créer `MR X ACADEMY — Stockage privé`, type canal privé, ne pas diffuser son lien. Seuls les administrateurs de confiance peuvent publier.
2. Ajouter le bot comme administrateur du canal de stockage ; droits minimaux, pas de suppression ni d'ajout d'utilisateurs requis.
3. Enregistrer `STORAGE_CHANNEL_ID`. Les événements `channel_post` ne sont importés que depuis ce canal autorisé. Ne jamais utiliser le canal de stockage comme canal de parrainage.
4. Publier les fichiers avec ces légendes exactes, après configuration du webhook et des secrets :

| Ressource | Légende |
|---|---|
| PDF gratuit 200 pages | `/file fondamentaux` |
| PDF Premium 492 pages | `/file masterclass` |
| Photo couverture gratuite | `/cover fondamentaux` |
| Photo couverture Premium | `/cover masterclass` |
| Photo de bienvenue | `/banner` |

Le bot enregistre les `file_id` et confirme chaque import en privé à l'administrateur principal. Si un fichier a été envoyé avant configuration, le republier avec sa légende. On peut également envoyer ces ressources directement au bot en privé depuis le compte administrateur. Les fichiers n'ont pas besoin d'être téléchargés vers Cloudflare ; seul leur identifiant est conservé dans D1. Les fichiers PDF doivent avoir un MIME application/pdf et faire au plus 49 Mio dans cette version. La redistribution du gratuit est autorisée ; la protection Telegram est activée pour le Premium, mais ne garantit pas l'impossibilité de toute copie. Garder une sauvegarde locale.

## Publication et campagne

Les deux produits initiaux restent inactifs jusqu'à importation de leurs PDF et publication volontaire. Depuis le bot en privé : `/publish fondamentaux`, `/publish masterclass`. Vérifier le catalogue et l'accès gratuit.

Ajouter le bot comme administrateur du canal public cible, avec le droit d'inviter des utilisateurs. Transférer une publication du canal pour obtenir son ID. Exemple à adapter :

```text
/campaign {"id":"masterclass10","product_id":"masterclass","channel_id":"-100REMPLACER","channel_url":"https://t.me/REMPLACER","target":10,"hold_hours":24}
```

Le bot vérifie ses droits d'invitation. Le canal de stockage n'est jamais une cible de campagne. Le lien public à épingler après test est `https://t.me/VOTRE_BOT?start=c_masterclass10`. Utiliser le vrai username. Une invitation valide correspond à une nouvelle adhésion attribuée au lien individuel, toujours présente après le délai ; pas un simple clic. Aucun pari, dépôt, achat ou inscription chez un bookmaker requis. Éducation sportive 18+, aucune promesse de gains. Ne pas solliciter de messages non consentis.

## Administration multiproduit

- `/admin` : statistiques et commandes. `/id` : identifiant Telegram.
- `/product {"id":"guide-business","title":"Mon guide business","category":"Business","description":"Présentation du guide","price_xof":3000}` : ajouter/modifier un produit (exemple fictif). ID : 1–24 caractères minuscules, chiffres, tirets, underscores. Puis fichier, couverture, `/publish guide-business`.
- `/file ID`, `/cover ID`, `/banner` : légendes dans le canal privé ou en privé avec le bot.
- `/unpublish ID` : masquer le produit sans retirer les droits acquis.
- `/campaign {JSON}` : seuil de 1 à 20, délai 0–168 heures. Nouveau ID pour changer les conditions. `/campaignoff ID` : arrêt d'une campagne.
- `/grant ID_UTILISATEUR ID_PRODUIT` : accorder manuellement un accès après vérification indépendante d'une vente Ficsell. Le client doit avoir ouvert le bot.

Les commandes d'administration ne sont pas publiques. La boutique web indépendante est https://mr-xpronos.myficsell.com/wn53m7wu6, tarif prévu 5 000 FCFA. Les ventes numériques à l'intérieur des bots et Mini Apps utilisent Telegram Stars. Aucun paiement n'est traité par cette V1, aucun webhook Ficsell n'est configuré.

## Tests et maintenance

Node 22.13+ ; `npm install`, `npm run check`, `npm test`. Tests SQLite locaux et API Telegram simulée. `wrangler.jsonc` pointe vers le Worker et D1 existants. La mise en production initiale peut appliquer les migrations via API ; sur un environnement déjà initialisé, ne pas rejouer des migrations destructives. `npm run migrate` et `npm run deploy` pour les mises à jour autorisées depuis le bon compte. Les secrets ne sont pas stockés dans Git.

`/health` : état du service et présence des configurations, sans valeur de secret. Vérifier en réel : `/start`, image, catalogue, accès gratuit, refus du Premium, droits admin ; campagne de test distincte (2 invitations et délai zéro) avec comptes légitimes consentants, doublons et départs, attribution et livraison. Désactiver la campagne de test et activer la vraie à 10/24 h seulement après succès.

Limites : Telegram n'a pas d'historique exhaustif des anciens membres avant l'installation ; les multicomptes ne peuvent pas être totalement détectés. Un compte ne compte qu'une fois par canal. Le cron valide 5 invitations et tente une récompense par passage ; le lecteur peut actualiser et réclamer. Le droit est unique et reste en bibliothèque après erreur d'envoi. Les confirmations d'adhésion nécessitent les droits et le webhook correctement configurés. Ne pas publier de liens du canal privé ni de tokens. Mini App et synchronisation des paiements à développer séparément.

## Assistant de création V1.2

En privé, `/admin` ou bouton Administration → Nouvelle formation. Sept étapes : titre, catégorie, prix (0 = gratuit), description optionnelle (0 ou bouton), couverture (photo), PDF, aperçu. Publier ou garder en brouillon. Pause, retour, annulation et reprise possibles. Le bot doit pouvoir publier dans le canal privé de stockage : les fichiers sont automatiquement archivés. Gérer les formations permet de compléter/modifier les deux produits initiaux, conserver les valeurs existantes, tester le PDF, publier ou masquer. Les anciennes commandes restent disponibles. Pour modifier le prix d'un produit déjà publié, le masquer d'abord. Les campagnes restent configurées avec /campaign. Les fichiers déjà archivés restent dans le canal après annulation. Aucun changement de secrets requis.

## Premium V1.3

Les livres payants ajoutent les étapes : URL HTTPS de la boutique web indépendante (facultative, visible à l'administrateur seulement), nouvelle campagne ou conservation des campagnes existantes, canal public/privé, sélection Telegram ou transfert d'une publication ou ID numérique/lien de publication, objectif 1–20 nouveaux abonnés et délai 0–168 h. Le bot vérifie ses droits d'invitation, refuse le canal de stockage et génère son propre lien d'entrée privé. Les participants reçoivent chacun leur lien individuel. Le menu Gérer les formations → Gérer les campagnes affiche le lien du bot à publier dans le canal, les statistiques et permet l'arrêt explicite. Les droits acquis restent en bibliothèque. Une adhésion ne compte qu'une fois par canal, y compris entre campagnes. Les anciennes campagnes ne sont pas supprimées par une nouvelle. Le lien Ficsell n'est pas un bouton de paiement Telegram : achat indépendant et validation manuelle /grant ; Telegram Stars non implémenté. Les fichiers restent protégés selon les droits existants. Aucun secret ni migration supplémentaire.

## Présentation V1.3.1

Les messages et légendes utilisent les entités Telegram (gras, italique, citation, soulignement et code), calculées sur le texte original en UTF-16. Aucun titre ou description saisi par un administrateur n'est interprété comme du HTML ou Markdown. Le message /start est enrichi et garde la bannière enregistrée. La description de profil avant /start reste du texte simple, conformément à setMyDescription. Aucun changement de données ni secrets.

## V1.4 — Produits numériques multiformats et promotions

L'assistant reçoit jusqu'à 100 ressources ordonnées (documents de tout type, vidéos, audios, vocaux, images, animations, liens HTTPS). Envoyer une ressource à la fois puis cliquer Terminer les ressources ; les fichiers sont archivés par file_id dans le canal privé. Une ressource est envoyée directement ; un pack ouvre une bibliothèque paginée, chaque téléchargement vérifie les droits. Les anciens PDF restent compatibles sans migration. Les liens externes ne bénéficient pas d'une protection après ouverture. Les promotions génériques permettent de sélectionner un produit publié, une destination publique/privée ou partage externe, un texte et une couverture ; l'envoi exige confirmation et permission de publication. Le canal de stockage est exclu. La promotion combinée Fondamentaux + Masterclass reste disponible. Aucun fichier Premium n'est envoyé dans un canal public par cette fonction. Les limites de Telegram s'appliquent ; les fichiers existants sont renvoyés via file_id, sans rechargement dans le Worker.
