#!/usr/bin/env python3
"""Prepare temporary, provenance-verified historical xG overlay for ML research.

Only certified football history exported from encrypted Git checkpoints is
accepted; measured xG comes from independently AES-GCM encrypted Git records.
The output is plaintext solely in /tmp and must never be committed.
"""
import argparse
import json
from pathlib import Path

from single_ml_v2_git import key_from_environment
from single_ml_v2_xg import enrich_from_encrypted


def prepare(source, target, *, key, root=None):
    source, target = Path(source), Path(target)
    if not str(target.resolve()).startswith("/tmp/"):
        raise ValueError("Plaintext temporary xG output must remain in /tmp")
    matches=json.loads(source.read_text(encoding="utf8"))
    kwargs={"root":root} if root is not None else {}
    enriched,report=enrich_from_encrypted(matches,key,**kwargs)
    target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_suffix(target.suffix+".tmp")
    try:
        with temp.open("x",encoding="utf8") as f:
            json.dump(enriched,f,ensure_ascii=False)
        temp.chmod(0o600)
        temp.replace(target)
    finally:
        if temp.exists():temp.unlink()
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True)
    p.add_argument("--out",default="/tmp/mrx_football_with_xg.json")
    p.add_argument("--root",default=None)
    a=p.parse_args()
    report=prepare(a.source,a.out,key=key_from_environment(),root=a.root)
    print("ML_V2_XG_PREPARE",json.dumps(report))

if __name__=="__main__":main()
