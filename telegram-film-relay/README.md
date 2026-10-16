# Mr XPRONOS — Telegram Film Relay (V3)

Projet isolé dans **`telegram-film-relay/`** du dépôt existant **`MrXPRONOS/MrXPRONOS_App`**. Les deux workflows GitHub Actions sont à la racine du dépôt dans **`.github/workflows/telegram-film-*.yml`**, comme exigé par GitHub Actions.

## Capacités

- **Surveillance toutes les 2 heures** (à 00h17, 02h17, etc. UTC/Togo) et **découverte quotidienne** (03h23 UTC/Togo). Les horaires GitHub Actions sont indicatifs et peuvent être retardés.
- Recherche de **canaux publics Telegram**, sans les rejoindre, via les recherches MTProto et les liens fournis dans `config/discovery.json`. Répertorie automatiquement les canaux compatibles dans `state/discovered_channels.json`, puis les inscrit dans `state/auto_sources.json` : **pas besoin de recopier leurs liens**.
- Vérification structurelle **stricte** : canal public broadcast, contenu non protégé (`noforwards=false`), messages lisibles sans rejoindre, au moins **2 couples distincts** affiche + vidéo, description significative, vidéo de **40 minutes minimum** et **150 Mo minimum**, couple séparé de 2 messages au maximum et d'une heure au maximum. Une correspondance structurelle **ne prouve pas** qu'il s'agit bien du film nommé dans l'affiche.
- Les canaux protégés, non lisibles ou incompatibles sont refusés. **Aucun contournement** des restrictions de Telegram ; `FloodWait` provoque un arrêt.
- Les sources découvertes sont **enregistrées automatiquement, mais inactives pour la republication** jusqu'à confirmation des droits. Avec la liste de licences `TG_APPROVED_SOURCES_JSON` (optionnelle, secret GitHub), une nouvelle source découverte qui est déjà couverte par une autorisation explicite peut être activée automatiquement.
- Pour les médias autorisés, envoi de la **photo + description nettoyée** dans le canal privé, suivi de la **vidéo + titre** ; dans le canal public, photo + description + lien direct vers la vidéo privée. Aucun en-tête « Transféré depuis » : `client.send_file(...)` réalise un **nouvel envoi**, pas `forward_messages`.
- Contrôle des doublons, limitation à 5 films par passage, checkpoint persistant après une publication partielle.

> **Droits d'auteur :** le fait qu'un canal soit public, transférable ou repéré par le moteur de recherche ne donne aucune licence. Un canal privé ne protège pas contre une plainte ni une sanction. Utiliser uniquement des films du domaine public, sous licence adéquate ou avec autorisation explicite. Ne jamais utiliser cette automatisation pour contourner les restrictions de copie/transfert.

## Test réel et reprise des archives (16 octobre 2026)

- Source explicitement déclarée comme autorisée par le responsable du projet : **@pleziyisliye1**.
- Le relais surveille les nouveaux messages **et** parcourt progressivement les archives avec le curseur persistant `state/state.json → history`. Un recouvrement des pages protège les couples affiche/film qui se trouvent à la frontière des pages.
- Premier lancement (événement GitHub `push`) et lancement manuel (`workflow_dispatch`) : **1 film maximum**. Exécutions programmées toutes les deux heures : **5 films maximum**.
- Les deux variables `FILM_PUBLISH_ENABLED` et `TG_RIGHTS_ATTESTED` prennent la valeur `true` par défaut **dans le workflow du relais**, uniquement en l'absence de valeur définie sur GitHub. Une variable explicitement positionnée à `false` désactive toujours l'envoi. Les sources non autorisées restent bloquées.
- Le lien d'invitation du canal privé est récupéré automatiquement lorsque le compte Telegram possède les droits administrateur requis ; sinon renseigner `TG_PRIVATE_INVITE_LINK`.
- **Attention :** seuls les journaux d'une vraie exécution GitHub Actions peuvent prouver que les médias ont été publiés. Les tests unitaires vérifient la logique, pas les autorisations Telegram ni la disponibilité du canal.

[Ouvrir le workflow Film Relay](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/workflows/telegram-film-relay.yml)

