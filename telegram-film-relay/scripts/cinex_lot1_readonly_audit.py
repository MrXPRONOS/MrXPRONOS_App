"""Read-only production acceptance for CinéX V4 Lot 1.

Checks all seven saved Secours identities and their *existing* invitations,
then previews 24h retention on all six active public video channels.
No Telegram create/edit/post/delete API operation is called by this script.
Never put Telegram invitation links into console output or artifacts.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from film_relay.cinex_v4_policy import MAIN_RELAY_HANDLES
from film_relay.rescue_channels import read_state
from film_relay.rescue_links_runtime import hydrate
from film_relay.public_video_retention import (
    category_targets,
    execute,
    validate_retention_targets,
)

LOG = logging.getLogger("cinex.lot1.audit")


async def audit(*, history: int = 4000) -> int:
    issues = []
    channels = read_state().get("channels", {})
    registered = set(channels)
    if registered != MAIN_RELAY_HANDLES:
        missing = sorted(MAIN_RELAY_HANDLES - registered)
        extraneous = sorted(registered - MAIN_RELAY_HANDLES)
        issues.append("Secours enregistrés non conformes: manquants="
                      + repr(missing) + ", hors périmètre=" + repr(extraneous))
    # Prevalidate the six approved pairs even in preview mode; the existing
    # retention.execute() checks this only before destructive --apply.
    try:
        validate_retention_targets(category_targets())
    except Exception as exc:
        issues.append("Configuration rétention incomplète : " + str(exc))

    rescue_report = {"ready": 0, "missing": len(MAIN_RELAY_HANDLES)}
    try:
        # The private invite URLs exist only in a temporary 0600 file.
        # They are neither committed nor uploaded as workflow artifacts.
        with TemporaryDirectory(prefix="cinex-lot1-") as tempdir:
            runtime = Path(tempdir) / "private-invites.json"
            rescue_report = await hydrate(runtime)
    except Exception as exc:
        LOG.error("Invitations Secours non vérifiées : %s", type(exc).__name__)
        issues.append("Invitations Secours : vérification réseau échouée")
    if rescue_report["ready"] != len(MAIN_RELAY_HANDLES) or rescue_report["missing"]:
        issues.append(f"Secours incomplets : {rescue_report['ready']}/7 prêts")

    reports = []
    try:
        reports = await execute(apply=False, history=history)
        if len(reports) != 6:
            issues.append(f"Rétention : {len(reports)}/6 canaux examinés")
        elif any(row.get("errors") for row in reports):
            issues.append("Rétention : un ou plusieurs canaux non examinés")
        if any(row.get("history_truncated") for row in reports):
            issues.append("Rétention : historique tronqué ; vérification exhaustive impossible")
    except Exception as exc:
        LOG.error("Prévisualisation rétention impossible : %s", type(exc).__name__)
        issues.append("Prévisualisation rétention : échec")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fp:
            fp.write("\n### Lot 1 : contrôle réel de production (lecture seule)\n")
            fp.write(f"- Identités Secours enregistrées : {len(registered)}/7\n")
            fp.write(f"- Invitations privées vérifiées : {rescue_report['ready']}/7\n")
            fp.write(f"- Catégories publiques examinées : {len(reports)}/6\n")
            fp.write("- Média créé, publié, modifié ou supprimé : **aucun**\n")
            fp.write("- Suppression 24h effective : **non testée** (simulation uniquement)\n")
            for issue in issues:
                fp.write(f"- ⚠️ {issue}\n")
            if not issues:
                fp.write("- ✅ Contrôles en lecture seule validés ; "
                         "une suppression effective reste à observer séparément.\n")
    for issue in issues:
        LOG.error("LOT1_BLOCKER: %s", issue)
    LOG.info("LOT1_READONLY_RESULT rescue=%s/7 retention=%s/6 blockers=%s",
             rescue_report["ready"], len(reports), len(issues))
    return 1 if issues else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", type=int, default=4000)
    args = parser.parse_args()
    if not 100 <= args.history <= 10000:
        parser.error("--history doit être compris entre 100 et 10000")
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    raise SystemExit(asyncio.run(audit(history=args.history)))


if __name__ == "__main__":
    main()
