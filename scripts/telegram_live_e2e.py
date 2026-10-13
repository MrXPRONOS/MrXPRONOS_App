#!/usr/bin/env python3
"""Run the five EXISTING Telegram test workflows exactly once, in sequence.

Designed for a one-shot GitHub Actions run on main. No direct Telegram/Supabase
publishing is performed here. Child workflows own their secrets and test ledgers.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import time

REPO = os.environ["GITHUB_REPOSITORY"]
RUN_ID = os.environ["GITHUB_RUN_ID"]
STAGES = [
    ("smoke", "telegram-test-channel-smoke.yml", {}, "TELEGRAM_TEST_SMOKE_OK"),
    ("visuel", "football-visual-live-test-once.yml", {}, "XPRONOS_VISUAL_TEST_LIVE"),
    ("six_rubriques", "football-live-test-once.yml", {}, "XPRONOS_TEST_LIVE"),
    ("premium", "football-premium-validation-once.yml", {}, "XPRONOS_TEST_LIVE"),
    ("bsd_v2", "bsd-v2-telegram-hourly.yml",
     {"trigger_source": "manual-e2e-" + RUN_ID, "destination": "test"}, "BSD_V2_TELEGRAM:"),
]


def gh(*args, check=True):
    result = subprocess.run(["gh", *args], text=True, capture_output=True, check=False)
    if check and result.returncode:
        raise RuntimeError("GitHub CLI failed: " + " ".join(args[:3]) + " "
                           + result.stderr[-450:])
    return result


def runs(workflow):
    r = gh("api", "-X", "GET",
           f"repos/{REPO}/actions/workflows/{workflow}/runs",
           "-f", "branch=main", "-f", "event=workflow_dispatch",
           "-f", "per_page=50")
    return json.loads(r.stdout)["workflow_runs"]


def get_new_run(workflow, before, started):
    for _ in range(36):
        new = [x for x in runs(workflow)
               if x["id"] not in before
               and x.get("head_branch") == "main"
               and x.get("event") == "workflow_dispatch"
               and x.get("actor", {}).get("login") == "github-actions[bot]"
               and dt.datetime.fromisoformat(x["created_at"].replace("Z", "+00:00")) >= started]
        if new:
            return sorted(new, key=lambda x: x["id"])[0]["id"]
        time.sleep(5)
    raise RuntimeError("Run dispatch non retrouvé dans GitHub Actions")


def wait_run(workflow, run_id):
    for _ in range(120):
        match = next((r for r in runs(workflow) if r["id"] == run_id), None)
        if match is None:
            r = gh("api", f"repos/{REPO}/actions/runs/{run_id}")
            match = json.loads(r.stdout)
        if match["status"] == "completed":
            return match["conclusion"]
        time.sleep(10)
    raise RuntimeError("Délai dépassé pour le run " + str(run_id))


def evidence(stage, log):
    marker = next((m for name, _, _, m in STAGES if name == stage), "")
    hits = [line[-380:] for line in log.splitlines()
            if marker and marker in line
            and not line.lstrip().startswith("echo ")
            and "36;1m" not in line]
    if not hits:
        return "partielle", "Aucun marqueur de publication réelle"
    hit = hits[-1]
    if stage == "bsd_v2":
        match = re.search(r"BSD_V2_TELEGRAM:\s*({.*})", hit)
        if match:
            data = json.loads(match.group(1))
            if int(data.get("errors", 0)) > 0:
                return "partielle", hit
            if int(data.get("sent", 0)) + int(data.get("combos_sent", 0)) == 0:
                return "complete", "Aucun coupon éligible à cet instant; moteur sain: " + hit
    if stage in ("visuel", "six_rubriques", "premium"):
        match = re.search(r"XPRONOS_(?:VISUAL_TEST_LIVE|TEST_LIVE)\s+({.*})", hit)
        if match:
            data = json.loads(match.group(1))
            if data.get("errors") or data.get("skipped") or not data.get("sent"):
                return "partielle", hit
    return "complete", hit


def main():
    if os.getenv("GITHUB_REF") != "refs/heads/main" or os.getenv("GITHUB_RUN_ATTEMPT") != "1":
        print("E2E_ABORT: Ref non-main ou nouvelle tentative : aucun test envoyé.")
        return 2

    results = []
    for stage, workflow, inputs, marker in STAGES:
        print("E2E_START", stage, workflow, flush=True)
        before = {r["id"] for r in runs(workflow)}
        started = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=3)
        args = ["workflow", "run", workflow, "--ref", "main"]
        for k, v in inputs.items():
            args.extend(["-f", f"{k}={v}"])
        gh(*args)
        run_id = get_new_run(workflow, before, started)
        url = f"https://github.com/{REPO}/actions/runs/{run_id}"
        print("E2E_DISPATCHED", stage, run_id, url, flush=True)
        conclusion = wait_run(workflow, run_id)
        logs = gh("run", "view", str(run_id), "--log", check=False)
        state, proof = evidence(stage, logs.stdout if logs.returncode == 0 else "")
        if conclusion != "success":
            state = "partielle"
            proof = "GitHub workflow conclusion=" + str(conclusion) + "; " + proof
        print("E2E_RESULT", json.dumps({"stage": stage, "state": state,
                                        "conclusion": conclusion, "run_id": run_id,
                                        "evidence": proof}, ensure_ascii=False), flush=True)
        results.append({"stage": stage, "state": state, "run_id": run_id,
                        "url": url, "evidence": proof})
        if stage == "smoke" and state != "complete":
            print("E2E_ABORT: smoke non confirmé, les autres envois sont bloqués.")
            break

    print("E2E_FINAL_REPORT", json.dumps(results, ensure_ascii=False), flush=True)
    if any(x["state"] != "complete" for x in results) or len(results) < len(STAGES):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
