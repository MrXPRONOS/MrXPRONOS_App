#!/usr/bin/env python3
"""Merge GitHub-backed Telegram monitoring snapshots after concurrent commits."""
import json
import sys
from pathlib import Path


def merge(incoming, saved):
    result = {"schema": 1, "tables": {}, "reports": {}}
    if incoming.get("schema") != 1 or saved.get("schema", 1) != 1:
        raise ValueError("Invalid monitoring schema")
    for name, fields in (("telegram_channel_metrics_daily", ("channel_id", "observed_on")),
                         ("telegram_channel_official_stats", ("channel_id", "week_start"))):
        entries = {}
        for source in (saved, incoming):
            for row in source.get("tables", {}).get(name, []):
                key = tuple(str(row.get(f)) for f in fields)
                entries[key] = {**entries.get(key, {}), **row}
        result["tables"][name] = sorted(entries.values(),
                                      key=lambda row: tuple(str(row.get(f)) for f in fields))
    dates = set(saved.get("reports", {})) | set(incoming.get("reports", {}))
    for day in sorted(dates):
        old, new = saved.get("reports", {}).get(day, {}), incoming.get("reports", {}).get(day, {})
        parts = {**old.get("parts", {}), **new.get("parts", {})}
        complete = old.get("status") == "sent" or new.get("status") == "sent"
        merged = {**old, **new, "parts": parts, "status": "sent" if complete else "pending"}
        if complete:
            merged["sent_at"] = old.get("sent_at") or new.get("sent_at")
        result["reports"][day] = merged
    return result


def main():
    source, target = map(Path, sys.argv[1:3])
    new = json.loads(source.read_text(encoding="utf-8"))
    old = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {"schema": 1}
    data = merge(new, old)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(target)


if __name__ == "__main__":
    main()