## Prise en charge des MKV et archives

- Les fichiers `.mkv` sont reconnus même lorsqu'ils sont envoyés en tant que **documents Telegram**, sans durée dans les métadonnées. Le nom de fichier est recherché dans `Message.file.name` puis dans `DocumentAttributeFilename`.
- Le filtre rejette les clips dont la durée est connue et trop courte. Si la durée est absente, le système vérifie une extension/MIME vidéo valide, une affiche associée et la taille du fichier ; il ne déduit pas une durée imaginaire.
- Pour `@pleziyisliye1`, le seuil de taille est de **75 Mo**, jusqu'à **5 messages** et **180 minutes** entre une affiche et sa vidéo. Les canaux découverts non autorisés restent inactifs.
- Dans **Film Relay → Run workflow**, garder **`rescan_history=true`** pour réexaminer les anciens messages après cette correction. Les identifiants déjà publiés restent dédupliqués.
- Un lancement manuel ou de vérification affichera désormais **une erreur** si aucun film n'a réellement été envoyé. Les passages programmés peuvent terminer normalement lorsqu'aucun film nouveau n'est disponible.

## Sources autorisées de type MKV

Le canal `@pleziyisliye1` utilise désormais le mode `authorized_mkv` :

- Associe **photo avec description → MKV**, ou **photo → message descriptif → MKV**, dans cet ordre.
- Le descriptif doit contenir un indice de film : Titre original, Genre, Durée, Synopsis, Film, Réalisateur, Acteurs, Année ou Sortie.
- Ce mode n'applique **aucune limite minimale de durée ou de taille** au MKV ; les autres sources conservent leurs règles normales.
- `archive_cycle: true` reprend la recherche d'anciens films à chaque exécution, même après une traversée complète.
- L'anti-doublon est conservé, les contenus protégés contre les transferts sont ignorés.

Pour tout autre canal disposant d'une autorisation de republication, ajouter dans `config/channels.json` :

```json
{
  "channel": "@autre_canal_avec_autorisation",
  "redistribution_authorized": true,
  "rights_basis": "Autorisation explicite du titulaire",
  "matching_mode": "authorized_mkv",
  "archive_cycle": true
}
```

Ne pas activer `redistribution_authorized` pour des canaux dont les droits n'ont pas été établis.

## Boutons Telegram et mise en forme CinéX

**Les vrais boutons Telegram exigent un bot : la session personnelle ne peut pas en publier.** Le projet CinéX réutilise maintenant un bot football déjà configuré dans les secrets GitHub.

1. Le dépôt possède déjà `FOOTBALL_NEWS_BOT_TOKEN` pour les actualités football (`.github/workflows/football-production.yml`) et `TELEGRAM_BOT_TOKEN` pour les pronostics/coupons (`.github/workflows/telegram-simple-coupons.yml`). **Aucun nouveau jeton n'est nécessaire**.
2. Le workflow CinéX utilise `secrets.FOOTBALL_NEWS_BOT_TOKEN || secrets.TELEGRAM_BOT_TOKEN` : bot des actualités en priorité, bot des pronostics si le premier secret est absent. Les valeurs sont masquées par GitHub et les deux secrets peuvent désigner des comptes différents.
3. Ajouter **le bot effectivement sélectionné** comme **administrateur du canal public CinéX** avec l'autorisation **Publier des messages**. Il n'a pas besoin d'être administrateur du canal privé. Le bot est identifié dans les logs sans afficher son jeton.
4. Relancer **Mr XPRONOS - Film Relay**. La session utilisateur continue d'envoyer affiche + MKV dans le privé ; le bot football publie l'affiche publique avec de vrais boutons Telegram.

Présentation publique : titre en **gras**, métadonnées (genre, durée, synopsis) stylées, sans URL visible dans la légende. Bouton principal : **🎬 REGARDER LE FILM** (message vidéo du privé). Si le lien d'invitation est disponible, second bouton : **🔐 REJOINDRE LA VIDÉOTHÈQUE**. Les destinataires doivent être membres du canal privé pour ouvrir le lien direct de la vidéo.

