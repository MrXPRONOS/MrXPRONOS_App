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



## Nouveaux utilisateurs, liens cliquables et corpus de 1000 messages — 17 novembre 2026

### Premier message automatique (une seule fois)

- Le bot vérifie si la conversation privée est déjà présente dans `mx_telegram_assistant_chats` ; **uniquement si elle est nouvelle**, il envoie une présentation courte puis deux boutons officiels : le **canal Telegram** `https://t.me/mrxpronosfr` et la **page d'installation** `https://mrxpronos.github.io/MrXPRONOS_App/installer.html`.
- Le message combine du **gras**, du **gras + souligné**, du **gras + italique** et une **citation** présentant une réserve sur les pronostics. La demande du nouvel utilisateur est ensuite traitée normalement par NVIDIA. Un premier `/start` est satisfait par l'accueil, sans second message d'introduction.
- Les anciens utilisateurs ne reçoivent pas une seconde fois cette présentation. Les messages Business personnels restent désactivés.
- L'accueil est basé sur la présence du chat dans Supabase ; comme il ne possède pas encore de marqueur atomique distinct, deux premiers messages strictement simultanés pourraient théoriquement générer deux accueils. Pour une forte simultanéité, prévoir un contrôle atomique spécifique.

### Formatage avancé Telegram

- Rendu HTML sûr pour `**gras**`, `*italique*`, `__souligné__`, `***gras + italique***`, `**__gras + souligné__**`, `*__italique + souligné__*` et `__***les trois styles***__` ; les citations `>`, spoilers `||...||`, barrés `~~...~~` et code restent compatibles.
- Les liens écrits `[clique ici](URL)` sont rendus comme de vrais liens HTML cliquables sur le texte **uniquement si l'URL figure dans le catalogue officiel**. Le HTML arbitraire et les domaines non autorisés sont échappés ou supprimés.
- Maximum **3 boutons visibles par message** par défaut ; les destinations officielles supplémentaires sont converties en liens intégrés au texte. Le moteur de sélection peut maintenant transmettre jusqu'à 5 destinations. Le découpage des messages longs reste disponible.
- La page `installer.html` a été ajoutée à `LINKS`, `BUTTON_KEYS`, à la connaissance officielle et au choix contextuel de destinations. Elle n'est pas remplacée par la simple page d'accueil.

### Corpus QA : 1000 entrées de clients sans doublons

- `tests/fixtures/1000_messages_clients.csv` contient **exactement 1000 messages différents**, répartis entre **50 intentions** (20 entrées par intention) et **5 styles** (200 entrées par style) : standard, SMS abrégé, vocal transcrit, orthographe approximative, message contextualisé.
- Chaque ligne fournit un ID, une intention, un style, le texte utilisateur et le comportement attendu. Les exemples incluent `line bet`, `mel bet`, `Betclic`, `Waris PT`, `Monsieur Espronos`, la PWA, les coupons, les cotes, les fautes de frappe, les vocaux, les photos et des situations de sécurité.
- Ce fichier est un **jeu de tests synthétiques**, pas un ensemble de messages privés réels ni un entraînement automatique de NVIDIA.
- `tests/corpus.test.mjs` valide les 1000 IDs, l'absence de doublons après normalisation, les 50 intentions et les 5 styles. Lancement conseillé : `node --test supabase/functions/telegram-assistant-v2/tests/*.test.mjs` depuis la racine du dépôt.

### Vérification

96 tests de fonctionnalités de l'assistant réussis, plus 3 contrôles automatiques du corpus. Simulation d'échanges avec deux comptes distincts : l'accueil est envoyé une fois par nouveau chat avec les deux destinations ; les messages suivants n'ont pas de nouvel accueil et restent répondus par l'IA.


## Audit des 80 améliorations et garde-fous supplémentaires — 17 novembre 2026

