#!/usr/bin/env python3
"""CineRadar independent failover for the existing Telegram bot menu.

- Runs on GitHub Actions, not Cloudflare, D1 or Supabase.
- Checks both /health (real D1 query) and /app before restoring normal mode.
- Selects ONLY a bot whose webhook already matches CineRadar's production
  URL; never changes, deletes or consumes the Telegram webhook/updates.
- During an outage exposes the independent GitHub Pages maintenance status
  through the *default* Telegram menu and a short profile note.
- On recovery restores the previously known CineRadar menu and description.
- Never changes a custom menu, non-CineRadar bot, channel-specific menu,
  owner chat menu, or webhook. No secrets in output.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "https://cinecanaux-bot.cinecanaux-xpronos.workers.dev"
WEBHOOK = BASE + "/telegram"
APP = BASE + "/app"
STANDBY = "https://mrxpronos.github.io/MrXPRONOS_App/cineradar-secours/"
NORMAL_DESCRIPTION = "🎬🍿 Films, séries et animés : explore, découvre et ouvre tes canaux favoris !"
MAINT_DESCRIPTION = "🎬 CinéRadar est en maintenance. Retour dès que possible."
SELECTED_SECRETS = (
    "CINE_RADAR_BOT_TOKEN", "TELEGRAM_BOT_TOKEN",
    "CINEX_RADAR_BOT_TOKEN", "CINEX_BOT_TOKEN",
)


def telegram_api(token, method, payload=None):
    data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    request = Request(
        "https://api.telegram.org/bot" + token + "/" + method,
        data=data, headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=12) as response:
            doc = json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError("Telegram API unavailable") from exc
    if not isinstance(doc, dict) or doc.get("ok") is not True:
        raise RuntimeError("Telegram API operation was rejected")
    return doc.get("result")


def select_active_bot(env, api=telegram_api):
    tokens = [str(env.get(name) or "").strip() for name in SELECTED_SECRETS]
    unique = list(dict.fromkeys(t for t in tokens if t))
    matches = []
    seen = set()
    for token in unique:
        try:
            info = api(token, "getWebhookInfo", {})
            if not isinstance(info, dict) or str(info.get("url") or "") != WEBHOOK:
                continue
            profile = api(token, "getMe", {})
            ident = profile.get("id") if isinstance(profile, dict) else None
            if not isinstance(ident, int) or profile.get("is_bot") is not True:
                continue
            if ident in seen:
                continue
            matches.append(token)
            seen.add(ident)
        except RuntimeError:
            continue
    print("CINERADAR_STANDBY_PREFLIGHT candidates=%d matching_webhook_bots=%d"%(len(unique),len(matches)))
    if len(matches) != 1:
        raise RuntimeError("Cannot safely identify exactly one CineRadar production bot")
    return matches[0]


def read_health(probe):
    """Require actual D1 + app availability, never treat HTTP 5xx as healthy."""
    health = probe(BASE + "/health")
    if not isinstance(health, dict) or health.get("status") != 200:
        return False
    body = health.get("json")
    if not isinstance(body, dict) or body.get("service") != "cine-radar" or body.get("database") is not True:
        return False
    app = probe(APP)
    return app.get("status") == 200 and str(app.get("type") or "").startswith("text/html")


def http_probe(url):
    # Match the same curl transport used by the proven production deployment.
    # urllib on hosted CI has occasionally received bot-protection responses.
    try:
        output = subprocess.run([
            "curl", "--silent", "--show-error", "--location", "--max-time", "12",
            "--header", "Cache-Control: no-cache", "--user-agent", "curl/8.0",
            "--write-out", "\\n%{http_code}|%{content_type}", url,
        ], capture_output=True, text=True, timeout=16, check=False)
        body, separator, meta = output.stdout.rpartition("\n")
        if not separator:
            return {"status": 0, "type": "", "json": {}}
        code, content_type = meta.split("|", 1)
        status = int(code)
        parsed = json.loads(body) if url.endswith("/health") and status == 200 else {}
        return {"status": status, "type": content_type, "json": parsed}
    except (OSError, ValueError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return {"status": 0, "type": "", "json": {}}


def checked_health(probe=http_probe):
    # Two checks; distinguish a confirmed HTTP 5xx quota/service failure from
    # uncertain 0/403 statuses (CI networking, Bot Management, TLS, etc.).
    samples = []
    for round_id in range(2):
        health = probe(BASE + "/health")
        app = probe(APP)
        statuses = (health.get("status"), app.get("status"))
        healthy = (
            health.get("status") == 200
            and isinstance(health.get("json"), dict)
            and health["json"].get("service") == "cine-radar"
            and health["json"].get("database") is True
            and app.get("status") == 200
            and str(app.get("type") or "").startswith("text/html")
        )
        definitely_down = any(isinstance(code, int) and 500 <= code <= 599 for code in statuses)
        samples.append((healthy, definitely_down, statuses))
        print("CINERADAR_STANDBY_HTTP_%d health=%s app=%s" % (round_id + 1, statuses[0], statuses[1]))
        if round_id == 0:
            time.sleep(1)
    if all(result[0] for result in samples):
        return True
    if all(result[1] for result in samples):
        return False
    # A complete transport outage (DNS, TLS, timeout, unavailable Worker)
    # is genuine only when independent GitHub Pages is reachable, ruling out
    # a broader GitHub Actions runner networking problem.
    all_unreachable = all(all(code == 0 for code in result[2]) for result in samples)
    if all_unreachable:
        backup = probe(STANDBY)
        print("CINERADAR_STANDBY_BACKUP_HTTP=%s" % backup.get("status"))
        if backup.get("status") == 200:
            return False
    return None


def menu_url(info):
    if not isinstance(info, dict) or info.get("type") != "web_app":
        return ""
    web = info.get("web_app")
    return str(web.get("url") or "").rstrip("/") if isinstance(web, dict) else ""


def menu_payload(destination):
    return {"menu_button": {
        "type": "web_app", "text": "🔧 Maintenance" if destination == STANDBY else "🎬 Ciné Radar",
        "web_app": {"url": destination},
    }}


def reconcile(token, healthy, api=telegram_api):
    current = api(token, "getChatMenuButton", {})
    active = menu_url(current)
    if active not in (APP, STANDBY.rstrip("/")):
        raise RuntimeError("Bot default menu is customized; refusing to modify it")

    target = APP if healthy else STANDBY
    changed_menu = False
    changed_description = False
    if active != target.rstrip("/"):
        api(token, "setChatMenuButton", menu_payload(target))
        for attempt in range(3):
            time.sleep(1 if attempt == 0 else 2)
            confirmed = api(token, "getChatMenuButton", {})
            if menu_url(confirmed) == target.rstrip("/"):
                break
        else:
            # Only emit the public Telegram menu *type*, never a secret.
            raise RuntimeError("Bot menu update could not be verified: type=" + str(confirmed.get("type", "unknown"))[:20])
        changed_menu = True

    # Only modify known CineRadar profile descriptions; preserve customization.
    descriptor = api(token, "getMyShortDescription", {})
    if isinstance(descriptor, dict):
        current_desc = str(descriptor.get("short_description") or "")
        destination = NORMAL_DESCRIPTION if healthy else MAINT_DESCRIPTION
        if current_desc in (NORMAL_DESCRIPTION, MAINT_DESCRIPTION, "🎬 CinéRadar est en maintenance. Retour prévu à 00h05 (heure du Togo).", "🔧 CinéRadar en maintenance. Retour prévu à 00h05 (heure du Togo).") and current_desc != destination:
            api(token, "setMyShortDescription", {"short_description": destination})
            confirmed = api(token, "getMyShortDescription", {})
            if confirmed.get("short_description") != destination:
                raise RuntimeError("Bot short description update not confirmed")
            changed_description = True
    return {"mode": "operational" if healthy else "maintenance",
            "menu_changed": changed_menu, "description_changed": changed_description}


def main():
    token = select_active_bot(os.environ)
    healthy = checked_health()
    print("CINERADAR_STANDBY_REAL_HEALTH="+str(healthy).lower())
    if healthy is None:
        print("CINERADAR_STANDBY_SKIPPED reason=unconfirmed_outage")
        return
    result = reconcile(token, healthy)
    # Output no tokens, usernames, chat IDs, or private data.
    print("CINERADAR_GITHUB_STANDBY_OK " +
          " ".join(str(k) + "=" + str(v).lower() for k, v in result.items()))
    print("actual_site_healthy=" + str(healthy).lower())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Only fixed, locally authored RuntimeError messages; no secret or API payload.
        detail = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        print("CINERADAR_STANDBY_FAILED:" + detail[:160], file=sys.stderr)
        sys.exit(1)
