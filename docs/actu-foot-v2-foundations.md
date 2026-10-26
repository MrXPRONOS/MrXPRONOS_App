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


## October 26 V2 hardening

- `scripts/actu_foot_v2_validation.py` validates bounded nested structures, timezone-aware
  timestamps, identities, score ranges, states, Telegram IDs, source URLs,
  finite numeric statistics, audit hashes, and rejects credential field names.
- Legacy history key fallback is **opt-in**, through
  `ACTU_FOOT_V2_ALLOW_LEGACY_KEY=1`. Prefer a newly generated repository
  secret `ACTU_FOOT_V2_KEY_B64_V1`. It must be created in GitHub Actions
  secrets by an authorized repository administrator. No key value is in code.
- `scripts/actu_foot_v2_operations.py` verifies ciphertext archives and
  refuses empty backups. Backups fetch committed encrypted collections
  from `main` (not a possibly stale Actions checkout) and validate them
  before releasing encrypted-only artifacts.
- Manual maintenance workflow `actu-foot-v2-maintenance.yml` uses the
  GitHub environment `actu-foot-v2-maintenance`. Repository administrators
  must configure required reviewers/branch rules for actual human approval.
  Rotation requires the operator's confirmation token and target key already
  installed. Missing protection rules cannot be enforced by workflow YAML alone.
- Remote restore is intentionally blocked in workflow until a verified backup
  has been securely retrieved from a known source. The local verified restore
  function and its conflict tests are implemented. This is a real remaining gap,
  not a completed disaster recovery exercise.
- The weekly backup workflow fails on **zero collections** instead of
  misleadingly passing with an empty artifact. Initialize data collections
  only after key/environment setup; the live Telegram bot still uses its
  prior backend.
- Audit read is now checked as a chain, but an independent off-repo trust
  anchor is still required to detect complete history rollback.
- A GitHub Actions artifact stays under the same provider, and is therefore
  **not** an independent disaster-recovery destination. Configure another
  provider, verify restore and document retention before calling V2 fully
  production-ready.

### Operator prerequisites

1. Add `ACTU_FOOT_V2_KEY_B64_V1` to GitHub repository secrets (32 random bytes,
   Base64). Prefer a dedicated new random value instead of the history secret.
2. Restrict the maintenance GitHub environment to authorized reviewers and
   `main`; check organization-level Actions permissions.
3. Initialize V2 encrypted collections through reviewed, credentialed Actions.
4. Verify an actual nonempty snapshot, retrieve the encrypted artifact, and
   rehearse restoration to a disposable destination before production migration.
5. Configure a provider-independent backup and audit-head anchor.

This hardening does not migrate Supabase/Neon, change Telegram channels, or
claim that GitHub is a high-frequency transactional engine.
