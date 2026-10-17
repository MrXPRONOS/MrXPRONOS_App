"""Merge CinéX Désir Telegram receipts after concurrent GitHub commits."""
import json
import sys
from pathlib import Path

def merge(remote: dict, local: dict) -> dict:
    completed = {**local.get("completed", {}), **remote.get("completed", {})}
    staged = {**remote.get("staged", {}), **local.get("staged", {})}
    staged = {key: value for key, value in staged.items() if key not in completed}
    mirrors = {}
    for target in set(remote.get("mirrors", {})) | set(local.get("mirrors", {})):
        mirrors[target] = {
            **local.get("mirrors", {}).get(target, {}),
            **remote.get("mirrors", {}).get(target, {}),
        }
    return {"completed": completed, "staged": staged, "mirrors": mirrors}

def main():
    local_path, remote_path = (Path(v) for v in sys.argv[1:3])
    local = json.loads(local_path.read_text(encoding="utf-8"))
    remote = json.loads(remote_path.read_text(encoding="utf-8")) if remote_path.exists() else {}
    updated = merge(remote, local)
    temp = remote_path.with_suffix(".merge.tmp")
    temp.write_text(json.dumps(updated, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")
    temp.replace(remote_path)

if __name__ == "__main__":
    main()