Le programme s'arrête avec une erreur claire lorsque le bot n'est pas configuré ; il **n'envoie pas la vidéo privée avant de vérifier** le jeton et l'accès du bot au canal public. Une défaillance ultérieure de publication publique conserve un checkpoint pour réessayer sans renvoyer le même MKV.

**Attention : un ancien lien d'invitation privé figurait en clair dans les journaux GitHub Actions. Révoquez l'ancien lien dans Telegram, générez-en un nouveau puis utilisez `CINEX_PRIVATE_INVITE_LINK` (secret, pas variable), ou laissez le programme obtenir un lien.**\n\n**Les anciens messages déjà envoyés par la session utilisateur ne peuvent pas être modifiés par ce nouveau bot.** Les boutons s'appliquent aux publications futures.

## Second canal public : transfert avec attribution

Le second canal est **@Torrent9SeriesFilm** (lien fourni par le propriétaire du projet).
Le workflow utilise la variable GitHub **`TG_MIRROR_CHANNEL`** ; valeur recommandée **`@Torrent9SeriesFilm`**. Cette valeur est déjà renseignée dans `config/channels.json` et comme valeur de repli du workflow. **Aucun secret ou jeton supplémentaire n'est nécessaire.**

Une fois l'affiche publiée dans le premier canal public par le bot, le compte Telethon autorisé utilise **`client.forward_messages(secondaire, id_public, from_peer=premier_public)`**. Il s'agit d'un vrai transfert Telegram : le second canal doit afficher l'attribution **« Transféré de [nom du premier canal public] »** et non une nouvelle publication indépendante. Il faut que le canal public principal autorise les transferts Telegram. Les boutons du post d'origine peuvent être gérés par Telegram lors du transfert ; leur conservation exacte dépend de Telegram.

Chaque transfert réussi est enregistré dans `state/state.json` sous `mirrors`, par ID numérique du second canal. En cas d'échec, le film déjà publié dans le privé et le public principal reste sauvegardé ; les exécutions suivantes essaient de transférer le post public existant **sans renvoyer le MKV**. Les publications publiques antérieures non encore transférées sont également traitées, par lots de dix.

**Vérification du 16 octobre 2026 :** Telegram a renvoyé `UsernameNotOccupiedError` pour `@Torrent9SeriesFilm` depuis la session connectée. Tant que cet identifiant n'est pas reconnu, le transfert secondaire est indisponible ; la publication dans les deux canaux principaux continue. Vérifier dans Telegram **Informations du canal → Nom d'utilisateur** et copier le lien exact, ou mettre un identifiant numérique `-100...` accessible à ce compte dans la variable `TG_MIRROR_CHANNEL`.

## Mise en production dans le dépôt existant

Le dépôt GitHub actuel est **public** : ne placez aucune session, hash API, invitation privée non destinée au public ou donnée personnelle dans les fichiers suivis par Git.

**Secrets GitHub** : `Settings > Secrets and variables > Actions > New repository secret`

| Secret | Requis | Valeur |
|---|---|---|
| `TG_API_ID` | oui | Numéro `api_id` de my.telegram.org |
| `TG_API_HASH` | oui | Chaîne `api_hash` de my.telegram.org |
| `TG_SESSION_STRING` | oui | Session Telethon `StringSession` générée localement, jamais dans le chat ou Git |
| `FOOTBALL_NEWS_BOT_TOKEN` | réutilisé en priorité | Bot Telegram existant pour les actualités football. Ajouter ce bot au canal public CinéX avec droit de publier. |\n| `TELEGRAM_BOT_TOKEN` | secours | Bot Telegram existant pour les pronostics ; utilisé seulement si le secret actualités est absent. |
| `TG_APPROVED_SOURCES_JSON` | facultatif | Liste JSON des sources **dont la redistribution est autorisée**, avec justification |
| `CINEX_PRIVATE_INVITE_LINK` | facultatif | Lien d'invitation du canal privé, réservé au secret GitHub et jamais aux variables visibles dans les logs. Si absent, le programme essaie de le récupérer avec la session administrateur. |

Exemple de **format** pour le secret facultatif (pas de vraie source) :

```json
[{"channel":"@chaine_avec_licence","rights_basis":"autorisation écrite du titulaire"}]
```

