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
| `MX_ASSISTANT_NVIDIA_MODEL` | Ancien paramètre facultatif, **ignoré** par le nouveau moteur de secours ; priorité définie dans `NVIDIA_MODELS` du code |
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
- Utilise **NVIDIA NIM pour tous les messages ordinaires** (y compris salutations, remerciements, FAQ, inscriptions et coupons) et conserve une mémoire de conversation isolée. Les modèles de réponse préécrits ne sont utilisés qu'en secours.
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

**Politique de réponse :** une phrase de 10 à 35 mots par défaut pour NVIDIA NIM, deux phrases si nécessaire ; développement uniquement sur demande explicite. Le bot ne répète pas les salutations, les promotions ou les liens inutilement. Les FAQ sont désormais rédigées **par l'IA en priorité**, avec des données vérifiées fournies par le serveur. Les réponses préécrites sont seulement un secours si l'IA échoue.

**Politique des boutons :** les boutons ne sont plus ajoutés sur les salutations, conversations générales, simples conseils ou questions « quel est le code promo ? ». Ils apparaissent seulement sur des demandes de pronostics, scores, résultats, canal, accès au site ou liens/conditions d’offres. Le rendu `/format` reste une démonstration volontaire. Les liens hors de ce contexte sont masqués, y compris s’ils ont été ajoutés par l’IA.

**Ne pas activer Telegram Business pendant les essais.** Garder le webhook et les bots de coupons existants isolés. Pour tester : `/start`, `Quel est ton code promo ?`, `Les pronostics sont gratuits ?`, `Vous publiez chaque jour ?`, `Je veux les coupons du jour`, `Comment rejoindre votre canal ?`, `Merci`.

## Correctifs de conversation, inscriptions et sitemap — 17 novembre 2026

- Réponses naturelles aux messages courants : `Merci !`, `D'accord`, `Parfait`, désormais générées par NVIDIA NIM si disponible, sans bouton superflu.
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


## Moteur NVIDIA multi-modèles avec secours automatique (17 novembre 2026)

Les modèles sont désormais **définis directement dans `index.js`**, par ordre de priorité strict. Le programme ne se limite plus à `MX_ASSISTANT_NVIDIA_MODEL` :

| Priorité | Identifiant NVIDIA NIM |
| --- | --- |
| 1 | `minimaxai/minimax-m3.1-flash` |
| 2 | `nvidia/nemotron-3-ultra-550b-a55b` |
| 3 | `nvidia/nemotron-3.5-super-vl-120b-a12b` |
| 4 | `stepfun-ai/step-5-preview` |
| 5 | `nvidia/nemotron-3.5-lightning-30b-a3b` |
| 6 | `mistralai/mistral-large-4-1t-a52b` |
| 7 | `z-ai/glm-5.3-flash` |
| 8 | `openai/gpt-oss-20b` |
| 9 | `meta/muse-glimmer-30b` |
| 10 | `poolside/laguna-xs-2.1` |

- Pour une demande générale traitée par l'IA, le bot teste le premier modèle. Il essaye le suivant si l'API renvoie un code d'erreur non global, une réponse vide ou une erreur réseau/un délai dépassé.
- Les codes **401** (clé API invalide) et **402** (crédits insuffisants) arrêtent immédiatement les tentatives : ils ne peuvent pas être résolus en changeant simplement de modèle.
- Un **budget total d'environ 29 secondes** protège le webhook. En cas de nombreux modèles très lents, tous les dix peuvent ne pas être atteints. Les délais par modèle sont volontairement courts et les réponses de service client restent concises.
- La configuration des requêtes reste compatible avec plusieurs modèles : pas de paramètre `reasoning_effort` imposé globalement, car ses valeurs possibles varient selon le fournisseur.
- La commande **`/diagnostic`** (administrateur seulement) teste la chaîne, indique le modèle retenu et le statut des tentatives (sans divulguer la clé, les messages ou le prompt).
- **36 tests automatisés** du code passent, y compris un test simulant la réussite de plusieurs modèles de secours et l'ordre des dix tentatives. Ces tests n'établissent **pas** que les dix modèles sont réellement disponibles avec la clé NVIDIA du compte.
- `MX_ASSISTANT_NVIDIA_KEY` reste obligatoire pour accéder à NVIDIA NIM. La connexion Telegram Business du propriétaire reste désactivée et le bot de publication des coupons ne change pas.



