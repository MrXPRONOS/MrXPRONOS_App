"""One-shot read-only GitHub audit of an already triggered REAL CineX run.

No Telegram login, no publication, no changes to the publishing workflow.
The report references only GitHub Actions steps and the preexisting Telegram
receipt verifier's output. A passed CI test is never counted as a publication.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GH_TOKEN"]
TARGET = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
OUT = Path(sys.argv[2])
if not re.fullmatch(r"[0-9a-f]{40}", TARGET):
    raise ValueError("SHA cible GitHub invalide")


def get(path, raw=False):
    request = Request("https://api.github.com/" + path, headers={
        "Authorization": "Bearer " + TOKEN,
        "Accept": "application/vnd.github+json",
        "User-Agent": "cinex-production-read-only-audit",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urlopen(request, timeout=25) as response:
        data = response.read()
    return data.decode("utf-8", errors="replace") if raw else json.loads(data)


result = {
    "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    "target_commit": TARGET,
    "source": "GitHub Actions production run metadata and real Telegram receipt verification",
    "telegram_messages_sent_by_audit": 0,
    "publication_verified": False,
}
try:
    query = f"repos/{REPO}/actions/workflows/telegram-film-relay.yml/runs?head_sha={TARGET}&per_page=30"
    runs = get(query).get("workflow_runs", [])
    selected = next((r for r in runs if r.get("head_sha") == TARGET
                     and r.get("event") == "push"), None)
    if selected is None:
        result["status"] = "run_not_found"
        result["explanation"] = "Aucune exécution push confirmée pour ce commit"
    else:
        run_id = int(selected["id"])
        result.update({
            "run_id": run_id,
            "run_url": selected.get("html_url"),
            "event": selected.get("event"),
            "run_status": selected.get("status"),
            "conclusion": selected.get("conclusion"),
        })
        if selected.get("status") != "completed":
            result["status"] = "run_in_progress"
        else:
            jobs = get(f"repos/{REPO}/actions/runs/{run_id}/jobs?per_page=100").get("jobs", [])
            result["jobs"] = [{
                "name": j.get("name"),
                "conclusion": j.get("conclusion"),
                "failed_steps": [s.get("name") for s in j.get("steps", [])
                                 if s.get("conclusion") == "failure"],
                "telegram_verify_step": next(
                    (s.get("conclusion") for s in j.get("steps", [])
                     if s.get("name") == "Confirmer les nouvelles publications directement sur Telegram"),
                    "not_found")
            } for j in jobs]
            check = next((j for j in jobs if any(
                s.get("name") == "Confirmer les nouvelles publications directement sur Telegram"
                for s in j.get("steps", []))), None)
            if check:
                logs = get(f"repos/{REPO}/actions/jobs/{check['id']}/logs", raw=True)
                match = re.search(r"Vérification Telegram réelle\s*:\s*(\{[^\r\n]+\})", logs)
                if match:
                    evidence = json.loads(match.group(1))
                    result["real_telegram_receipts"] = {
                        "status": evidence.get("status"),
                        "verified_posts": evidence.get("verified_posts", 0),
                        "categories": evidence.get("categories", {}),
                        "errors": evidence.get("errors", []),
                    }
                    result["publication_verified"] = (
                        evidence.get("status") == "verified"
                        and evidence.get("verified_posts", 0) > 0
                    )
            result["status"] = ("completed_telegram_verified" if result["publication_verified"]
                                else "completed_no_publication_proof")
except Exception as exc:
    result["status"] = "audit_error"
    result["error_type"] = type(exc).__name__
    result["explanation"] = "Impossible de lire les métadonnées GitHub ; aucune conclusion Telegram"

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("CineX real-run audit:", result["status"], "run:", result.get("run_id"))
