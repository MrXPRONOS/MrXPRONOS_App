"""One-time, all-or-nothing initialization of encrypted V2 collections.

Does not import old publication history or activate Telegram. Safe to re-run:
if all collections exist, validates them and makes no commit. Partially present
collections are deliberately rejected instead of silently overwritten.
"""
import os
from scripts.actu_foot_github_vault import VaultError
from scripts.actu_foot_v2_store import COLLECTIONS, collection_path, encrypt, append_audit
from scripts.actu_foot_v3_atomic import GitAtomicStore


def bootstrap(store):
    parent, tree = store.head()
    already = {}
    for name in COLLECTIONS:
        current = store.load_collection(name, parent)
        already[name] = current.exists
    if all(already.values()):
        print("V2_ALL_COLLECTIONS_VERIFIED", len(COLLECTIONS))
        return None
    if any(already.values()):
        raise VaultError("Partially initialized V2: manual review required")
    staged = {}
    for name in COLLECTIONS:
        records = (append_audit({}, "initialize_v2", {"collections": len(COLLECTIONS)})
                   if name == "audit" else {})
        staged[collection_path(name)] = encrypt(name, records, generation=1, key_version=1)
    commit = store.commit(parent, tree, staged,
                          message="ops(actu-foot-v3): initialize all V2 encrypted collections")
    print("V2_INITIALIZED_ATOMICALLY", len(COLLECTIONS), commit[:12])
    return commit


if __name__ == "__main__":
    bootstrap(GitAtomicStore(repo=os.environ["GITHUB_REPOSITORY"],
                             branch="main", token=os.environ["GITHUB_TOKEN"]))