## Aliases bookmakers et salutations — 17 novembre 2026

- `line bet`, `Line-Bet`, `Line_Bet` et `linebet` sont tous reconnus comme **Linebet**. Même logique pour `1 x bet`, `bet winner`, `mel bet`, `1 win` et `bet clic`.
- Quand le bot a demandé « Sur quel bookmaker souhaites-tu t'inscrire ? », une réponse courte comme `line bet` déclenche le guide du bookmaker correspondant avec son lien partenaire déjà vérifié dans le catalogue.
- La commande `/start` continue à présenter l'assistant. Lorsqu'une discussion a déjà commencé, un salut simple tel que `cc` ou `bonjour` reçoit seulement une réponse brève, sans répéter les services ni le code promo.
- La reconnaissance des alias est déterministe et ne dépend pas de NVIDIA ; un faux positif sur un nom étranger comme `Alicenet` n'entraîne pas de redirection partenaire.
- Les boutons partenaires sont des éléments Telegram `reply_markup.inline_keyboard` et peuvent ne pas figurer dans les copies textuelles d'une conversation.

Tests automatiques de la version initiale : 40 réussis, plus simulations de messages avec un compte administrateur. La version IA d'abord passe 46 tests et une simulation de quatre conversations.


## Architecture IA d'abord — 17 novembre 2026

Le **modèle NVIDIA NIM est désormais le cerveau conversationnel**. L'assistant n'utilise plus le routage de 15 à 20 textes préécrits comme réponse prioritaire. Sur chaque message Telegram ordinaire, il :

1. Recharge l'historique isolé de la conversation (jusqu'à 8 messages), les faits confirmés de Mr XPRONOS et, si la question le demande, les données des pronostics/scores et le sitemap.
2. Interroge le premier modèle NVIDIA disponible de la liste des 10 priorités, avec basculement automatique en cas d'échec.
3. Demande au modèle un objet JSON court de la forme `{"reply":"réponse naturelle","buttons":["pronos"]}`. La réponse textuelle est librement rédigée par l'IA et peut contenir du formatage Telegram.
4. Convertit **uniquement** les identifiants de boutons proposés par l'IA en URL déjà validées dans le code (`pronos`, `channel`, `historique`, `partner_linebet`, etc.). Un filtre supplémentaire évite les liens d'affiliation non demandés et les boutons décoratifs.
5. Envoie le message et garde l'historique de la réponse pour les relances.

Le code continue de prendre en charge les éléments qui ne doivent pas être laissés à une IA : authentification du webhook, permissions Business (toujours désactivé), contrôles d'âge / détresse liés aux paris, commandes administrateur et reprise humaine. Le `/format` de démonstration est également déterministe.

**Dégradation contrôlée :** si NVIDIA ne renvoie aucune réponse exploitable ou échoue, le bot conserve d'anciens messages prédéfinis pour ne pas laisser les clients sans réponse. Ce n'est plus le chemin normal.

**Vérification :** 46 tests automatiques du code réussis et simulation de quatre messages successifs (`Merci !`, inscription Linebet, coupons du jour, `cc`) ayant tous entraîné une requête NVIDIA, avec boutons contextuels et données de coupon injectées dans le prompt. Le fonctionnement avec la vraie clé NVIDIA nécessite encore le test dans Telegram.

**Confidentialité :** les messages des clients traités par ce mode sont transmis à l'API NVIDIA pour générer les réponses. Ne jamais journaliser les clés API ni les conversations en clair.

## Boutons et formatage contextuels renforcés — 17 novembre 2026

**Architecture IA d'abord préservée.** L'IA NVIDIA reste chargée de rédiger les réponses et de proposer des boutons. Une validation côté serveur vérifie ces boutons, complète les destinations indispensables dans certains contextes et empêche les promotions non sollicitées.

