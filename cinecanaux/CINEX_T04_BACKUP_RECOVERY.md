# CinéX — T04 : sauvegarde D1 chiffrée et restauration hors production

Cette procédure protège la **base D1 complète** indépendamment de la discussion Telegram du propriétaire : titres, catalogues, liens sources, inventaires et reçus, états des files, configurations et suivi des suppressions. Elle contient aussi des données sensibles (identifiants privés) ; **ne jamais publier un export SQL en clair**.

## Architecture en service

- **Source :** base Cloudflare D1 `cinecanaux-directory` (Worker `cinecanaux-bot`).
- **Fréquence :** chaque jour à **02:37 UTC** via `.github/workflows/cinex-t04-backup.yml`; exécution également possible par `workflow_dispatch`.
- **Export :** `wrangler@4.165.0 d1 export ... --remote`, schéma + données, sans filtre de table ; aucune session Telegram personnelle.
- **Protection :** chiffrement X25519 (clé publique du dépôt) + HKDF-SHA256 + AES-256-GCM avec clé et nonce uniques par sauvegarde. L'export SQL n'est envoyé à aucun fournisseur autre que Cloudflare/GitHub Actions avant chiffrement ; le workflow efface son fichier temporaire.
- **Destination vérifiable :** artefact **uniquement chiffré** de GitHub Actions, conservation **90 jours au maximum** sur ce dépôt public. Accéder aux exécutions `CinéX T04 - sauvegarde D1 chiffree et verifiee`.
- **Contrôle de qualité :** le dump doit se restaurer en SQLite isolé et réussir `PRAGMA integrity_check`, contenir les tables attendues et un manifeste chiffré avec l'empreinte SHA-256 et les nombres de lignes par table. Un échec bloque l'upload.
- **R2 :** non disponible actuellement sur le compte Cloudflare (activation demandée dans le tableau de bord) ; aucun bucket R2 fictif.

**Limite critique : la base D1 ne contient pas les octets des films et des épisodes.** La sauvegarde conserve les références des fichiers et les messages sources, mais pas les vidéos elles-mêmes. La perte des canaux d'origine, du fichier Telegram ou des permissions d'accès ne peut être réparée par cet export seul. Une vraie sauvegarde multimédia hors Telegram exige un stockage privé dédié (R2 ou équivalent) et des droits de diffusion et de conservation vérifiés. Ne pas présenter cette sauvegarde D1 comme une archive complète de vidéos.

## Sauvegarde complémentaire des fichiers déjà présents sur GitHub

Le workflow **`.github/workflows/cinex-t04-github-files-backup.yml`** crée tous les jours à **03:12 UTC** un second artefact GitHub Actions, chiffré séparément, contenant uniquement les fichiers CinéX déjà archivés dans le dépôt GitHub :

- `telegram-film-relay/state/*.json` — états et catalogues existants ;
- `telegram-film-relay/config/*.json` — paramètres de la diffusion ;
- `telegram-film-relay/assets/` — images et affiches uniquement ; les vidéos sont exclues de GitHub ;
- `cinecanaux/assets/` — images, avatars et JSON seulement, sans vidéo.

**Important :** l'inventaire du dépôt GitHub effectué le 21/11/2026 ne trouve actuellement aucun fichier MP4/MKV/WebM/MOV/AVI réellement commité dans ce périmètre. **Une référence vers un message Telegram ou un `file_id` n'est pas une copie vidéo.** La sauvegarde GitHub est donc utile dès maintenant pour les catalogues et visuels, mais elle **ne permet pas encore de restaurer les octets des films ou épisodes**.

Conformément au choix du propriétaire, le script **n'ajoute jamais de fichiers vidéo à l'archive GitHub**, même si un fichier média apparaît ultérieurement dans le dépôt. Le stock privé Telegram conservera les médias, tandis que D1 et ses sauvegardes GitHub chiffrées conserveront les références `source_chat_id/source_message_id` et `stock_chat_id/stock_message_id`, sans octets vidéo.\n\nLe script refuse les fichiers individuels supérieurs à 48 MiB, les volumes supérieurs à 128 MiB et les liens symboliques ; ces limites protègent les artefacts et évitent de confondre GitHub avec une vidéothèque illimitée. **Ne jamais déposer des vidéos privées directement dans l'historique public de ce dépôt :** les objets Git restent récupérables après leur suppression apparente. N'ajouter que des médias que tu as le droit de stocker et de diffuser.

