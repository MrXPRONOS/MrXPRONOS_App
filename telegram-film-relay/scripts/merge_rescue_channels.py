"""Merge durable Secours channel identifiers after other Github workflow commits."""
from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path


def merge(old: dict, incoming: dict) -> dict:
    if not isinstance(old.get("channels", {}), dict) or not isinstance(incoming.get("channels", {}), dict):
        raise ValueError("Rescue state must have channels dictionaries")
    result = {"channels": dict(old.get("channels", {}))}
    for key, item in incoming.get("channels", {}).items():
        prior = result["channels"].get(key, {})
        if not isinstance(item, dict) or not isinstance(prior, dict):
            raise ValueError("Invalid rescue channel checkpoint")
        for identity in ("public_id", "rescue_channel_id", "public_username"):
            if prior.get(identity) and item.get(identity) and str(prior[identity]) != str(item[identity]):
                raise ValueError(f"Conflicting Telegram rescue identity for {key}: {identity}")
        row = {**prior, **item}
        url = row.pop("invite_link", None)
        row.pop("invite", None)
        if url:
            row["invite_sha256"] = hashlib.sha256(url.encode()).hexdigest()
        result["channels"][key] = row
    return result


def main():
    src, dest = map(Path, sys.argv[1:3])
    old = json.loads(dest.read_text(encoding="utf-8")) if dest.exists() else {"channels": {}}
    new = json.loads(src.read_text(encoding="utf-8"))
    dest.write_text(json.dumps(merge(old, new), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


if __name__ == "__main__":
    main()
