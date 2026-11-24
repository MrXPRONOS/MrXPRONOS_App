"""Atomic V2 key migration: preview and explicit, SHA-pinned all-collection rotation."""
from __future__ import annotations
import argparse
import hmac
import os
import re
from scripts.actu_foot_github_vault import VaultError, VaultConflict
from scripts.actu_foot_v2_store import COLLECTIONS, master_key, encrypt, decrypt, collection_path, append_audit
from scripts.actu_foot_v3_atomic import GitAtomicStore

def rotate_all(store, *, target=2, expected_commit="", execute=False, confirmation=""):
    if target!=2 or not os.getenv("ACTU_FOOT_V2_KEY_B64_V2","").strip():
        raise VaultError("Dedicated V2 key must be configured")
    new_key=master_key(target)
    if hmac.compare_digest(master_key(1),new_key):
        raise VaultError("New dedicated key must differ from legacy key")
    parent,tree=store.head()
    if execute and (confirmation!="ROTATE_ALL_ENCRYPTED_V2" or not re.fullmatch(r"[0-9a-f]{40}",expected_commit)):
        raise VaultError("Explicit rotation confirmation and expected commit required")
    if execute and parent!=expected_commit:
        raise VaultConflict("Approved repository head changed")
    states={name:store.load_collection(name,parent) for name in COLLECTIONS}
    if not all(state.exists for state in states.values()):
        raise VaultError("Incomplete collections")
    versions={state.key_version for state in states.values()}
    if versions=={2}:
        return {"status":"already_rotated","commit":parent,"collections":7}
    if versions!={1}:
        raise VaultError("Mixed or unsupported versions require manual review")
    staged={}
    for name,state in states.items():
        records=state.data
        if name=="audit":
            records=append_audit(records,"rotate_all_v2",{"from_version":1,"to_version":2,"collections":7})
        envelope=encrypt(name,records,generation=state.generation+1,key_version=2)
        if decrypt(name,envelope)[0]!=records:
            raise VaultError("Rotation round-trip failed")
        staged[collection_path(name)]=envelope
    if not execute:
        return {"status":"preview_verified","commit":parent,"collections":len(staged)}
    result=store.commit(parent,tree,staged,message="ops(actu-foot-v3): atomic V2 dedicated key rotation")
    for name in COLLECTIONS:
        state=store.load_collection(name,result)
        if not state.exists or state.key_version!=2 or state.generation!=states[name].generation+1:
            raise VaultError("Post-commit rotation verification failed")
    return {"status":"rotated_verified","commit":result,"collections":7}

def main():
    import json
    p=argparse.ArgumentParser()
    p.add_argument("--target",type=int,default=2)
    p.add_argument("--expected-commit",default="")
    p.add_argument("--execute",action="store_true")
    p.add_argument("--confirmation",default="")
    a=p.parse_args()
    store=GitAtomicStore(repo=os.environ["GITHUB_REPOSITORY"],branch="main",token=os.environ["GITHUB_TOKEN"])
    print("V2_ROTATION",json.dumps(rotate_all(store,target=a.target,expected_commit=a.expected_commit,execute=a.execute,confirmation=a.confirmation),sort_keys=True))
if __name__=="__main__":
    main()
