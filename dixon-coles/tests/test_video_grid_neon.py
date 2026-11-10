"""Tests for the new neon grid; does not replace the original grid tests."""
from datetime import date
from pathlib import Path
import tempfile

from PIL import Image

from dcscore import video_grid_neon as neon


def test_approved_user_assets_and_transparency():
    neon.check_assets()
    with Image.open(neon.TITLE) as title:
        assert title.mode == "RGBA"
        assert title.getchannel("A").getextrema()[0] == 0
    with Image.open(neon.TELEGRAM) as badge:
        assert badge.mode == "RGBA"
        assert badge.getchannel("A").getextrema()[0] == 0


def test_five_rows_two_columns_with_safe_footer():
    p = neon.positions(10)
    assert len(p) == len(set(p)) == 10
    assert len({y for _, y in p}) == 5
    assert max(y + neon.CARD_H for _, y in p) < 900
    # Bigger gaps, centered CTA, reduced footer height and social UI exclusion.
    assert neon.CARD_Y0 >= 249
    last_card_bottom = max(y + neon.CARD_H for _, y in p)
    assert neon.TELEGRAM_Y - last_card_bottom >= 30
    assert neon.TELEGRAM_X + neon.TELEGRAM_WIDTH / 2 == neon.W / 2
    with Image.open(neon.TELEGRAM) as badge:
        telegram_bottom = neon.TELEGRAM_Y + round(
            badge.height * neon.TELEGRAM_WIDTH / badge.width)
    assert telegram_bottom * 1.5 <= 1630  # social controls / descriptions
    assert (neon.TELEGRAM_X + neon.TELEGRAM_WIDTH) * 1.5 <= 920


def test_reject_incomplete_grid():
    import pytest
    with pytest.raises(ValueError):
        neon.positions(9)


def test_dynamic_date_not_stuck_on_11_nov():
    background = Image.new("RGBA", (neon.W, neon.H), (2, 6, 20, 255))
    neon._draw_calendar_date(background, date(2026, 11, 10))
    assert background.getpixel((98, 179))[0] > 200


def test_compact_score_badge_does_not_cover_club_names():
    assert neon.SCORE_HALF_WIDTH <= 47
    assert neon.SCORE_HALF_HEIGHT <= 21
    assert neon.SCORE_CENTER_Y + neon.SCORE_HALF_HEIGHT < 80
    # The first team-name baseline is y+87; leave padding above the glyphs.
    assert neon.SCORE_CENTER_Y + neon.SCORE_HALF_HEIGHT <= 74


def test_render_frame_before_after_score_reveal():
    before = Image.new("RGBA", (neon.W, neon.H), (3, 10, 30, 255))
    clip = {"display_score": "2-1"}
    neon.draw_score(before, clip, 23, 235, -1)
    after = Image.new("RGBA", (neon.W, neon.H), (3, 10, 30, 255))
    neon.draw_score(after, clip, 23, 235, 1)
    assert before.getpixel((23 + neon.CARD_W // 2, 235+59)) != after.getpixel(
        (23 + neon.CARD_W // 2, 235+59))
