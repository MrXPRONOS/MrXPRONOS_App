# Actu Foot V2 — Security Foundation

**Scope:** Encrypted module storage, key segregation/versioning, validation,
tamper-evident audit, backup export, guarded restoration, optimistic concurrency.

**Status:** V2 library and isolated tests. Live Telegram production **unchanged**.

## Collections

Allowlisted: `matches`, `live_events`, `publications`, `news`,
`statistics`, `settings`, `audit`.
Per-collection file path:
`assets/data/private/actufoot_v2/<collection>.aes.json`.

## Key setup

A GitHub Actions secret `ACTU_FOOT_V2_KEY_B64_V1` with exactly 32
cryptographically random bytes encoded as Base64 is recommended.
For migration only, V1 may fall back to `ML_V2_HISTORY_KEY_B64`.
Every collection derives its own HKDF-SHA256 key; AES-256-GCM authenticates
schema version, collection identity, key version, codec and generation.

Do not put plaintext, key material or decrypted backup into Git history,
pull request artifacts or job logs. Rotate by creating
`ACTU_FOOT_V2_KEY_B64_V2`, validating its availability and backed-up V1 key,
then invoking `CollectionVault.rotate(2)` via restricted maintenance workflow.
Never delete previous key versions until all backups are migrated/tested.

## Writing and query boundaries

`CollectionVault.update(callback)` retries SHA conflicts and is for
**deterministic, side-effect-free** callbacks only. It does not provide atomic
transactions across collections, and GitHub Contents API is not an appropriate
primary realtime outbox for Telegram delivery.

No V2 production state is initialized or populated by tests.
Do not run production changes from pull-request events.
Never infer that GitHub file encryption provides secrecy of filenames,
commit timestamps, file sizes or access logs.

## Audit

`append_audit` creates a sequence of hash-linked events, and `verify_audit`
detects corruption inside the loaded chain. Store an independently trusted
audit head off-repo to detect *whole-chain* rollback/replacement.
Audit events must exclude secrets and personal data.

## Backup and recovery

`backup_bundle` creates a versioned encrypted export.
`verify_backup` verifies AEAD and schema before use.
`restore_backup` requires explicit confirmation, an expected current SHA
and approved generation floor; it increments the destination generation.
Keep independent copies off the same repository and periodically test restoration.
There is no automatic backup scheduler or independent destination yet.

## V2 acceptance

- Distinct collection keys, authenticated ciphertext and nonce randomness.
- Wrong keys, tampering, invalid records and unknown collections rejected.
- SHA collision/concurrent writes fail and allow controlled retries.
- Audit chain tampering detected.
- Backup verified, restoration gated, stale SHA rejected.
- V1 remains usable; no Telegram publication side effects.

## V3 backlog

Structured indexes/query engine, multi-record transactional layer, smart
cache, compaction, lifecycle archival and larger-volume stress testing.

## V4 backlog

History import/reconciliation, football provider normalization, live tracking,
durable Telegram reservation/acknowledgment protocol, event replay,
test-channel integration and gradual production switch.
