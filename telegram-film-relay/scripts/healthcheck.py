"""Safe, non-secret GitHub Actions diagnostic for Telegram Film Relay."""
from __future__ import annotations
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

def flag(name):
    return os.getenv(name, "").strip().lower() in ("true", "yes", "1", "on")

def format_ok(value, private=False):
    value = str(value or "").strip()
    if value.startswith("-100") and len(value) >= 9 and value[4:].isdigit():
        return True
    if private:
        return False
    value = value.lstrip("@")
    return 5 <= len(value) <= 32 and value[0].isalpha() and all(c.isalnum() or c == "_" for c in value)

def check(report, name, ok, hint=""):
    report["checks"][name] = {"status": "ok" if ok else "error"}
    if hint and not ok:
        report["checks"][name]["hint"] = hint

def record(report):
    report["last_checked"] = datetime.now(timezone.utc).isoformat()
    report["status"] = ("ready" if all(c["status"] == "ok" for c in report["checks"].values())
                        else "needs_attention")
    p = Path("state/health.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["## Telegram Film Relay — diagnostic", "", "État de la connexion : **" + report["status"] + "**",
             "", "Publication activée : **" + ("oui" if not report.get("publishing_blocked", True) else "non") + "**",
             "Découverte déjà exécutée : **" + ("oui" if report.get("discovery_has_run", False) else "non") + "**",
             ""]
    for name, item in report["checks"].items():
        lines.append(("- ✅ " if item["status"] == "ok" else "- ❌ ") + name +
                     (" — " + item.get("hint", "") if item.get("hint") else ""))
    lines.append("\nAucune valeur de secret, aucun identifiant privé et aucune invitation n'est affiché.")
    text = "\n".join(lines) + "\n"
    print(text)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text)

async def run():
    report = {"last_checked": None, "status": "pending", "checks": {}}
    aid = os.getenv("TG_API_ID", "").strip()
    ahash = os.getenv("TG_API_HASH", "").strip()
    session = os.getenv("TG_SESSION_STRING") or os.getenv("TG_STRING_SESSION") or os.getenv("TG_STREAM_SESSION") or ""
    private = os.getenv("TG_PRIVATE_CHANNEL", "").strip()
    public = os.getenv("TG_PUBLIC_CHANNEL", "").strip()
    secrets_ok = bool(aid.isdigit() and ahash and session)
    check(report, "Secrets TG_API_ID / TG_API_HASH / TG_SESSION_STRING (ou TG_STRING_SESSION)",
          secrets_ok, "Au moins un secret manque ou TG_API_ID n'est pas numérique.")
    check(report, "Format TG_PRIVATE_CHANNEL", format_ok(private, private=True),
          "Utiliser l'ID numérique du canal privé commençant par -100 ; son nom ne suffit pas.")
    check(report, "Format TG_PUBLIC_CHANNEL", format_ok(public),
          "Utiliser @username ou l'ID numérique -100 du canal public.")

    report["publishing_enabled"] = flag("FILM_PUBLISH_ENABLED")
    report["rights_attested"] = flag("TG_RIGHTS_ATTESTED")
    report["publishing_blocked"] = not (report["publishing_enabled"] and report["rights_attested"])
    source = Path("state/discovered_channels.json")
    try:
        report["discovery_has_run"] = bool(json.loads(source.read_text(encoding="utf-8")).get("last_scan"))
    except (ValueError, OSError):
        report["discovery_has_run"] = False

    if secrets_ok:
        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            from film_relay.runner import resolve_peer, find_broadcast_by_exact_title
            client = TelegramClient(StringSession(session), int(aid), ahash,
                                    request_retries=1, connection_retries=1,
                                    flood_sleep_threshold=0)
            await asyncio.wait_for(client.connect(), timeout=35)
            try:
                auth = await asyncio.wait_for(client.is_user_authorized(), timeout=15)
                check(report, "Session Telegram autorisée", auth,
                      "Session invalide ou révoquée ; générer une nouvelle StringSession.")
                if auth:
                    expected_public = "Super Mario Film"
                    matched = await asyncio.wait_for(
                        find_broadcast_by_exact_title(client, expected_public), timeout=35
                    )
                    check(report, "Super Mario Film trouvé dans ce compte",
                          len(matched) == 1,
                          "Impossible de trouver un canal unique de ce nom dans les dialogues Telegram.")
                    for kind, name, is_private in (("privé", private, True), ("public", public, False)):
                        if not format_ok(name, private=is_private):
                            continue
                        try:
                            peer = await asyncio.wait_for(resolve_peer(client, name), timeout=25)
                            check(report, "Accès au canal " + kind, bool(getattr(peer, "broadcast", False)),
                                  "La destination doit être un canal, pas un groupe.")
                            is_expected = True
                            if kind == "public":
                                is_expected = expected_public.casefold() in str(
                                    getattr(peer, "title", "") or "").casefold()
                                check(report, "TG_PUBLIC_CHANNEL correspond à Super Mario Film",
                                      is_expected,
                                      "Le canal défini sur GitHub porte un autre nom. "
                                      "Mettre l'ID -100 ou @username de Super Mario Film.")
                            if getattr(peer, "broadcast", False) and is_expected and flag("FILM_HEALTH_SEND_TEST"):
                                try:
                                    await asyncio.wait_for(client.send_message(
                                        peer, "🎬 CinéX — test technique de publication."), timeout=25)
                                    check(report, "Publication test " + kind, True)
                                    await asyncio.sleep(3)
                                except Exception as e:
                                    check(report, "Publication test " + kind, False, type(e).__name__)
                        except Exception as e:
                            check(report, "Accès au canal " + kind, False,
                                  type(e).__name__ + " : vérifier compte membre/admin et identifiant.")
            finally:
                await client.disconnect()
        except Exception as e:
            check(report, "Connexion Telegram", False,
                  type(e).__name__ + " : vérifier la session, l'API et le réseau.")
    record(report)
    return int(report["status"] != "ready")

if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
