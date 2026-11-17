"""Persist the latest CineX monitor across GitHub main-state rebases."""
import json
import sys
from pathlib import Path
from datetime import datetime


def merge(incoming: dict, current: dict) -> dict:
    def stamp(row):
        try:
            return datetime.fromisoformat(str(row.get("last_checked", ""))).timestamp()
        except (ValueError, TypeError, OverflowError):
            return 0.0
    return incoming if stamp(incoming) >= stamp(current) else current


def main():
    src, dst = map(Path, sys.argv[1:3])
    newer = json.loads(src.read_text(encoding="utf-8"))
    older = json.loads(dst.read_text(encoding="utf-8")) if dst.exists() else {}
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(merge(newer, older), ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")


if __name__ == "__main__":
    main()
