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


def test_social_buttons_right_safe_zone_and_background_not_scaled():
    assert 0.80 <= neon.ARTWORK_SCALE <= 0.90
    assert neon.ARTWORK_X <= 10
    assert neon.ARTWORK_X + round((neon.CARD_X[1] + neon.CARD_W + 2) * neon.ARTWORK_SCALE) <= 620
    assert neon.ARTWORK_X + round((8 + 704) * neon.ARTWORK_SCALE) <= 625
    assert neon.ARTWORK_Y + round((neon.TELEGRAM_Y + 210) * neon.ARTWORK_SCALE) < 1060

    # Stadium must stay full-frame: foreground transparent areas change nothing.
    clear = Image.new("RGBA", (neon.W, neon.H), (0, 0, 0, 0))
    output = neon.fit_artwork(clear)
    stadium = neon.stadium_background()
    for sample in ((680, 500), (700, 1000), (50, 1200)):
        assert output.getpixel(sample) == stadium.getpixel(sample)


def test_global_dark_rectangle_removed_while_cards_are_separate():
    from dcscore.video_render import Crest
    logo = Crest(Image.new("RGBA", (40, 40), (240, 220, 60, 255)), True)
    clips = [{"headline": "Home Club - Away Club", "display_score": "1-2"} for _ in range(10)]
    raw = neon.base_frame({"date_local_africa_lome": "2026-11-10"},
                          clips, [(logo, logo)] * 10, preview=False)
    assert raw.getpixel((11, 340))[3] == 0, "No large global black panel behind fixtures"
    assert raw.getpixel((30, neon.CARD_Y0 + 15))[3] > 150


def test_real_logo_test_mode_refuses_placeholder_letters(tmp_path):
    import pytest
    clips = [{"headline": f"Home {i} - Away {i}", "display_score": "0-0"}
             for i in range(10)]
    payload = {"date_local_africa_lome": "2026-11-10", "clips": clips}
    with pytest.raises(ValueError, match="vrais écussons"):
        neon.render(payload, tmp_path / "should_not_render.mp4",
                    preview=True, require_real_logos=True)


def test_score_label_is_weighted_for_pale_and_yellow_states():
    assert neon.SCORE_HALF_WIDTH <= 47
    before = Image.new("RGBA", (neon.W, neon.H), (0, 0, 0, 0))
    after = before.copy()
    neon.draw_score(before, {"display_score": "10-10"}, 23, 235, -1)
    neon.draw_score(after, {"display_score": "10-10"}, 23, 235, 1.0)
    assert before.getbbox() is not None and after.getbbox() is not None
