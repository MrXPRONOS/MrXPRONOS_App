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
