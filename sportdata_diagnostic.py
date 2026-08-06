#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Diagnostic SportData pour GitHub Actions, sans exposer les clés."""

from datetime import datetime, timedelta, timezone

from sportdata_api import check_account_status, fetch_games

UTC = timezone.utc


def main() -> int:
    now = datetime.now(UTC)
    today = now.date()

    print("=" * 70)
    print("DIAGNOSTIC SPORTDATA - Mr XPRONOS")
    print(f"UTC : {now.isoformat()}")
    print("=" * 70)

    status_rows = check_account_status()
    valid_keys = [row for row in status_rows if row.get("ok")]

    print(f"\nClés configurées : {len(status_rows)}")
    print(f"Clés valides selon /status : {len(valid_keys)}")

    dates = [today - timedelta(days=1), today, today + timedelta(days=1)]
    valid_responses = 0
    total_games = 0

    for day in dates:
        result = fetch_games(day, day)
        print(
            f"{day}: ok={result.ok}, matchs={len(result.games)}, "
            f"clé=#{result.key_index}, endpoint={result.endpoint}, raison={result.reason}"
        )
        if result.ok:
            valid_responses += 1
            total_games += len(result.games)

    if not valid_keys:
        print("\nERREUR: aucune clé n'est valide ou le endpoint /status est inaccessible.")
        return 1

    if valid_responses == 0:
        print("\nERREUR: aucune réponse allscores valide.")
        return 2

    if total_games == 0:
        print(
            "\nERREUR: les trois journées retournent zéro match. "
            "Le système refuse de publier un data.json vide."
        )
        return 3

    print(f"\nOK: {total_games} matchs reçus sur les trois journées.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
