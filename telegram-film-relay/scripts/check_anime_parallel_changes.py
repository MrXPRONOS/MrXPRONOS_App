"""Pre-merge CineX Anime V2 collision guard.

Compare the PR patch against CURRENT main since the real merge base, and
against other recently touched CinéX pull requests. No repository mutation,
no automatic merge/deployment. Fail closed on unreadable metadata.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen


def _git(*args):
    return subprocess.check_output(
        ["git", *args], text=True, timeout=30).strip()


def _names(base, head):
    output = _git("diff", "--name-only", base, head, "--")
    return {p for p in output.splitlines() if p}


def compare_main(head, base):
    split = _git("merge-base", head, base)
    ours = _names(split, head)
    main = _names(split, base)
    return {"merge_base": split,
            "changed_by_us": sorted(ours),
            "changed_in_main": sorted(main),
            "overlap": sorted(ours & main)}


def _api(path):
    repo = os.environ["GITHUB_REPOSITORY"]
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "cinex-anime-v2-premerge-check"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request("https://api.github.com/repos/" + repo + path,
                  headers=headers)
    with urlopen(req, timeout=20) as response:
        return json.load(response)


def concurrent_pr_overlaps(changed, *, current_pr):
    now = datetime.now(timezone.utc)
    clashes = []
    for pr in _api("/pulls?state=open&per_page=100"):
        if int(pr["number"]) == current_pr:
            continue
        title = str(pr.get("title") or "").lower()
        if not any(tag in title for tag in (
                "cinex", "cinéx", "anime", "cine radar", "cineradar")):
            continue
        updated = datetime.fromisoformat(pr["updated_at"].replace("Z", "+00:00"))
        if now - updated > timedelta(days=7):
            continue
        paths = set()
        for page in range(1, 6):
            entries = _api(
                f"/pulls/{pr['number']}/files?per_page=100&page={page}")
            paths.update(item["filename"] for item in entries)
            if len(entries) < 100:
                break
        overlap = sorted(changed & paths)
        if overlap:
            clashes.append({"pr": int(pr["number"]), "paths": overlap})
    return clashes


def main():
    head = os.environ["CINEX_HEAD_SHA"]
    base = os.environ.get("CINEX_BASE_REF", "origin/main")
    result = compare_main(head, base)
    overlaps = concurrent_pr_overlaps(
        set(result["changed_by_us"]),
        current_pr=int(os.environ.get("CINEX_PR_NUMBER", "0")))
    result["concurrent_cinex_pr_overlaps"] = overlaps
    # Do not output paths containing private state file IDs or tokens.
    print(json.dumps({
        "changed_files": len(result["changed_by_us"]),
        "main_concurrent_files": len(result["changed_in_main"]),
        "main_colliding_files": len(result["overlap"]),
        "concurrent_cinex_prs": [p["pr"] for p in overlaps],
    }, sort_keys=True))
    # A concurrent change *merged into main* can overwrite deployed code:
    # hard block. An unfinished draft PR has not changed production and is
    # reported for review, but cannot veto a reconciled release forever.
    for row in overlaps:
        print("UNMERGED PR " + str(row["pr"]) + " OVERLAP (review only) " +
              ", ".join(row["paths"]), file=sys.stderr)
    if result["overlap"]:
        print("CineX Anime V2: main was changed after the tested base; "
              "reconcile before merge.", file=sys.stderr)
        for item in result["overlap"]:
            print("MAIN COLLISION " + item, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("CineX parallel-work guard failed closed: " +
              type(exc).__name__, file=sys.stderr)
        raise SystemExit(2)
