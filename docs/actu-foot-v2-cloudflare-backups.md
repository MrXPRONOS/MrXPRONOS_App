# Independent Cloudflare KV encrypted V2 backup

Cloudflare KV namespace has been created separately from the public GitHub
repository: `mrxpronos-actufoot-v2-encrypted-backups`.

The first baseline snapshot was uploaded and independently read back using the
connected Cloudflare account on 2026-10-26, under
`snapshots/bootstrap-20261026/` (seven ciphertexts and one manifest).
This is an **empty baseline**, not a backup of old Supabase/Neon history.

## Automatic backups

`scripts/actu_foot_v2_cloudflare_backup.py` verifies each local AES-GCM
envelope and manifest, writes a uniquely versioned Cloudflare Workers KV
snapshot, checks the API response, and reads back its manifest. It uploads no
plaintext, keys, or Telegram secrets.

For GitHub Actions to do this on a schedule, a repository administrator must
add these scoped secrets:

- `CLOUDFLARE_API_TOKEN`: KV write/read token, minimum practical scope
- `CLOUDFLARE_ACCOUNT_ID`: account ID
- `CLOUDFLARE_V2_KV_NAMESPACE_ID`: namespace ID

The existing backup workflow now **fails visibly** if these credentials are
missing. This failure is preferable to a false success on a same-provider
GitHub artifact. The GitHub artifact upload still happens first.

The Cloudflare connector available in this conversation cannot set GitHub
Actions repository secrets or review environment protection policies.
Do not paste secret values in issues, commits, logs or chat.

## Recovery and audit

Encrypted KV snapshots are independent of GitHub. Recovery requires verified
credentials and verification of AES-GCM tags and the manifest before restoring
with the existing V2 guarded restore API. There is not yet a Cloudflare KV
automatic restore job.

The initial audit ciphertext, source commit and snapshot manifest can be used
as an external baseline, but continuous independent anti-rollback anchoring of
each new audit head requires authenticated per-run uploads with rollback
protection; never claim it is complete before this is deployed and tested.

## No production cutover

The seven V2 collections currently contain initialization state only.
Telegram and historical data remain on their existing paths. V4 must reconcile
old publication IDs before any production switchover.
