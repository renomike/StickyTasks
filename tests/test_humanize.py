from datetime import date

import pytest

from stickytasks import humanize

TODAY = date(2026, 9, 14)


@pytest.mark.parametrize(
    "offset,expected",
    [
        (-90, "overdue by 3 months"),
        (-21, "overdue by 3 weeks"),
        (-3, "overdue by 3 days"),
        (-1, "overdue by 1 day"),
        (0, "due today"),
        (1, "due tomorrow"),
        (5, "in 5 days"),
        (21, "in 3 weeks"),
        (90, "in 3 months"),
    ],
)
def test_due_phrase(offset, expected):
    from datetime import timedelta

    assert humanize.due_phrase(TODAY + timedelta(days=offset), TODAY) == expected


def test_due_phrase_without_date():
    assert humanize.due_phrase(None, TODAY) == "no due date"


def test_short_date_has_no_leading_zero():
    assert humanize.short_date(date(date.today().year, 9, 5)) == "Sep 5"


def test_short_date_includes_other_years():
    other = date.today().year + 1
    assert str(other) in humanize.short_date(date(other, 9, 5))


def test_plural():
    assert humanize.plural(1, "task") == "1 task"
    assert humanize.plural(2, "task") == "2 tasks"
    assert humanize.plural(0, "task") == "0 tasks"