L'audit de mise en service se trouve dans [`AUDIT_80_CHECKLIST.md`](./AUDIT_80_CHECKLIST.md), avec une ligne par amélioration, la preuve disponible et le statut ✅ code/test, 🟡 partiel ou ⬜ à faire.

**Les quatre axes** : (1) compréhension du client, (2) récupération de sources vérifiées, (3) intelligence conversationnelle NVIDIA, (4) contrôle de la réponse avant envoi.

- Détection de fautes SMS (`jvx`, `coupan`, `ajd`, `prono du jr`, etc.), distinction cote totale/coupon/score exact et clarification des marques mal transcrites comme `Bedclicker`.
- Garde-fous déterministes : âge inférieur à 18 ans, pertes de contrôle liées aux paris, partage de codes OTP/mots de passe et demandes de gestion des données ; aucun lien commercial dans les réponses sensibles.
- La réponse de NVIDIA est vérifiée contre les données publiées : aucun coupon ni score exact inventé lorsque les sources ne présentent pas de sélection admissible. Une demande de cote 10 n'est jamais convertie en score exact fictif.
- Les demandes de coupons, même en un seul mot, proposent le site ET le canal Telegram ; la page `installer.html` est reconnue comme officielle même si le sitemap public n'a pas encore été mis à jour.
- Pour la vision NVIDIA, préférence à une variante JPEG de photo Telegram de moins de 120 ko ; pour les fichiers plus importants, le transfert via NVCF peut toujours répondre 410. En cas d'échec, le bot explique comment recadrer ou renvoyer le document comme photo. Aucun succès réel du modèle visuel n'a encore été prouvé.
- Les codes OTP, mots de passe et numéros de type carte sont masqués lorsqu'ils sont consignés dans l'historique de conversation. Les fichiers image eux-mêmes ne sont pas automatiquement expurgés : éviter l'envoi de documents sensibles.
- La conversation conserve jusqu'à 20 messages, dont 12 peuvent être fournis au modèle NVIDIA. Une politique de temporisation évite, au niveau d'une instance chaude, de rappeler sans arrêt un modèle après deux timeouts/erreurs 503.
- La première salutation repose maintenant sur un INSERT atomique dans `mx_telegram_assistant_chats` afin de réduire les doubles messages de bienvenue lors d'une première prise de contact simultanée.
- Les commandes `/restart` et `/stop` permettent de reprendre ou terminer un guidage étape par étape.
- Le sitemap contenant `installer.html` a été **modifié sur la branche de développement** ; la publication effective sur GitHub Pages exige encore la fusion ou l'équivalent sur la branche du site.

**Tests** : 114 tests de fonctions + 5 tests de corpus = **119 réussis** dans un environnement JavaScript simulant les dépendances Edge. Une simulation du webhook vérifie le nouvel accueil, les coupons, les restrictions d'âge et les demandes de gestion de données. Les appels réels NVIDIA et les vocaux Ogg nécessitent toujours une vérification directe.


## Corrections des points partiels — Novembre 2026

Le bilan actualisé est dans [`AUDIT_80_CHECKLIST.md`](./AUDIT_80_CHECKLIST.md) : **52 points couverts par le code et des tests, 23 encore partiels, 5 non réalisés**. Un point marqué « complet » n’est pas une preuve d’un essai réel du modèle sur un vocal ou une image.

### Nouvelles capacités réellement codées

