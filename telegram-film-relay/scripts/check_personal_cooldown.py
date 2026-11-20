"""Fail closed before opening the shared Telegram *personal* user session.

The 2026-11-20 FloodWait (31119 sec at ~08:06 UTC) is protected through
17:00 UTC, with a conservative buffer. Future known restrictions may extend
this date via TG_PERSONAL_COOLDOWN_UNTIL_UTC; cannot shorten the known wait.
This script makes no network requests or bot calls.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

KNOWN_UNTIL = datetime(2026, 11, 20, 17, 0, tzinfo=timezone.utc)


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("TG_PERSONAL_COOLDOWN_UNTIL_UTC doit contenir un fuseau UTC.")
    return parsed.astimezone(timezone.utc)


def blocked_until(env=None) -> datetime:
    env = os.environ if env is None else env
    value = str(env.get("TG_PERSONAL_COOLDOWN_UNTIL_UTC") or "").strip()
    extra = parse_utc(value) if value else KNOWN_UNTIL
    return max(KNOWN_UNTIL, extra)


def seconds_remaining(now=None, env=None) -> int:
    now = now or datetime.now(timezone.utc)
    return max(0, int((blocked_until(env) - now).total_seconds() + 0.999))


def main():
    remaining = seconds_remaining()
    if remaining:
        print(f"Pause Telegram utilisateur toujours active : {remaining} s restants. "
              "Aucune connexion MTProto ne sera lancée.", file=sys.stderr)
        return 75
    print("Pause Telegram utilisateur expirée : accès autorisé seulement "
          "sous réserve des limites Telegram en vigueur.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