- **Inscription** : si l'utilisateur demande une inscription chez un bookmaker nommé (dont les variantes `line bet` / `1xbet`), le serveur garantit le **bouton partenaire exact** du catalogue GitHub et le code **XPVIP** dans le texte, en indiquant clairement « si accepté » ou une réserve équivalente. Les étapes restent rédigées par NVIDIA.
- **Pronostics/coupons du jour** : boutons vers les pronostics officiels et le canal Telegram, uniquement sur une demande de consultation ou de réception.
- **Canal Telegram** : bouton vert pointant vers l'URL vérifiée `https://t.me/mrxpronosfr`, ou la valeur valide du secret `MX_ASSISTANT_COUPONS_CHANNEL_URL`.
- **Site et rubriques** : bouton vers l'accueil ou la rubrique demandée (résultats, conseils, analyses, scores exacts, bonus). Ne pas ajouter de bouton site à chaque réponse.
- **Salutation, remerciement ou simple code promo** : pas de bouton commercial non sollicité.
- Les choix de boutons de l'IA sont filtrés une seconde fois selon la question, le bookmaker choisi et l'historique. Un bouton hors sujet, même vers un site officiel, est ignoré.
- **Formatage** : les titres d'inscriptions, de coupons et de canal sont en gras ; le code `XPVIP` est mis en valeur ; les précisions peuvent être en italique. NVIDIA peut produire une citation `>`, un ~~barré~~ ou un `||spoiler||` lorsque le contexte le justifie. Le moteur HTML Telegram échappe le contenu non fiable avant le rendu.

**Tests :** 56 tests de fonctions et de formatage réussis. Simulation d'une conversation avec NVIDIA ayant renvoyé `buttons: []` : le message d'inscription Linebet inclut XPVIP et son bouton ; les coupons incluent les boutons pertinents ; le canal renvoie au canal officiel ; les messages de remerciement n'ont pas de bouton.

Le bot de coupons `telegram_webhook` et le compte personnel Telegram Business restent séparés. Leur configuration n'est pas modifiée.


## Typographie et paragraphes automatiques — 17 novembre 2026

Les réponses de **NVIDIA NIM restent générées librement**, puis passent dans une mise en forme légère pour la lecture mobile Telegram :