Cette liste **n'effectue pas la découverte**, elle active seulement une source déjà trouvée, dès lors que son autorisation est documentée et que les variables de publication sont activées. Les sources ajoutées manuellement dans `config/channels.json` nécessitent `redistribution_authorized: true` après vérification des droits.

**Variables GitHub** : `Settings > Secrets and variables > Actions > Variables > New repository variable`

| Variable | Valeur à utiliser |
|---|---|
| `TG_PRIVATE_CHANNEL` | identifiant du canal privé, par ex. `-1001234567890` |
| `TG_PUBLIC_CHANNEL` | identifiant du canal public, par ex. `@mon_canal` |
| `TG_PRIVATE_INVITE_LINK` | **ne plus utiliser comme variable** ; facultatif : préférer le secret `CINEX_PRIVATE_INVITE_LINK` ci-dessus |
| `FILM_PUBLISH_ENABLED` | **`false` au démarrage** ; `true` seulement après validation |
| `TG_RIGHTS_ATTESTED` | **`false` au démarrage** ; `true` après confirmation des droits |

Les workflows acceptent **`TG_SESSION_STRING` (nom effectivement utilisé)**, ainsi que `TG_STRING_SESSION` et `TG_STREAM_SESSION` comme alias. Le secret est transmis à la variable interne `TG_STRING_SESSION`. Si une variable `FILM_PUBLISH_ENABLED` ou `TG_RIGHTS_ATTESTED` est explicitement fixée à `false`, elle bloque les publications. Le workflow GitHub du relais utilise actuellement `true` comme valeur par défaut si ces variables sont absentes ; il ne publie néanmoins que les sources explicitement marquées comme autorisées. La simulation analyse les sources sans publier. Les tests unitaires s'exécutent avant chaque workflow.

Créer la session Telethon sur votre propre ordinateur :

```bash
pip install -r telegram-film-relay/requirements.txt
cd telegram-film-relay
python scripts/create_session.py
```

Le script demande le code de connexion Telegram. **Ne publiez jamais la session**. Un bot Telegram ne suffit pas pour la recherche générale des canaux.

### Déroulement

1. Les workflows sont **installés sur GitHub**, mais **ne contactent pas Telegram si les trois secrets obligatoires sont absents**.
2. Une fois les secrets configurés, lancez manuellement **Mr XPRONOS - Film Channel Discovery** dans l'onglet Actions, ou attendez le déclenchement quotidien. Les liens détectés sont automatiquement inscrits dans le rapport et `state/auto_sources.json`.
3. Renseignez les variables des deux canaux et testez **Mr XPRONOS - Film Relay** avec `FILM_PUBLISH_ENABLED=false` : analyse uniquement, aucun message envoyé.
4. Seuls les films pour lesquels vous avez les droits peuvent ensuite être publiés. L'activation exige **les deux variables à `true`**, et une source explicitement autorisée.

Le lien `t.me/c/...` pointe vers la vidéo dans le canal privé. Seuls les utilisateurs ayant accès à ce canal peuvent ouvrir le message. Le lien d'invitation permet de rejoindre le canal (selon ses paramètres d'accès).

## Configuration et maintenance

- `config/channels.json` : sources manuellement choisies (autorisées ou en attente), mode `poster_and_video` ou `title_only`, limites d'envoi. Les identifiants de destination sont plutôt fournis par les **variables GitHub** ci-dessus.
- `config/discovery.json` : recherches et critères stricts, ainsi que `seed_channels` facultatif.
- `state/discovered_channels.json` : résultats publics et statistiques.
- `state/auto_sources.json` : liens auto-inscrits, en attente de droits sauf si préautorisés via secret.
- `state/state.json` : anti-doublons et reprise après échec d'envoi.
- `python -m unittest discover -s tests -v` dans `telegram-film-relay/` : tests hors ligne. Ils ne garantissent pas le succès d'une session Telegram réelle.

Le projet ne déploie aucun serveur. GitHub Actions le lance aux horaires spécifiés. La première exécution réelle dépend des secrets et des canaux ; aucune exécution réelle n'a été faite lors de la création du code.
