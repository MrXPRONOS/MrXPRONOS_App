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
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "https://cinecanaux-bot.cinecanaux-xpronos.workers.dev"
WEBHOOK = BASE + "/telegram"
APP = BASE + "/app"
STANDBY = "https://mrxpronos.github.io/MrXPRONOS_App/cineradar-secours/"
NORMAL_DESCRIPTION = "🎬🍿 Films, séries et animés : explore, découvre et ouvre tes canaux favoris !"
MAINT_DESCRIPTION = "🔧 CinéRadar en maintenance. Retour prévu à 00h05 (heure du Togo)."
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
    request = Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "CineRadar-GitHub-Standby/1.0"})
    try:
        with urlopen(request, timeout=13) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            data = {}
            if url.endswith("/health") and status == 200:
                data = json.loads(response.read(20000).decode("utf-8"))
            return {"status": status, "type": content_type, "json": data}
    except (HTTPError, URLError, TimeoutError, ValueError):
        return {"status": 0, "type": "", "json": {}}


def checked_health(probe=http_probe):
    # Two checks prevent reacting to a single transient network timeout.
    first = read_health(probe)
    if not first:
        time.sleep(1)
    second = read_health(probe)
    return first and second


def menu_url(info):
    if not isinstance(info, dict) or info.get("type") != "web_app":
        return ""
    web = info.get("web_app")
    return str(web.get("url") or "") if isinstance(web, dict) else ""


def menu_payload(destination):
    return {"menu_button": {
        "type": "web_app", "text": "🔧 Maintenance" if destination == STANDBY else "🎬 Ciné Radar",
        "web_app": {"url": destination},
    }}


def reconcile(token, healthy, api=telegram_api):
    current = api(token, "getChatMenuButton", {})
    active = menu_url(current)
    if active not in (APP, STANDBY):
        raise RuntimeError("Bot default menu is customized; refusing to modify it")

    target = APP if healthy else STANDBY
    changed_menu = False
    changed_description = False
    if active != target:
        api(token, "setChatMenuButton", menu_payload(target))
        confirmed = api(token, "getChatMenuButton", {})
        if menu_url(confirmed) != target:
            raise RuntimeError("Bot menu update could not be verified")
        changed_menu = True

    # Only modify known CineRadar profile descriptions; preserve customization.
    descriptor = api(token, "getMyShortDescription", {})
    if isinstance(descriptor, dict):
        current_desc = str(descriptor.get("short_description") or "")
        destination = NORMAL_DESCRIPTION if healthy else MAINT_DESCRIPTION
        if current_desc in (NORMAL_DESCRIPTION, MAINT_DESCRIPTION) and current_desc != destination:
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
    result = reconcile(token, healthy)
    # Output no tokens, usernames, chat IDs, or private data.
    print("CINERADAR_GITHUB_STANDBY_OK " +
          " ".join(str(k) + "=" + str(v).lower() for k, v in result.items()))
    print("actual_site_healthy=" + str(healthy).lower())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("CINERADAR_STANDBY_FAILED:" + type(exc).__name__, file=sys.stderr)
        sys.exit(1)
