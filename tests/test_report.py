from datetime import date

import pytest

from stickytasks import report
from stickytasks.models import STATUS_COMPLETE, STATUS_IN_WORK


def complete_on(db, task_id, when: str):
    """Force a completion timestamp so date-range queries are deterministic."""
    db.set_status(task_id, STATUS_COMPLETE)
    db.conn.execute(
        "UPDATE tasks SET completed_at=?, updated_at=? WHERE id=?",
        (when, when, task_id),
    )
    db.conn.execute(
        "UPDATE status_events SET changed_at=? WHERE task_id=? AND to_status=?",
        (when, task_id, STATUS_COMPLETE),
    )
    db.conn.commit()


@pytest.fixture
def populated(db):
    a = db.add_task("Migrate billing service", project="Platform", due_date=date(2026, 3, 1))
    complete_on(db, a.id, "2026-03-02T14:30:00")

    b = db.add_task("Write onboarding guide", project="Docs", note_plain="Covered setup and FAQ.")
    complete_on(db, b.id, "2026-06-10T09:00:00")

    c = db.add_task("Old work", project="Platform")
    complete_on(db, c.id, "2025-11-01T09:00:00")  # outside a 2026 window

    db.add_task("Still going", project="Platform", status=STATUS_IN_WORK)
    return db


def test_completed_scope_respects_date_window(populated):
    opts = report.ReportOptions(start=date(2026, 1, 1), end=date(2026, 12, 31))
    titles = [t.title for t in report.collect(populated, opts)]
    assert titles == ["Write onboarding guide", "Migrate billing service"] or set(titles) == {
        "Write onboarding guide", "Migrate billing service"
    }
    assert "Old work" not in titles
    assert "Still going" not in titles


def test_window_boundaries_are_inclusive(populated):
    opts = report.ReportOptions(start=date(2026, 3, 2), end=date(2026, 3, 2))
    assert [t.title for t in report.collect(populated, opts)] == ["Migrate billing service"]


def test_activity_scope_includes_open_tasks(populated):
    opts = report.ReportOptions(
        start=date(2026, 1, 1), end=date(2026, 12, 31), scope=report.SCOPE_ACTIVITY
    )
    titles = {t.title for t in report.collect(populated, opts)}
    assert "Still going" in titles
    assert "Migrate billing service" in titles


def test_markdown_report_structure(populated):
    opts = report.ReportOptions(
        start=date(2026, 1, 1), end=date(2026, 12, 31), title="2026 Review"
    )
    out = report.generate(populated, opts)

    assert out.startswith("# 2026 Review")
    assert "**Period:** 2026-01-01 to 2026-12-31" in out
    assert "| Project | Total | Complete | In Work | To Do |" in out
    assert "#### Migrate billing service" in out
    assert "### Platform" in out
    assert "> Covered setup and FAQ." in out
    assert "Old work" not in out


def test_text_report_structure(populated):
    opts = report.ReportOptions(
        start=date(2026, 1, 1), end=date(2026, 12, 31),
        fmt=report.FORMAT_TEXT, title="2026 Review",
    )
    out = report.generate(populated, opts)

    assert out.startswith("2026 REVIEW")
    assert "Period:    2026-01-01 to 2026-12-31" in out
    assert "* Migrate billing service" in out
    assert "[Platform]" in out
    assert "Covered setup and FAQ." in out


def test_empty_period_says_so(populated):
    opts = report.ReportOptions(start=date(2020, 1, 1), end=date(2020, 12, 31))
    assert "_No tasks matched this period._" in report.generate(populated, opts)

    opts.fmt = report.FORMAT_TEXT
    assert "No tasks matched this period." in report.generate(populated, opts)


def test_history_section_is_opt_in(populated):
    opts = report.ReportOptions(
        start=date(2026, 1, 1), end=date(2026, 12, 31), include_history=True
    )
    out = report.generate(populated, opts)
    assert "Status history in period:" in out
    assert "To Do → Complete" in out


def test_pipe_in_title_does_not_break_table(db):
    t = db.add_task("A | B", project="Ops | Infra")
    complete_on(db, t.id, "2026-05-01T10:00:00")
    out = report.generate(
        db, report.ReportOptions(start=date(2026, 1, 1), end=date(2026, 12, 31))
    )
    assert r"Ops \| Infra" in out
    header_cols = out.split("| Project | Total")[1].splitlines()[0]
    assert header_cols  # table header survived


@pytest.mark.parametrize(
    "html,expected",
    [
        ("<p>Hello</p>", "Hello"),
        ("<p>One</p><p>Two</p>", "One\nTwo"),
        ("a<br>b", "a\nb"),
        ("<ul><li>x</li><li>y</li></ul>", "- x\n- y"),
        ("<p>Pic: <img src='a.png'></p>", "Pic: [image]"),
        ("<style>p{color:red}</style><p>Body</p>", "Body"),
        ("<p>5 &lt; 10 &amp; rising</p>", "5 < 10 & rising"),
        ("", ""),
    ],
)
def test_html_to_text(html, expected):
    assert report.html_to_text(html) == expected


def test_note_falls_back_to_html_when_plain_missing(db):
    t = db.add_task("Rich", note_html="<p>From <b>HTML</b></p>", note_plain="")
    complete_on(db, t.id, "2026-05-01T10:00:00")
    out = report.generate(
        db, report.ReportOptions(start=date(2026, 1, 1), end=date(2026, 12, 31))
    )
    assert "> From HTML" in out


def test_note_char_limit_truncates(db):
    t = db.add_task("Long", note_plain="x" * 500)
    complete_on(db, t.id, "2026-05-01T10:00:00")
    out = report.generate(
        db,
        report.ReportOptions(
            start=date(2026, 1, 1), end=date(2026, 12, 31), note_char_limit=50
        ),
    )
    assert "…" in out
    assert "x" * 60 not in out


def test_preset_ranges_are_sane():
    today = date(2026, 9, 14)
    presets = dict((name, (s, e)) for name, s, e in report.preset_ranges(today))
    assert presets["This year to date"] == (date(2026, 1, 1), today)
    assert presets["Last 12 months"] == (date(2025, 9, 14), today)
    assert presets["This quarter"] == (date(2026, 7, 1), today)
    assert presets["Last calendar year"] == (date(2025, 1, 1), date(2025, 12, 31))


def test_month_shift_handles_short_months():
    assert report._shift_months(date(2026, 3, 31), -1) == date(2026, 2, 28)
    assert report._shift_months(date(2024, 3, 31), -1) == date(2024, 2, 29)