- Guide persistant `mx_telegram_assistant_sessions` avec objectif, bookmaker, étape, dernière instruction et confirmation de transcription. La commande `/restart` repart à l’étape 1 ; `/stop` clôt le guidage. Un changement de sujet explicite met le guide en veille.
- NVIDIA : latences et états d’erreur partagés dans `mx_telegram_assistant_model_events`, politique de temporisation après deux erreurs temporaires, commande administrateur `/health` donnant succès et délai moyen des derniers événements.
- Messages Telegram : reçus par fragment dans `mx_telegram_assistant_delivery_receipts`, permettant de passer les fragments déjà acceptés si la même mise à jour est rejouée. La garantie exactement une fois reste impossible en cas de coupure dans l’instant entre succès Telegram et enregistrement du reçu.
- Vocaux : demande `verbose_json` à Nemotron Transcribe, contrôle qualitatif (troncature, chute vers CTC, répétitions), demande de confirmation, gestion de « Non, j’ai dit… ». Les vocaux Ogg nécessitent un serveur ASR réellement configuré ; aucune confiance chiffrée artificielle n’est présentée.
- Images : description structurée (résumé, textes, boutons, incertitude) et essai du modèle visuel de secours si le premier ne donne pas de réponse exploitable. Les fichiers trop grands continuent à dépendre d’Assets NVCF et peuvent rencontrer HTTP 410.
- Questions clients : correction prudente des noms phonétiques, prise en compte du pays sans inventer la légalité des bookmakers, aide spécifique Android/iPhone/Windows pour installer la PWA, calcul de multiplication uniquement pour les cotes chiffrées fournies par le client, sans prétendre disposer de cotes bookmaker temps réel.
- Rédaction : suppression de répétitions identiques, filtrage des mentions d’URL non vérifiées, demande de reformulation simplifiée, réutilisation de l’état du guide pour répondre aux photos liées à l’étape en cours.

### Base de données

Les trois tables protégées ont été créées dans Supabase avec RLS activée et permissions serveur : voir [`schema-private-reference.sql`](./schema-private-reference.sql). Le schéma est une référence versionnée ; la migration a déjà été exécutée côté Supabase.

### Vérification

- **134 tests automatisés réussis** : 114 tests historiques, 15 tests avancés et 5 contrôles du corpus des 1 000 messages.
- La simulation de bout en bout reproduit un nouvel utilisateur, l’étape 1, la confirmation « fait », l’étape 2, l’orientation site/canal et les reçus de livraison.
- Le sitemap du site publié sur la branche `main` contient désormais la page officielle `installer.html` (commit `60787aaf`). La propagation HTTP du site public n’est pas certifiée par ces seuls tests.
- La réception et l’analyse réelles des vocaux Ogg et des photos volumineuses restent à valider. Les autres points non terminés sont détaillés dans l’audit.


## Version 23 — traitement des 28 points restants

### Bilan du tableau de bord d’audit

Les 80 points sont repris dans [`AUDIT_80_CHECKLIST.md`](./AUDIT_80_CHECKLIST.md) : **59 couverts dans le code et les tests**, **21 partiels car validation ou dépendance réelle manque**, **0 totalement non implémenté**. Ces chiffres ne constituent pas une garantie de réussite sur des clients réels.

### Nouveau code de production

