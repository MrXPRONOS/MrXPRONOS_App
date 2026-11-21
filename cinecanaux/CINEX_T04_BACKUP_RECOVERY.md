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