- **Gras** pour un titre de rubrique et les informations clés (notamment XPVIP, type de pronostic, intitulé d'inscription), sans mettre chaque phrase en gras.
- Ligne vide après un titre, entre deux idées, avant un avertissement et entre un développement et un complément important. Pas de paragraphes artificiels pour un salut ou un simple merci.
- Guide d'inscription : étapes numérotées sur des lignes distinctes et bloc séparé pour le code XPVIP lorsqu'il manque.
- *Italique* pour les conditions ou réserves ; citation Telegram pour un avertissement de prudence suffisamment important. Souligné, barré et spoiler seulement si leur usage a du sens.
- L'IA est explicitement guidée dans le prompt pour produire des phrases courtes, un titre seul quand utile et des paragraphes aérés. Le serveur n'ajoute pas de fait ou de recommandation de pari.
- Le texte est échappé et converti en HTML pris en charge par l'API Telegram. Les URL restent transformées en boutons uniquement selon le contexte.
- Le formatage s'applique également aux réponses de secours si NVIDIA est indisponible. La commande `/format` affiche les styles avec espaces et sauts de ligne comme exemple de vérification.

Tests du code : 64 réussis, y compris espacement, sécurité HTML, titres, italique, citations, étapes, message court sans formatage forcé et non-régression des boutons.



## Étapes d'inscription et saisie du code XPVIP — 17 novembre 2026

- **Espacement du guide :** même si le modèle écrit `Une fois sur le site, 1. Inscription`, la première étape commence désormais après **une ligne vide**. Les étapes 2, 3, etc. commencent chacune sur une ligne distincte. Les variantes `1, inscription`, `1)` et les étapes déjà à la ligne sont prises en charge. Les cotes `1.50` et sélections `1X` ne sont pas modifiées.
- **Instruction directe :** pour une inscription chez un partenaire identifié, l'assistant présente dans un paragraphe autonome `🎁 **Code promo : XPVIP**` suivi de `Repère le champ **Code promo** du formulaire et saisis **XPVIP**.`. La formule « si le champ existe » est éliminée des instructions générales d'inscription.
- Les instructions relatives à la présence du champ sont formulées selon l'indication du propriétaire du service. **La disponibilité d'un champ et l'acceptation du code ne sont pas garanties sur chaque formulaire/pays**, et les conditions éventuelles des offres restent celles du bookmaker ; éviter de promettre un bonus.
- Si le modèle fournit déjà une étape ou ligne promo ambiguë, le serveur évite de la répéter et affiche le bloc unique de code. Les étapes restantes sont renumérotées si nécessaire.
- NVIDIA continue de rédiger librement le guide, les réponses courtes, les introductions et les relances. Le post-traitement ne corrige que la mise en page et les renseignements du service imposés par la configuration.
- Le lien partenaire reste un **bouton Telegram** seulement dans le contexte d'une inscription chez ce partenaire. Aucun lien brut n'est envoyé à l'utilisateur.

Vérifications : **74 tests automatisés réussis** et simulation de conversation NVIDIA → Telegram confirmant le saut de ligne avant `1. Inscription`, le bloc XPVIP sans conditionnel, la conservation de l'ordre des étapes et le bouton Melbet.


## Messages multiples, tutoriels guidés et médias — 17 novembre 2026

**NVIDIA reste le cerveau principal.**

- **Messages longs** : 1 à 5 messages Telegram par réponse, coupés aux paragraphes. Le titre reste avec son premier paragraphe ; les boutons officiels ne se trouvent que sur le dernier message. Les réponses courtes ne sont pas découpées.
- **Guidage interactif** : sur « pas à pas », « étape par étape », « guide-moi », l'IA donne UNE SEULE action, demande de répondre « fait », puis utilise l'historique existant pour continuer à l'étape suivante. En cas de blocage, elle reste sur l'étape en cours. Le code promo XPVIP est expliqué à l'étape appropriée.
- **Images** : photo Telegram ou document JPEG/PNG téléchargé via `getFile` (6 Mo maximum) et analysé avec `nvidia/nemotron-3.5-super-vl-120b-a12b` ; secours `nvidia/nemotron-nano-12b-v2-vl`. La description visuelle est transmise à NVIDIA conversationnel, sans traiter le contenu de l'image comme des instructions fiables.
- **Vocales** : reconnaissance des messages Telegram Ogg/Opus et fichiers WAV/MP3. Avec un endpoint Nemotron Transcribe compatible Ogg, l'enregistrement est transcrit, puis le texte est traité par NVIDIA conversationnel. Sinon, un essai se fait via `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`.
- **Limite importante** : la compatibilité Ogg/Opus n'est pas documentée pour l'endpoint Omni hébergé (WAV/MP3 sont documentés). Un service ASR adapté est requis pour une transcription fiable des vocaux Telegram. Si rien ne fonctionne, le bot signale honnêtement l'échec.
- Les fichiers sont récupérés côté serveur : aucune URL de téléchargement Telegram contenant le jeton du bot n'est transmise à NVIDIA. Pour les fichiers > 175 ko, l'API officielle NVCF Asset est utilisée avec un asset privé. Les fichiers médias ne sont pas stockés dans la base du bot.

### Secrets facultatifs pour la transcription

- `MX_ASSISTANT_ASR_URL` : URL HTTPS complète de `/v1/audio/transcriptions` sur un service Nemotron Transcribe compatible Ogg/Opus configuré par l'administrateur. Ne pas inventer d'endpoint public.
- `MX_ASSISTANT_ASR_KEY` : clé privée optionnelle du serveur ASR ; sinon la clé NVIDIA principale est utilisée.
- `MX_ASSISTANT_ASR_MODEL` : modèle optionnel si l'endpoint ASR en exige un.
- `MX_ASSISTANT_NVIDIA_KEY` : la clé NVIDIA déjà configurée ; aucune modification requise pour les images.

**Validation** : 89 tests fonctionnels et simulation de la réception de trois événements Telegram (démarrage du guide, confirmation « fait », analyse photo). Un essai avec la clé réelle reste nécessaire pour les endpoints multimodaux.

Le bot de coupons historique et le compte personnel Telegram Business restent indépendants et inchangés.
