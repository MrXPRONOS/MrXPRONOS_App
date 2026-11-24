# Actu Foot V3 completion: atomic versioned storage

## Implemented

- `actu_foot_v3_atomic.py`: Git trees plus single non-forced branch ref update for one atomic commit containing several ciphertext collections; stale heads are retried by reapplying deterministic mutations. It is not a realtime Telegram lock.
- `actu_foot_v3_archive.py`: monthly encrypted archive partitions; compacting a collection writes encrypted archive shards **and** updated live ciphertext together in one ref update. No deletion happens unless that update succeeds. Crashes before commit preserve live data.
- `actu_foot_v3_migrate.py`: reversible record-level migration from schema 2 to 3 with preview and no invented football data. The encrypted V2 envelope format is unchanged.
- `test_actu_foot_v3_complete.py`: synthetic fault injection, conflicting-ref retry, repeated compaction, period validation and 4,000-match stress run.

## Security and operational constraints

- No data is persisted in plaintext, including indexes.
- Only trusted `main` workflows with `contents:write` can mutate Git; pull request tests are read-only. Routine V3 maintenance requires no repeated human approval.
- Only branch `main` is writable. No force-push is permitted through the transaction engine.
- The multi-collection operation is atomic **only for writers cooperating via the single Git ref**. Existing V2 Contents API writers or privileged forced updates can still race with it; put all V3 writers behind the same workflow concurrency lock before production enablement.
- The archive path and UTC month are authenticated by V3's AES-GCM archive context and verified against the audit receipt.
- The in-memory index and TTL cache are per job. No shared or persistent cache service.
- The V3 scheduler is enabled every Monday at 02:21 UTC, applying the previously approved encrypted retention policy (90d matches, 30d live, 60d news, 120d statistics); never purge publications or audit.
- No archive of `audit` is allowed by automatic compaction, and `publications` must not be automatically deleted before V4 deduplication migration.
- Validation includes offline Git conflict tests, a real GitHub settings transaction, Cloudflare KV authenticated readback, isolated recovery and an end-to-end synthetic compaction. A real archive cannot be observed until eligible production football records exist.
- Actual live bot connection, outbox and cutover belong in V4.

## Durcissement de finalisation

Les archives sont désormais des shards mensuels UTC immuables, liés cryptographiquement au chemin (AAD), et distincts des fichiers live. Une copie indépendante Cloudflare KV par digest est déposée puis relue, avec reçu append-only D1, avant toute suppression de source. La transaction Git inclut archives, live et audit avec les reçus; les copies orphelines après conflit restent conservées mais ne sont pas des archives actives. Le journal de reçus indépendant permet de retrouver les copies, et les entrées audit ancrées V2 documentent les shards actifs. Le contrôle en lecture seule teste toutes les collections et la récupération isolée d'un shard synthétique (namespace temporaire, expiration 24h). Les périodes proposées sont 90j matches terminés, 30j live_events, 60j news, 120j statistics; jamais publications, settings ou audit. L'exécution hebdomadaire vérifie les quatre collections archivables et applique automatiquement la politique chiffrée préalablement approuvée. Les opérations manuelles modifiant cette politique exigent une confirmation explicite, sans approbation administrative récurrente.

L'inventaire Git des archives est comparé aux reçus du journal d'audit authentifié à chaque contrôle. La commande isolée `python -m scripts.actu_foot_v3_maintenance --recover-archives` restaure jusqu'à 24 shards depuis Cloudflare sans écrire dans main; `--audit-file` accepte le ciphertext audit récupéré par V2, même si le dépôt d'archives est indisponible. Le rapport distingue vérifiés/restants; la récupération des lots suivants utilise `--after` avec `next_after` et un nouveau répertoire vide.

La lecture des enveloppes volumineuses bascule sur Git Blobs lorsque GitHub Contents ne renvoie pas le Base64 (digest Git vérifié). Les limites de transport V2/KV sont alignées sur les enveloppes jusqu'à 3 Mo, sans augmenter la limite de contenu déchiffré de 2 Mo. Le workflow automatique exécute la récupération isolée des archives après maintenance; le mode manuel recover_archives permet les lots suivants via recovery_after.

## Exploitation autonome (24 novembre 2026)