- JPEG/PNG : compression et redimensionnement progressifs via imports à la demande `npm:jpeg-js@0.4.4` et `npm:upng-js@2.1.0` jusqu'à 128 Ko ; si non disponible, le transfert NVCF historique reste un secours. Le chargement réel des codecs dans l’Edge Runtime et le traitement d’une vraie photo restent à valider.
- Vision : modèles visuels séquentiels ; description structurée avec incertitude, textes visibles et boutons ; demande de renvoi d'image lorsqu'aucun résultat ne peut être vérifié. Les images ne sont pas enregistrées volontairement en base ; les secrets dans les pixels ne sont **pas** automatiquement masqués. Les captures explicitement annoncées comme sensibles sont bloquées avant envoi et l'utilisateur est invité à les recadrer.
- Vocaux : le relais Nemotron Transcribe optionnel reçoit Ogg/Opus (`MX_ASSISTANT_ASR_URL`), avec `verbose_json`, drapeaux de dégradation et indice **heuristique non calibré**. Les répétitions peuvent être nettoyées, les transcriptions incertaines sont confirmées. `/health` teste l’endpoint HTTPS `/v1/health/ready` s'il est configuré.
- Sports : deux sources publiées comparées pour les heures de coup d'envoi ; en cas d'écart supérieur à 5 minutes, la sélection incohérente n'est pas présentée comme validée. Une source absente ne constitue pas une seconde confirmation.
- Cotes : lecture optionnelle du fichier officiel `https://mrxpronos.github.io/MrXPRONOS_App/odds.json`, dont `updated_at` doit dater de moins de 15 minutes, avec événements futurs et opérateurs de la liste autorisée. Les combinaisons ne reprennent jamais deux sélections du même match. **Aucun flux live `odds.json` n'a été installé ni alimenté**. Schéma : [`ODDS_FEED_SCHEMA.json`](./ODDS_FEED_SCHEMA.json). L’IA ne doit pas créer des cotes lorsqu'il manque.
- Bookmakers : variables `MX_ASSISTANT_EXCLUDED_BOOKMAKERS` et `MX_ASSISTANT_APPROVED_ALTERNATIVES`, acceptant des clés du catalogue (`1xbet`, `1win`, `betwinner`, `melbet`, `linebet`, `betclic`) séparées par des virgules. Les listes sont intentionnellement vides tant que le propriétaire ne les a pas décidées. Les exclusions s'appliquent aux liens, boutons et catalogue envoyé à NVIDIA.
- Contexte : résumé persistant dans `mx_telegram_assistant_sessions` et contrôle de pertinence sur les demandes clés. Une seule clarification lorsque c'est nécessaire, relecture et réponses de repli sans deuxième appel NVIDIA inutile.
- Livraison : table RLS `mx_telegram_assistant_delivery_claims` ; chaque fragment est réservé avant `sendMessage` pour éviter les doubles envois lors du rejeu de l'update. Ceci offre une politique **au plus une fois**, pas la garantie « exactement une fois » : après panne entre réservation et envoi, la livraison peut nécessiter une intervention manuelle.
- Jeu responsable : détection supplémentaire des dettes, mises doublées pour se refaire et situations à risque ; aucun lien commercial dans ces réponses.

### Dépendances et configuration encore nécessaires

1. Vérifier en production une image JPEG/PNG volumineuse avec NVIDIA ; la compression doit être effectivement disponible à l’exécution.
2. Mettre en place et renseigner un véritable endpoint Nemotron Transcribe compatible HTTPS dans `MX_ASSISTANT_ASR_URL` ; le texte du bot seul n'héberge aucun GPU.
3. Fournir une source légitime et mise à jour pour les cotes avant de publier `odds.json` ; ne jamais remplir le fichier avec des valeurs fictives.
4. Définir les valeurs commerciales des bookmakers interdits ou alternatifs ; aucune liste n'a été devinée.
5. Une solution de masquage local des pixels contenant des données sensibles nécessite une détection visuelle locale fiable. Le filtre textuel actuel **ne garantit pas** la confidentialité des documents photographiés.

### Preuves de vérification

- **149 tests JavaScript réussis** : 114 anciens + 15 avancés + 15 nouveaux cas restants + 5 contrôles du corpus.
- Fonction Supabase `telegram-assistant-v2` version **23 ACTIVE** ; `telegram_webhook` version **38 ACTIVE**, inchangée.
- Tables privées RLS : sessions, événements de modèles, reçus d'envoi et réservations de fragments. Lecture par `anon`/`authenticated` interdite, accès au rôle `service_role` accordé.
- Aucun test live de la capture/vocal sur le vrai compte n'est déclaré réussi sans preuve correspondante.


## Version 24 — confirmation des vocaux

Lorsqu'une transcription vocale est confirmée par « oui » ou corrigée par « Non, j'ai dit ... », l'assistant restaure la demande complète et recalcule l'intention avant de répondre. Pour une correction de bookmaker, l'intention d'inscription originale est conservée uniquement si elle était exprimée. **150 tests réussis** ; fonction Supabase `telegram-assistant-v2` version 24 ACTIVE. Les dépendances multimodales externes restent celles documentées dans la checklist.



## Version 25 — correction de la transcription des vocaux Ogg/Opus

### Diagnostic fondé sur les conversations du 17 novembre 2026