### Restauration locale de cet artefact GitHub

Télécharger l'artefact nommé `cinex-t04-github-files-sealed-...` depuis l'exécution réussie du workflow **CinéX T04 - sauvegarde chiffrée des fichiers GitHub**. Extraire `files.enc`, puis utiliser la **même clé privée hors ligne** que la sauvegarde D1.

```bash
python cinecanaux/scripts/cinex_github_files_backup.py verify-local \
  --archive files.enc \
  --private-key cinex_t04_recovery_private.pem

python cinecanaux/scripts/cinex_github_files_backup.py restore-local \
  --archive files.enc \
  --private-key cinex_t04_recovery_private.pem \
  --out cinex-files-restored
```

La restauration crée un **nouveau dossier local** ; elle n'écrase jamais les fichiers existants du projet. Vérifier les fichiers restaurés avant toute utilisation dans une autre branche. La clé privée ne doit jamais entrer dans les Actions GitHub ou le dépôt.

---

## Stock Telegram privé pour les fichiers lourds (sans vidéo dans GitHub)

Le propriétaire a choisi le **21 novembre 2026** de conserver dans GitHub **seulement les références** et les affiches. Le stock de vidéos proprement dit sera un **canal de diffusion Telegram privé réservé au propriétaire et aux bots CinéX autorisés**. La création unique suit `.github/workflows/cinex-private-stock-provision.yml`, sous le verrou de la session personnelle et la protection FloodWait déjà en place.

- **Création :** une seule fois via Telethon et la session personnelle du propriétaire. Nom `CinéX — Stock privé`, sans nom d'utilisateur public, sans exportation de lien d'invitation. Si un canal du même nom existe, son identité et sa propriété sont vérifiées au lieu de créer un doublon.
- **Droits :** seul le propriétaire est humain ; les bots doivent correspondre à leurs jetons officiels vérifiés. Les droits d'administration accordés sont limités à `post_messages`. Le bot Radar est requis ; le bot de publication dédié n'est ajouté que si son identité est configurée et vérifiée.
- **Fichiers :** le Worker place au maximum **un film par minute** dans le stock, en utilisant `copyMessage` depuis les messages Telegram déjà identifiés, avec autorisations/approbations présentes dans D1. Aucun téléchargement vidéo, réencodage ou upload GitHub.
- **Sources :** pour commencer, films classiques publiés, saga Fast and Furious publiée et films approuvés des vidéothèques. Les séries non autorisées et les contenus en révision ne sont pas transférés.
- **Index :** les tables `cine_private_stock_config` et `cine_private_stock_items` dans D1 conservent la correspondance entre référence originale `source_chat_id/source_message_id` et copie de stock `stock_message_id`. Le canal privé n'est pas identifié publiquement dans le dépôt GitHub. Les sauvegardes D1 **chiffrées** sur GitHub incluent ces références.
- **Récupération :** lorsqu'une copie stock est confirmée, les livraisons du bot peuvent faire `copyMessage` **depuis le stock**, sans dépendre de l'original. Tant que la copie n'est pas confirmée, la livraison conserve sa source existante.
- **Erreurs :** l'état `needs_review` empêche toute nouvelle tentative automatique si la réponse Telegram était ambiguë ; un cas en échec reste visible dans le tableau de bord propriétaire. Les quotas T01 continuent de s'appliquer et les copies envoyées aux abonnés expirent suivant T03.

**Une chaîne Telegram privée n'est PAS une sauvegarde indépendante de Telegram.** Si Telegram supprime les fichiers, suspend la session, ou retire les droits d'accès aux médias, les références dans D1 et GitHub ne permettent pas de reconstruire les octets des films. Ce système préserve les copies des originaux d'autres canaux au sein de Telegram ; pour une sauvegarde totalement indépendante, il faudrait plus tard un stockage externe privé autorisé.

