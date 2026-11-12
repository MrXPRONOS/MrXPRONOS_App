#!/usr/bin/env python3
import json
import os
import pathlib
import subprocess
import threading
import time

from flask import Flask, jsonify, request

app = Flask(__name__)
LOCK = threading.Lock()
ROOT = pathlib.Path(__file__).resolve().parents[2]
RESULT = ROOT / "odds_diagnostic_results" / "onewin_togo_local_probe.json"
PROBE = ROOT / "tools" / "odds_diagnostic" / "onewin_togo_local_probe.py"
TOKEN = os.environ.get("RUN_TOKEN", "")


def authorized():
    if not TOKEN:
        return False
    supplied = request.headers.get("X-Run-Token") or request.args.get("token", "")
    return supplied == TOKEN


@app.get("/")
def home():
    return jsonify({
        "service": "Mr XPRONOS - 1win Render probe",
        "region": os.environ.get("RENDER_REGION", "unknown"),
        "endpoints": ["/health", "/run", "/result"],
        "note": "No login, no stake, no wager submission."
    })


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.get("/result")
def result():
    if not authorized():
        return jsonify({"error": "unauthorized"}), 401
    if not RESULT.exists():
        return jsonify({"status": "no_result_yet"}), 404
    return jsonify(json.loads(RESULT.read_text(encoding="utf-8")))


@app.route("/run", methods=["GET", "POST"])
def run_probe():
    if not authorized():
        return jsonify({"error": "unauthorized"}), 401
    if not LOCK.acquire(blocking=False):
        return jsonify({"status": "already_running"}), 409
    try:
        started = time.time()
        cp = subprocess.run(
            ["python", str(PROBE)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=150,
            env=os.environ.copy(),
        )
        payload = {
            "process_exit_code": cp.returncode,
            "elapsed_seconds": round(time.time() - started, 2),
            "stdout_tail": cp.stdout[-4000:],
            "stderr_tail": cp.stderr[-4000:],
        }
        if RESULT.exists():
            try:
                payload["report"] = json.loads(RESULT.read_text(encoding="utf-8"))
            except Exception as exc:
                payload["report_error"] = type(exc).__name__
        return jsonify(payload), 200 if cp.returncode == 0 else 500
    except subprocess.TimeoutExpired:
        return jsonify({"error": "probe_timeout"}), 504
    finally:
        LOCK.release()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
