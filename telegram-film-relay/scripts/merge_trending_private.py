"""Merge CineX private channel checkpoints after concurrent GitHub workflow runs."""
from __future__ import annotations
import json
import sys
from pathlib import Path


def merge(base: dict, incoming: dict) -> dict:
    output = {**base, "channels": dict(base.get("channels", {}))}
    for key, row in incoming.get("channels", {}).items():
        if not isinstance(row, dict):
            continue
        current = dict(output["channels"].get(key, {}))
        if current.get("channel_id") and row.get("channel_id") and current["channel_id"] != row["channel_id"]:
            raise ValueError("Conflit : deux canaux Telegram distincts pour " + key)
        current.update({k:v for k,v in row.items() if k != "copied" and v is not None})
        current["copied"] = {**(output["channels"].get(key, {}).get("copied") or {}),
                             **(row.get("copied") or {})}
        output["channels"][key] = current
    return output


def main():
    src, dst = map(Path, sys.argv[1:3])
    old = json.loads(dst.read_text(encoding="utf-8")) if dst.exists() else {"channels": {}}
    new = json.loads(src.read_text(encoding="utf-8"))
    dst.write_text(json.dumps(merge(old, new), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")


if __name__ == "__main__":
    main()
