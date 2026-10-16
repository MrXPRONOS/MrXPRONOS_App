"""Merge a Film Relay run checkpoint into the latest remote GitHub state.

The runner saves its local checkpoint under RUNNER_TEMP before any pull/reset.
Every retry starts from origin/main and reapplies the saved receipts.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path


def combine(current: dict, incoming: dict) -> dict:
    merged = {**incoming, **current}
    # A post received and recorded by either run remains complete.
    # Current remote receipts win if simultaneous runs recorded the same pair.
    complete = {**incoming.get("processed", {}), **current.get("processed", {})}
    merged["processed"] = complete

    videos = {**incoming.get("videos", {}), **current.get("videos", {})}
    merged["videos"] = videos

    mirrors = {}
    for target in set(incoming.get("mirrors", {})) | set(current.get("mirrors", {})):
        mirrors[target] = {
            **incoming.get("mirrors", {}).get(target, {}),
            **current.get("mirrors", {}).get(target, {}),
        }
    merged["mirrors"] = mirrors

    # Incomplete media must survive failure; completed pairs must never
    # re-enter the staged queue.
    staged = {**incoming.get("staged", {}), **current.get("staged", {})}
    merged["staged"] = {key: value for key, value in staged.items()
                        if key not in complete}

    seen = {}
    for key in set(incoming.get("last_seen", {})) | set(current.get("last_seen", {})):
        seen[key] = max(
            int(incoming.get("last_seen", {}).get(key, 0)),
            int(current.get("last_seen", {}).get(key, 0)),
        )
    merged["last_seen"] = seen

    # Archive scans are cyclic: remote progress wins on conflict.
    merged["history"] = {
        **incoming.get("history", {}),
        **current.get("history", {}),
    }
    return merged


def main() -> None:
    incoming_path, current_path = map(Path, sys.argv[1:3])
    incoming = json.loads(incoming_path.read_text(encoding="utf-8"))
    current = (json.loads(current_path.read_text(encoding="utf-8"))
               if current_path.exists() else {})
    merged = combine(current, incoming)
    tmp = current_path.with_suffix(".merge.tmp")
    tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2,
                              sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(current_path)


if __name__ == "__main__":
    main()
