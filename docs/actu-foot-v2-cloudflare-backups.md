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

## État observé et durcissement du 24 novembre 2026

- La sauvegarde hebdomadaire du 22/11, run 45017542699, a confirmé 7 collections via GitHub OIDC (sans jeton Cloudflare permanent). Le run 40326596839 du 26/10 a récupéré 7 collections du snapshot 40326358146. Ces preuves concernent la base initialisée, pas l'historique importé.
- Le snapshot est désormais lié au SHA immuable de l'exécution : sept fichiers du même commit, refus de snapshot partiel, comparaison de provenance en récupération et ancre obligatoire sur les nouveaux snapshots. Les anciens manifests restent lisibles. Le backup en push/dispatch demande une restauration isolée du snapshot exact, via le workflow et l'environnement existants.
- Le rapport expose exclusivement les versions et nombres d'enregistrements ainsi que la présence des clés dédiées, jamais les clés. Ne pas remplacer la clé V1 avant d'avoir établi le mode de chiffrement et validé une rotation contrôlée.
- L'ancre par snapshot n'est pas une protection continue contre le rollback complet. La protection de l'environnement et l'ancrage monotone indépendant restent à vérifier; ne pas déclarer la V2 totalement terminée.

## Ancrage monotone indépendant (protocole 2)

La base D1 dédiée mrxpronos-actufoot-v2-audit-anchor contient un journal append-only, initialisé à partir du snapshot vérifié 45311391405/1. Le Worker compare le hash de l'ancien préfixe d'audit et les générations, versions de clés et hashes de toutes les collections. Il réserve chaque run/tentative, écrit les ciphertexts KV puis ajoute l'ancre via CAS. Une copie orpheline après conflit n'est pas acceptée en récupération. Les sauvegardes historiques restent récupérables pour exercice isolé. D1 ne contient ni clé ni contenu déchiffré; seulement métadonnées et hashes. Cette garantie dépend de l'intégrité du compte Cloudflare et du workflow OIDC autorisé; elle ne protège pas contre la compromission simultanée de ces autorités.
