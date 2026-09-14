from datetime import date, timedelta

import pytest

from stickytasks import colors
from stickytasks.colors import Band, DEFAULT_BANDS


TODAY = date(2026, 9, 14)


@pytest.mark.parametrize(
    "offset,expected",
    [
        (-30, "Overdue"),
        (-1, "Overdue"),
        (0, "Due today"),
        (1, "Next 3 days"),
        (3, "Next 3 days"),
        (4, "This week"),
        (7, "This week"),
        (8, "Next 2 weeks"),
        (14, "Next 2 weeks"),
        (15, "Later"),
        (365, "Later"),
    ],
)
def test_band_boundaries(offset, expected):
    due = TODAY + timedelta(days=offset)
    assert colors.label_for(due, DEFAULT_BANDS, TODAY) == expected


def test_no_due_date_has_its_own_colour():
    assert colors.band_for(None, DEFAULT_BANDS, TODAY) is None
    assert colors.color_for(None, DEFAULT_BANDS, TODAY) == colors.DEFAULT_NO_DUE_COLOR.lower()


def test_bands_are_sorted_before_use():
    """A band list entered out of order still colours correctly."""
    scrambled = [
        Band("Later", None, "#00ff00"),
        Band("Soon", 2, "#ff0000"),
        Band("Middle", 10, "#ffff00"),
    ]
    assert colors.label_for(TODAY + timedelta(days=1), scrambled, TODAY) == "Soon"
    assert colors.label_for(TODAY + timedelta(days=5), scrambled, TODAY) == "Middle"
    assert colors.label_for(TODAY + timedelta(days=50), scrambled, TODAY) == "Later"


def test_missing_catch_all_falls_back_to_last_band():
    bounded = [Band("Soon", 2, "#ff0000"), Band("Middle", 10, "#ffff00")]
    assert colors.label_for(TODAY + timedelta(days=99), bounded, TODAY) == "Middle"


@pytest.mark.parametrize(
    "raw,expected",
    [("#ABCDEF", "#abcdef"), ("abcdef", "#abcdef"), ("#f00", "#ff0000"),
     ("f00", "#ff0000"), ("nonsense", "#9e9e9e"), ("", "#9e9e9e")],
)
def test_normalize_hex(raw, expected):
    assert colors.normalize_hex(raw) == expected


def test_text_colour_contrasts():
    assert colors.text_color_for("#ffffff") == "#000000"
    assert colors.text_color_for("#000000") == "#ffffff"
    assert colors.text_color_for("#fdd835") == "#000000"  # yellow band
    assert colors.text_color_for("#b71c1c") == "#ffffff"  # deep red band


def test_mix_blends_endpoints():
    assert colors.mix("#000000", "#ffffff", 0.0) == "#000000"
    assert colors.mix("#000000", "#ffffff", 1.0) == "#ffffff"
    assert colors.mix("#000000", "#ffffff", 0.5) == "#808080"
