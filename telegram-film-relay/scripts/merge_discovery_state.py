"""Merge notification receipts for discovered channels without re-notifying users."""
import json
import sys
from datetime import datetime
from pathlib import Path


def merge(remote: dict, local: dict) -> dict:
    def time_of(item: dict) -> str:
        return str(item.get("last_detected") or item.get("first_detected") or "")
    entries = {}
    for entry in remote.get("channels", []):
        if entry.get("username"):
            entries[entry["username"].casefold()] = dict(entry)
    for entry in local.get("channels", []):
        if not entry.get("username"):
            continue
        key = entry["username"].casefold()
        prior = entries.get(key, {})
        current = dict(entry) if time_of(entry) >= time_of(prior) else dict(prior)
        for field in ("notified_saved_messages_at", "first_detected"):
            found = [value for value in (prior.get(field), entry.get(field)) if value]
            if found:
                current[field] = min(found) if field == "first_detected" else max(found)
        entries[key] = current
    latest = local if str(local.get("last_scan", "")) >= str(remote.get("last_scan", "")) else remote
    return {
        "last_scan": latest.get("last_scan"),
        "notice": latest.get("notice", ""),
        "statistics": latest.get("statistics", {}),
        "channels": sorted(entries.values(), key=lambda e: (
            -int(e.get("matching_pairs", 0)), str(e.get("username", "")).casefold()
        ))[:300],
    }


def main():
    local_path, remote_path = map(Path, sys.argv[1:3])
    local = json.loads(local_path.read_text(encoding="utf-8"))
    remote = json.loads(remote_path.read_text(encoding="utf-8")) if remote_path.exists() else {}
    result = merge(remote, local)
    temporary = remote_path.with_suffix(".merge.tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(remote_path)


if __name__ == "__main__":
    main()
