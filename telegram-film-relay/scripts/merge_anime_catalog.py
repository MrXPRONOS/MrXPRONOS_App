"""Safe merge of source-indexed Anime catalog episode receipts."""
import json
import sys
from pathlib import Path


def merge(remote: dict, local: dict) -> dict:
    # Preserve audit and cursor metadata during the workflow's state merge.
    result = {**remote, **local, "series": {}}
    result["source_observed"] = {}
    for snapshot in (remote, local):
        for key, seasons in snapshot.get("source_observed", {}).items():
            target = result["source_observed"].setdefault(key, {})
            for season, numbers in seasons.items():
                dest = target.setdefault(season, {})
                for episode, refs in numbers.items():
                    item = dest.setdefault(str(episode), [])
                    for ref in refs:
                        if ref not in item:
                            item.append(ref)
    result["scans"] = {**remote.get("scans", {})}
    for source, incoming in local.get("scans", {}).items():
        prior = result["scans"].get(source)
        if not prior:
            result["scans"][source] = incoming
        elif incoming.get("complete") and not prior.get("complete"):
            result["scans"][source] = incoming
        elif prior.get("complete") and not incoming.get("complete"):
            continue
        elif incoming.get("cursor") is None:
            if not prior.get("cursor"):
                result["scans"][source] = incoming
        elif prior.get("cursor") is None or int(incoming["cursor"]) <= int(prior["cursor"]):
            result["scans"][source] = incoming
    rseries = remote.get("series", {})
    lseries = local.get("series", {})
    for key in set(rseries) | set(lseries):
        older = rseries.get(key, {})
        newer = lseries.get(key, {})
        series = dict(older)
        series.update({k: v for k, v in newer.items() if k not in ("episodes", "source_items", "season_indices") and v is not None})
        series["source_items"] = {**older.get("source_items", {}), **newer.get("source_items", {})}
        series["season_indices"] = {**older.get("season_indices", {}), **newer.get("season_indices", {})}
        seasons = {}
        for season in set(older.get("episodes", {})) | set(newer.get("episodes", {})):
            seasons[season] = {**older.get("episodes", {}).get(season, {}),
                               **newer.get("episodes", {}).get(season, {})}
        series["episodes"] = seasons
        result["series"][key] = series
    return result


def main():
    local_path, remote_path = (Path(value) for value in sys.argv[1:3])
    local = json.loads(local_path.read_text(encoding="utf-8"))
    remote = json.loads(remote_path.read_text(encoding="utf-8")) if remote_path.exists() else {}
    updated = merge(remote, local)
    temp = remote_path.with_suffix(".merging")
    temp.write_text(json.dumps(updated, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    temp.replace(remote_path)


if __name__ == "__main__":
    main()