Le canal ne doit pas être ouvert au public et ne doit contenir que des médias que le propriétaire est autorisé à conserver et à partager. Ne jamais publier son identifiant numérique, ses messages sources, les tokens des bots ou un lien d'invitation dans une issue ou un dépôt public.

---
## Clé privée de récupération

Le fichier **`cinex_t04_recovery_private.pem`** est créé séparément et doit être téléchargé depuis la conversation privée où la sauvegarde a été mise en place. Ne jamais copier cette clé dans GitHub, une variable Actions, Cloudflare D1, un message Telegram ni le dépôt du projet.

Conserver **au moins deux copies hors ligne**, sur supports contrôlés. Sans cette clé privée, les sauvegardes chiffrées sont irrécupérables. La clé publique seule ne peut pas les déchiffrer. En cas de fuite de la clé privée, générer une nouvelle paire et renouveler la clé publique pour les futures sauvegardes.

## Retrouver une sauvegarde et restaurer en local

1. Ouvrir GitHub → **Actions** → `CinéX T04 - sauvegarde D1 chiffree et verifiee` → exécution réussie → **Artifacts**, télécharger `cinex-t04-d1-sealed-...`.
2. Extraire le fichier **`backup.enc`** de l'artifact vers un dossier privé sur ton ordinateur.
3. Placer le fichier **`cinex_t04_recovery_private.pem`** dans un dossier privé et ne pas le transmettre à un tiers.
4. Installer Python 3 puis, depuis une copie locale du projet :

```bash
python -m pip install "cryptography==46.0.3"

# Vérification de l'intégrité et du contenu en mémoire, sans aucune écriture sur Cloudflare :
python cinecanaux/scripts/cinex_backup_crypto.py verify-local \
  --archive backup.enc \
  --private-key cinex_t04_recovery_private.pem

# Restauration dans un nouveau fichier SQLite LOCAL seulement :
python cinecanaux/scripts/cinex_backup_crypto.py restore-local \
  --archive backup.enc \
  --private-key cinex_t04_recovery_private.pem \
  --out cinex-restored.sqlite
```

Le programme refuse d'écraser un fichier existant. **Il n'existe aucune commande de restauration directe dans la base D1 de production.** En cas de catastrophe, comparer d'abord les tables et les volumes sur une base de préproduction isolée, vérifier les droits/canaux et faire valider un plan de restauration et la reprise des écritures avant toute mutation de la vraie base.

## Tests et limites de restauration

- Un test automatique crée un dump D1 fictif, le chiffre, le déchiffre et importe les tables dans une nouvelle base SQLite ; il vérifie ensuite les valeurs et l'intégrité.
- Les tests refusent une archive altérée, une mauvaise clé privée, un export incomplet et l'écrasement d'une base existante.
- Le pipeline de production doit publier un **artefact chiffré de taille non nulle** ; l'absence de cet artefact est un échec et non une sauvegarde réussie.
- Sur un dépôt public, GitHub Actions conserve les artefacts au plus **90 jours** ; télécharger une copie chiffrée hors GitHub si une conservation plus longue est exigée.
- Une restauration SQLite locale testée **n'est pas** une preuve de restauration D1 de production, ni de récupération des octets médias.
- En cas d'expiration des artefacts, de suppression du dépôt GitHub ou de perte de la clé privée, cette solution seule ne suffit pas. Prévoir une destination durable et indépendante dès que possible.

## Périmètre des données sensibles

Une base complète peut contenir des identifiants d'abonnés, des liens d'invitation et des références Telegram ; la sauvegarde chiffrée doit être considérée comme sensible au même titre que la base. Ne pas envoyer de SQL en clair dans les issues GitHub, les logs, les Pull Requests, les fichiers `/tmp` réutilisés ou des canaux Telegram. La fréquence de création et la conservation des copies doivent respecter la politique de protection des données.