Plusieurs messages vocaux de test étaient retranscrits de façon très incohérente. L'ancien chemin de secours transmettait directement `audio/ogg` (Ogg/Opus Telegram) au modèle `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`, alors que ce modèle ne documente que WAV/MP3 comme entrées audio. La base historise les transcriptions mais pas les fichiers audio originaux ni la source du moteur : on ne peut donc pas prouver un changement de modèle ancien ni mesurer la précision exacte sur les enregistrements disparus.

### Nouveau chemin voix

1. **Priorité au service ASR dédié** (`MX_ASSISTANT_ASR_URL`) pour Ogg/Opus natif ; formulaire HTTPS, `verbose_json`, langue française par défaut (modifiable avec `MX_ASSISTANT_ASR_LANGUAGE`). Le service doit être réellement déployé et disponible.
2. Si l'ASR dédié est indisponible, le bot reconnaît l'en-tête Ogg/Opus, décode l'audio via `npm:@audio/decode-opus@1.3.3`, le convertit en **WAV PCM mono 16 kHz** et divise les vocaux en tranches de 4,8 secondes (moins de 175 Ko chacune).
3. Nemotron Omni reçoit désormais **uniquement WAV/MP3** ; aucun Ogg brut ne doit lui être envoyé. Deux segments au plus sont traités en parallèle ; maximum six segments pour le secours en ligne. Au-delà, le bot indique qu'il ne peut pas transcrire correctement et demande un vocal plus court.
4. Les transcriptions absurdes ou incomplètes sont rejetées. Les vocaux segmentés demandent confirmation avant de servir d'entrée à l'IA conversationnelle. Le bot ne doit plus traiter silencieusement des mots inventés comme un ordre valide.
5. La clarification vocale expire après cinq minutes ou lors d'une nouvelle demande ; une ancienne transcription n'interfère plus avec le nouveau message.
6. `/health` (administrateur) indique la disponibilité du service ASR dédié et le chargement du décodeur Ogg. Les métriques `source=speech` enregistrent **modèle, résultat et durée seulement**, sans stocker l'audio ni recopier son contenu.

### Contrôles et limites

- **162 tests JavaScript réussis** dans le harnais de simulation, dont 12 tests ciblés sur le traitement des vocaux.
- **Supabase** : `telegram-assistant-v2` version **25 ACTIVE** ; `telegram_webhook` **38 ACTIVE** et inchangé.
- Le chargement réel du module WASM et la précision sur une voix Telegram réelle doivent encore être confirmés. Une simple mise en production et un déploiement réussi ne prouvent pas ces deux points.
- Pour vérifier, envoyer `/health` depuis le compte administrateur puis un court vocal de 5 à 10 secondes. La présence de nouvelles lignes dans `mx_telegram_assistant_model_events` avec `source=speech` permettra d'identifier les moteurs effectivement utilisés.
- Si le décodeur Ogg est indisponible dans Edge Runtime, la réponse doit signaler l'impossibilité de transcrire plutôt que transmettre le format brut à Omni. Un endpoint ASR dédié reste la solution la plus robuste pour les vocaux longs.


## Version 27 — suivi client et fiabilité du guidage (17 novembre 2026)

**Statut vérifié :** Edge Function `telegram-assistant-v2` V27 ACTIVE. `telegram_webhook` V38 ACTIVE, inchangé. La PR #328 reste en brouillon.

### Commandes administrateur (depuis le compte propriétaire uniquement)

- `/quality` : compteurs de messages, tentatives NVIDIA, réponses humaines et chats suspendus sur les données disponibles.
- `/chats` : derniers interlocuteurs et état de pause.
- `/history <chat>` : 8 derniers messages conservés, avec distinction client / bot / responsable et masquage des secrets détectables en texte.
- `/reply <chat> <message>` : répondre manuellement et mettre la conversation en pause ; `/resume <chat>` : réactiver le bot.
- `/health` : état ASR / décodeur Ogg/Opus et modèles NVIDIA.