La politique chiffrée de rétention a été approuvée et activée par le run 45323687858 (commit d6a38686d3b7c33443a87f0205e77d5a0722f535). Les tâches automatiques V3 sur main (schedule/push) appliquent exclusivement cette politique exacte, sans approbation répétée ni possibilité de modifier les durées ou d'activer la politique. La copie indépendante, la relecture, l'audit et l'écriture Git non forcée restent obligatoires. Le Worker accepte uniquement l'identité OIDC du workflow V3 sur `main` pour schedule/push/dispatch. Les restaurations V2 en runner isolé sont en lecture seule et ne nécessitent plus d'approbation; chaque sauvegarde réussie déclenche sa propre restauration, y compris le dimanche. La rotation reste manuelle avec confirmation, sauvegarde ancrée et SHA approuvé, sans approbation d'environnement; seule une restauration écrasant des données actives reste soumise à l'approbation administrative. Les anciens runs en attente sont des instantanés de l'ancien workflow et ne bloquent plus les nouvelles restaurations.

### Suppression des approbations récurrentes — décision du propriétaire

Les jobs V3 de maintenance et de récupération, y compris manuels, n'utilisent plus l'environnement à validation humaine. L'activation ou la compaction manuelle exige toujours le dispatch explicite et la confirmation APPROVE_V3_ENCRYPTED_COMPACTION; un push ne peut plus activer une politique absente. L'identité OIDC reste liée au dépôt, au workflow et à main. L'environnement protégé est réservé à la restauration V2 écrasant une collection active.

## E2E réel Cloudflare avec données fictives (24 novembre 2026)

Le nouveau script `scripts/actu_foot_v3_e2e_rehearsal.py` reproduit le circuit complet sur une copie **en mémoire** uniquement : archivage sélectif d'un match terminé, maintien d'un match actif et d'un match non terminé, refus sûr d'une copie dont le hash est faux, copie chiffrée dans KV (namespace rehearsal à expiration), relecture via OIDC, ref locale atomique, empreinte et reçu d'audit, requêtes live et archive, récupération chiffrée isolée. Une clé AES aléatoire jetable est utilisée et aucune modification des données réelles de GitHub ou des reçus D1 n'est autorisée. Le script est exécuté sur les occurrences programmées et les pushes ; son succès réel a été observé dans le run 45408241722.

## Décision de clôture V3 — 24/11/2026

**V3 opérationnelle dans son périmètre de moteur de données, archivage et maintenance.** PRs #665, #667, #669 fusionnées. La maintenance autonome GitHub Actions **45408241722** a exécuté le vrai Cloudflare E2E : une donnée fictive archivée, deux conservées, copie indépendante vérifiée, audit et restauration isolée vérifiés, zéro mutation des collections métier réelles. L'exécution automatique a réussi.

La sauvegarde chiffrée et ancrée de sept collections **45408510666** est réussie ; la restauration indépendante et sans approbation **45408645985** est réussie (7/7). Cloudflare D1 a enregistré l'ancre id 8, séquence 3, commit 00577a3dbfc64654c9146073158670cf2d836806. 25 tests Python + 8 tests JavaScript de V3 et la CI générale ont réussi.

**Limite explicitement non testable :** six collections métier V3 restent vides, donc aucun shard de match historique réel n'a encore été archivé. C'est attendu : la migration des historiques, l'alimentation V3 et la bascule Telegram restent prévues en V4. Aucun contenu fictif n'a été publié sur Telegram ou écrit dans les collections chiffrées de production.

## Audit d'exhaustivité — cache et requêtes

Le lecteur `SnapshotReader` ne doit pas rester indéfiniment fixé au commit d'origine dans les processus longs : il vérifie désormais automatiquement l'état de la branche au plus tard toutes les 30 secondes par défaut (ou à intervalle configurable inférieur au TTL), invalide le cache et les index si le commit change, et invalide les anciens curseurs. L'audit a aussi détecté le silence sur certains filtres vides de type invalide et des exceptions de décodage de curseur non traduites : la requête refuse maintenant explicitement ces valeurs. Des tests isolés vérifient ces garanties sans mutation des données réelles.

## Audit d'exhaustivité — rattrapage de la rétention

La première implémentation arrêtait chaque collection après une seule tranche de 1 000 enregistrements. La maintenance exécute désormais jusqu'à six tranches bornées par collection (limite de taille V2 : 5 000), conserve les limites de rétention existantes, vérifie le reliquat et remonte explicitement `V3_RETENTION_BACKLOG_REMAINING` en cas de backlog au lieu de signaler un faux succès. Le pré-contrôle compte jusqu'à 5 000 candidats pour rendre la taille réelle du retard visible. Les tests couvrent plus de 2 000 enregistrements sur plusieurs lots et l'arrêt avec reliquat.
