# ML V2 — GitHub-only encrypted football history

Supabase and Neon are NOT used for this history. Repository is public: ALL persisted match records are AES-256-GCM encrypted before commit; gzip is only compression and is not treated as encryption.

## Security setup (one-time, REQUIRED)
1. Generate a cryptographically random 32-byte key on your own secure computer: `python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"`.
2. In GitHub > Settings > Secrets and variables > Actions > New repository secret, set `ML_V2_HISTORY_KEY_B64` to that string. **Never paste it into a chat, repository, issue, PR, workflow input, log, or web page.**
3. Maintain the existing `SPORTDATA_API_KEY` or `SPORTDATA_API_KEY_1` ... `SPORTDATA_API_KEY_5` GitHub secrets for the source provider.
4. Keep the key in a safe private backup: loss makes the stored snapshots permanently unreadable. Rotating the key requires a separate migration/decrypt-reencrypt operation.

## Operation
- Research script: `research/single_ml_v2_git.py`.
- GitHub Actions workflow: `.github/workflows/research-certified-football-backfill.yml`.
- Workflow is manual (`workflow_dispatch`), incremental and quota-controlled. It appends encrypted files `research/encrypted_football/days/YYYY/MM/YYYY-MM-DD.enc`, then updates encrypted `manifest.enc`.
- Repeat the workflow until the encrypted manifest reports a complete date range. Each previous day is reused. A missing, ambiguous, or empty provider day stays missing, never filled by pretending.
- The code commits **only encrypted .enc files**, never plaintext or API keys.
- The ML backtest is permitted only after all requested days are certified. Decrypted temporary `/tmp/mrx_football_history.json` is never added to git or uploaded as artifact.
- The research branch workflow must be registered/available through GitHub Actions (GitHub may require the workflow file to exist on the default branch before manual dispatch). PR #227 is currently draft; no automatic production integration.

## Limitations
- GitHub storage is subject to repository-size, push, rate-limit, and file-size constraints. Day-by-day files bound the size, but thousands of files and long-term history cause repo growth.
- Encryption hides contents but public filenames reveal that a day's encrypted data exists. Git commit history reveals when data was changed. AES-GCM guarantees confidentiality/integrity only while the secret key remains secret.
- This is **code integration**, not a completed 2024–2026 backfill: source API credentials, quota, successful runs, and tests still needed.
- Legacy mixed-sport `cache/all_matches.json` is not used.