Les notifications répétées d'un même chat repris par un humain sont espacées d'au moins 30 secondes ; les messages reçus restent conservés dans l'historique du chat pendant la pause.

### Confidentialité pour les interlocuteurs

- `/privacy` : fonctionnement et limites.
- `/delete_my_data` puis `/confirm_delete_my_data` sous 5 minutes : suppression des messages, du résumé et du chat enregistrés par l'assistant pour **son propre identifiant Telegram** ; `/cancel_delete_my_data` annule la demande.
- Cette suppression ne supprime ni l'historique sur les serveurs Telegram ni certaines métadonnées techniques non rattachées au chat. Les secrets présents dans les pixels d'une photo ne sont pas automatiquement masqués avec garantie.

### Qualité et vérification

- Le guidage n'avance plus lors d'un simple « OK / d'accord » : confirmation explicite de l'étape, et limitation à une seule étape dans les réponses structurées.
- Suite GitHub Actions `Telegram Assistant V2 tests` : [run #44131799220](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/44131799220) — **193 tests réussis / 193**.
- Le test des connaissances vérifie aussi les pages du site, les six réseaux officiels et le catalogue partenaire contre les fichiers du dépôt.
- **Encore à valider en conditions réelles** : un guidage complet sur un second compte Telegram, la transcription Ogg/Opus, NVIDIA Vision et les cotes live avec une source fiable. Aucun succès réel n'est présumé.


## Routage NVIDIA V28 — Mistral Large 4 et délai par modèle (17 novembre 2026)

**Règle demandée :** le modèle initial est `mistralai/mistral-large-4-1t-a52b` (Mistral Large 4). Une réponse NVIDIA non vide, contrôlée et effectivement envoyée via Telegram inscrit son modèle dans `mx_telegram_assistant_model_events` avec `source=routing_v28` et `status=ok`. Lors du message suivant, le plus récent événement de ce type devient le modèle prioritaire, y compris sur une autre instance Edge. En l'absence de succès enregistré dans cette nouvelle stratégie, priorité à Mistral Large 4. Les anciens succès V27 ne modifient pas la priorité du premier démarrage V28.

- Chaque modèle interrogé reçoit **jusqu'à 60 000 ms** ; une réponse rapide est transmise dès sa réception, sans attendre artificiellement une minute.
- Une erreur HTTP ou une réponse vide peut provoquer un essai immédiat du modèle suivant. En cas de timeout, le modèle suivant n'est interrogé qu'après expiration de sa minute.
- L'administrateur peut utiliser **`/status`** pour voir le prochain modèle prioritaire et le délai maximal par IA.
- Le traitement complet dispose d'un **budget de 125 000 ms** pour les appels de chat. La fonction ne démarre pas un nouvel essai si elle ne peut pas lui garantir les 60 secondes complètes. En pratique, **deux modèles qui expirent à 60 secondes** épuisent ce budget ; les autres modèles ne sont alors pas testés pour ce message, et une réponse de secours sûre est envoyée.
- L'ordre de secours initial derrière Mistral est Nemotron 3 Ultra, Poolside Laguna XS, Nemotron 3.5 Super VL, puis les autres modèles existants.
- Le webhook **confirme immédiatement à Telegram** après validation de son secret, et exécute `handleUpdate` dans `EdgeRuntime.waitUntil`. C'est essentiel pour éviter que Telegram n'attende 60 secondes sur la connexion HTTP.
- Les tâches d'arrière-plan Supabase restent soumises à la durée de vie des instances : **150 secondes sur le plan Free, 400 secondes sur les plans payants**, selon la documentation Supabase consultée. Le budget de 125 secondes laisse une marge pour la préparation, l'envoi et la sauvegarde, mais n'apporte pas de reprise garantie après arrêt forcé de l'instance.
- Un accusé de réception HTTP ne prouve pas qu'un client a reçu son message. Pour garantir des reprises illimitées de 60 secondes par IA, il faudrait une **file d'attente persistante et un worker distinct**, qui ne sont pas fournis par cette version.

Cette stratégie concerne les **réponses de chat NVIDIA**. La transcription audio et la vision gardent leurs propres limites et leur routage spécialisé. Le bot historique `telegram_webhook` de publication des coupons ne doit pas être modifié.


## Annuaire de liens et test d’accueil (V30, 17 novembre 2026)

**Problème corrigé :** un lien hors de l’annuaire était présenté avec un message peu utile (« lien non vérifié retiré »). Désormais, les liens officiels, les principaux canaux et les URL de bookmakers sont centralisés et rendus sous forme de boutons et liens cliquables. Une adresse externe inconnue n’est **jamais** transformée en lien affilié ; le bot explique comment consulter `/liens`.

### Commandes accessibles aux abonnés

- `/start` : accueille un nouvel abonné avec trois accès immédiats : page pronostics, canal Telegram pronostics, installation du site.
- `/accueil` : affiche à nouveau le même message de bienvenue, sans réinitialiser la conversation.
- `/liens` : annuaire complet avec site, pronostics Pro/VIP, installation, page d’actualités foot, canal pronostics, dossier Telegram Mr XPRONOS F, contact Telegram, WhatsApp, Instagram, Facebook, YouTube, Threads et les six bookmakers partenaires configurés. Les liens exclus par `MX_ASSISTANT_EXCLUDED_BOOKMAKERS` ne sont pas proposés.
- `/dossier` : dossier Telegram **Mr XPRONOS F** : `https://t.me/addlist/ZmW4vfwcrMAwNzJk` (source : lien précédemment transmis par le propriétaire).
- `/actufoot` : canal Telegram Actu Foot lorsque l’URL est renseignée, ou la page officielle `infos.html` tant que l’adresse publique est inconnue.
- `/bookmakers` : liens configurés pour les opérateurs partenaires, avec avertissement concernant l’âge, le pays et les conditions.

**Note sur le rendu Telegram** : par défaut trois liens sont convertis en boutons, et les autres liens vérifiés deviennent des ancres cliquables dans le texte, sans perte d’URL.

### Commandes administrateur

- `/testaccueil` : montre la bienvenue envoyée au premier nouveau client, avec les trois mêmes boutons.
- `/synccommandes` : met à jour le menu des commandes du bot Telegram via `setMyCommands`. Cette opération doit être exécutée **une fois depuis le compte propriétaire** après le déploiement (les fichiers de code ne modifient pas automatiquement les menus déjà publiés par Telegram).

### Compléter le lien Actu Foot

Pour le moment, seule l’existence du système de publication de l’actualité football a été retrouvée : **l’URL publique exacte du canal Telegram Actu Foot n’a pas été confirmée**. Elle n’a donc pas été inventée. Pour l’ajouter, configurer le secret Supabase `MX_ASSISTANT_FOOT_NEWS_CHANNEL_URL` avec une véritable adresse de canal de type `https://t.me/<username>` ou `https://t.me/+<code>`. Le bot valide le format et ne l’affiche que s’il est renseigné. Sinon, il donne `https://mrxpronos.github.io/MrXPRONOS_App/infos.html`.

### Validation automatisée

Les tests de `link-hub-integration.test.mjs` couvrent des appels à `handleUpdate` pour `/start`, `/liens`, `/dossier`, `/actufoot`, `/bookmakers`, `/accueil` et `/testaccueil`. Les destinations sont contrôlées dans les boutons et les ancres HTML.

**Attention au deuxième audit sportif :** 200 questions nouvelles ont fait ressortir **28 réponses signalées** lorsque NVIDIA est simulé de façon délibérément trompeuse. Ces défauts sont documentés dans `AUDIT_200_NOUVELLES_QUESTIONS_20261117.md`. Les tests automatisés réussis prouvent le fonctionnement technique, pas l’absence des 28 anomalies.
