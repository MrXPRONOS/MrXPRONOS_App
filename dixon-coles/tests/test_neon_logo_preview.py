"""Authentic crest checks for the one-shot Telegram layout preview."""
from datetime import date

import pytest

from scripts.build_neon_logo_preview import make_crest_demo, parse_preview_event


def event(n, *, missing=False):
    def team(i, name):
        result = {
            "id": str(i), "displayName": name,
            "logo": f"https://a.espncdn.com/i/teamlogos/soccer/500/{i}.png",
        }
        if missing:
            result.pop("logo")
        return result
    return {
        "id": str(100000 + n),
        "competitions": [{"competitors": [
            {"homeAway": "home", "team": team(n * 2 + 1, f"Home {n}")},
            {"homeAway": "away", "team": team(n * 2 + 2, f"Away {n}")},
        ]}],
    }


class Provider:
    def __init__(self, count=10):
        self.count = count
    def _fetch(self, league, selector):
        if league == "uefa.wchampions" and selector == "20261110":
            return [event(i) for i in range(self.count)]
        return []


def test_get_true_crest_urls_not_initials():
    payload = make_crest_demo(date(2026, 11, 10), provider=Provider())
    assert payload["demo_only"] is True
    assert len(payload["clips"]) == 10
    assert all("home_logo_url" in c and "away_logo_url" in c for c in payload["clips"])
    assert all(c["home_logo_url"].startswith("https://a.espncdn.com/") for c in payload["clips"])


def test_missing_badges_cannot_be_replaced_with_letter_placeholders():
    assert parse_preview_event(event(3, missing=True)) is None
    with pytest.raises(ValueError, match="Vrais écussons insuffisants"):
        make_crest_demo(date(2026, 11, 10), provider=Provider(count=7))
