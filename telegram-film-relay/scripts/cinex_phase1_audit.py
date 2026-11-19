"""Phase 1: fail CI on public Telegram invitation leakage or unsafe workflows.

Checks all CineX tracked state JSON, checks Telegram account serialization,
YAML duplicate keys and the approval gates for destructive operations.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github/workflows"
STATE = ROOT / "telegram-film-relay/state"
TELEGRAM_WORKFLOWS = [
    "telegram-film-relay.yml",
    "cinex-rescue-channels.yml",
    "cinex-public-video-rotation.yml",
    "cinex-trending-private.yml",
    "cine-radar-owned-private.yml",
    "cine-radar-avatars.yml",
    "cine-radar-official-posts.yml",
    "cinex-comedie-test.yml",
    "cinex-anime-test.yml",
    "cinex-channel-audit.yml",
    "cinex-phase1-health.yml",
]
INVITATION_PATTERN = re.compile(r"https?://t\.me/(?:\+|joinchat/)[A-Za-z0-9_-]{12,}", re.I)


class StrictLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node):
    output = {}
    for keynode, valuenode in node.value:
        key = loader.construct_object(keynode, deep=True)
        if key in output:
            raise ValueError(f"Clé YAML dupliquée : {key}")
        output[key] = loader.construct_object(valuenode, deep=True)
    return output


StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
)


def check() -> list[str]:
    issues = []
    for path in sorted(STATE.glob("*.json")):
        filename = path.name
        raw = path.read_text(encoding="utf-8")
        # Every file is checked as text first, including legacy JSON state files.
        if INVITATION_PATTERN.search(raw):
            issues.append(f"{filename}: invitation Telegram publique enregistrée")
        if filename not in ("rescue_channels.json", "trending_private.json"):
            continue
        try:
            data = json.loads(raw)
        except (ValueError, OSError):
            issues.append(f"{filename}: JSON de sécurité invalide")
            continue
        if isinstance(data, dict) and isinstance(data.get("channels", {}), dict):
            for key, item in data.get("channels", {}).items():
                if isinstance(item, dict) and ("invite" in item or "invite_link" in item):
                    issues.append(f"{filename}:{key}: clé d'invitation en clair")
    for name in TELEGRAM_WORKFLOWS:
        path = WF / name
        text = path.read_text(encoding="utf-8")
        try:
            data = yaml.load(text, Loader=StrictLoader)
        except (ValueError, yaml.YAMLError) as exc:
            issues.append(f"{name}: YAML invalide ou ambigu: {exc}")
            continue
        concurrency = data.get("concurrency", {})
        if concurrency.get("group") != "mrx-telegram-personal-account":
            issues.append(f"{name}: groupe Telegram absent ou différent")
        if concurrency.get("cancel-in-progress") is not False or concurrency.get("queue") != "max":
            issues.append(f"{name}: sérialisation ou file maximale non configurée")
    archive = (WF / "cinex-public-video-rotation.yml").read_text(encoding="utf-8")
    for key in ("CINEX_ARCHIVE_ENABLED", "CINEX_ARCHIVE_DELETE_APPROVED",
                "CINEX_RIGHTS_VERIFIED"):
        if key not in archive:
            issues.append(f"Archivage: approbation manquante {key}")
    if "github.event.head_commit.message" in archive or "cinex-archive-apply-2" in archive:
        issues.append("Archivage: activation destructrice par message de commit interdite")
    if "TG_RIGHTS_ATTESTED: 'true'" in archive:
        issues.append("Archivage: contrôle d'autorisation Telegram forcé à vrai")
    return issues


def main():
    issues = check()
    if issues:
        for item in issues:
            print("SECURITY ERROR: " + item)
        raise SystemExit(1)
    print("Ciné X phase 1: tous les contrôles de sécurité statiques ont réussi.")


if __name__ == "__main__":
    main()
