"""Fusion de l'historique des recherches quotidiennes Telegram."""
import json
import sys
from pathlib import Path

def merge(remote, local):
    result = dict(remote)
    result["known_usernames"] = sorted(set(remote.get("known_usernames", [])) | set(local.get("known_usernames", [])))
    if str(local.get("last_scan", "")) >= str(remote.get("last_scan", "")):
        for key in ("last_scan", "last_notification_day", "categories", "offsets"):
            if key in local:
                result[key] = local[key]
    return result

def main():
    local, remote = (Path(p) for p in sys.argv[1:3])
    incoming = json.loads(local.read_text(encoding="utf-8"))
    existing = json.loads(remote.read_text(encoding="utf-8")) if remote.exists() else {}
    data = merge(existing, incoming)
    temp = remote.with_suffix(".merging")
    temp.write_text(json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(remote)

if __name__ == "__main__":
    main()
