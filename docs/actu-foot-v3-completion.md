# Actu Foot V3 completion: atomic versioned storage

## Implemented

- `actu_foot_v3_atomic.py`: Git trees plus single non-forced branch ref update for one atomic commit containing several ciphertext collections; stale heads are retried by reapplying deterministic mutations. It is not a realtime Telegram lock.
- `actu_foot_v3_archive.py`: monthly encrypted archive partitions; compacting a collection writes encrypted archive shards **and** updated live ciphertext together in one ref update. No deletion happens unless that update succeeds. Crashes before commit preserve live data.
- `actu_foot_v3_migrate.py`: reversible record-level migration from schema 2 to 3 with preview and no invented football data. The encrypted V2 envelope format is unchanged.
- `test_actu_foot_v3_complete.py`: synthetic fault injection, conflicting-ref retry, repeated compaction, period validation and 4,000-match stress run.

## Security and operational constraints

- No data is persisted in plaintext, including indexes.
- Only reviewed workflows holding GitHub `contents:write` may invoke `GitAtomicStore`. PRs use read-only test workflows.
- Only branch `main` is writable. No force-push is permitted through the transaction engine.
- The multi-collection operation is atomic **only for writers cooperating via the single Git ref**. Existing V2 Contents API writers or privileged forced updates can still race with it; put all V3 writers behind the same workflow concurrency lock before production enablement.
- The encrypted archive path is validated, but V2's ciphertext metadata does not authenticate that filename. Validated timestamp partitioning ensures a misfiled record cannot be silently accepted.
- The in-memory index and TTL cache are per job. No shared or persistent cache service.
- The V3 maintenance scheduler is **not enabled** before V2 secrets and collections are initialized. Retention policy must be approved so that publication history and audit data are not lost.
- No archive of `audit` is allowed by automatic compaction, and `publications` must not be automatically deleted before V4 deduplication migration.
- V3 code tests use fake Git stores; successful CI does not prove GitHub remote commit privileges, storage quotas or disaster recovery.
- Actual live bot connection, outbox and cutover belong in V4.

## Durcissement de finalisation

Les archives sont désormais des shards mensuels UTC immuables, liés cryptographiquement au chemin (AAD), et distincts des fichiers live. Une copie indépendante Cloudflare KV par digest est déposée puis relue, avec reçu append-only D1, avant toute suppression de source. La transaction Git inclut archives, live et audit avec les reçus; les copies orphelines après conflit restent conservées mais ne sont pas des archives actives. Le journal de reçus indépendant permet de retrouver les copies, et les entrées audit ancrées V2 documentent les shards actifs. Le contrôle en lecture seule teste toutes les collections et la récupération isolée d'un shard synthétique (namespace temporaire, expiration 24h). Les périodes proposées sont 90j matches terminés, 30j live_events, 60j news, 120j statistics; jamais publications, settings ou audit. L'exécution hebdomadaire contrôle toutes les collections, sans écriture si aucune candidate, et demande l'approbation de l'environnement protégé si une compaction est nécessaire. L'activation du paramètre chiffré est également protégée. Les réels logs et résultats doivent être vérifiés après fusion.

L'inventaire Git des archives est comparé aux reçus du journal d'audit authentifié à chaque contrôle. La commande isolée `python -m scripts.actu_foot_v3_maintenance --recover-archives` restaure jusqu'à 24 shards depuis Cloudflare sans écrire dans main; `--audit-file` accepte le ciphertext audit récupéré par V2, même si le dépôt d'archives est indisponible. Le rapport distingue vérifiés/restants; la récupération des lots suivants utilise `--after` avec `next_after` et un nouveau répertoire vide.

La lecture des enveloppes volumineuses bascule sur Git Blobs lorsque GitHub Contents ne renvoie pas le Base64 (digest Git vérifié). Les limites de transport V2/KV sont alignées sur les enveloppes jusqu'à 3 Mo, sans augmenter la limite de contenu déchiffré de 2 Mo. Le workflow protégé exécute la récupération isolée des archives après maintenance; le mode manuel recover_archives permet les lots suivants via recovery_after.

## Exploitation autonome (24 novembre 2026)

La politique chiffrée de rétention a été approuvée et activée par le run 45323687858 (commit d6a38686d3b7c33443a87f0205e77d5a0722f535). Les tâches automatiques V3 sur main (schedule/push) appliquent exclusivement cette politique exacte, sans approbation répétée ni possibilité de modifier les durées ou d'activer la politique. La copie indépendante, la relecture, l'audit et l'écriture Git non forcée restent obligatoires. Le Worker accepte l'identité OIDC du workflow V3 sur main pour schedule/push sans environnement; les opérations manuelles d'archivage restent liées à l'environnement protégé. Les restaurations V2 en runner isolé sont en lecture seule et ne nécessitent plus d'approbation; chaque sauvegarde réussie déclenche sa propre restauration, y compris le dimanche. Les rotations et restaurations modifiant main restent protégées. Les anciens runs en attente sont des instantanés de l'ancien workflow et ne bloquent plus les nouvelles restaurations.
