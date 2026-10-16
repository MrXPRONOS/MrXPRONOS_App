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

## Mise en production dans le dépôt existant

Le dépôt GitHub actuel est **public** : ne placez aucune session, hash API, invitation privée non destinée au public ou donnée personnelle dans les fichiers suivis par Git.

**Secrets GitHub** : `Settings > Secrets and variables > Actions > New repository secret`

| Secret | Requis | Valeur |
|---|---|---|
| `TG_API_ID` | oui | Numéro `api_id` de my.telegram.org |
| `TG_API_HASH` | oui | Chaîne `api_hash` de my.telegram.org |
| `TG_SESSION_STRING` | oui | Session Telethon `StringSession` générée localement, jamais dans le chat ou Git |
| `TG_APPROVED_SOURCES_JSON` | facultatif | Liste JSON des sources **dont la redistribution est autorisée**, avec justification |

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
| `TG_PRIVATE_INVITE_LINK` | lien d'invitation du privé, par ex. `https://t.me/+...`, facultatif |
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
