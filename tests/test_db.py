from datetime import date

import pytest

from stickytasks.db import Database
from stickytasks.models import (
    STATUS_COMPLETE,
    STATUS_IN_WORK,
    STATUS_TODO,
    Task,
)


def test_add_task_records_creation_event(db):
    t = db.add_task("Write spec", project="Alpha", due_date=date(2026, 10, 1))
    assert t.id is not None
    assert t.title == "Write spec"
    assert t.project == "Alpha"
    assert t.due_date == date(2026, 10, 1)
    assert t.status == STATUS_TODO
    assert t.archived is False

    events = db.status_events(t.id)
    assert len(events) == 1
    assert events[0].from_status is None
    assert events[0].to_status == STATUS_TODO


def test_completing_archives_but_does_not_delete(db):
    t = db.add_task("Ship it")
    done = db.set_status(t.id, STATUS_COMPLETE)

    assert done.status == STATUS_COMPLETE
    assert done.archived is True
    assert done.completed_at is not None

    # Gone from the default panel view...
    assert db.list_tasks() == []
    # ...but still in the database.
    assert len(db.list_tasks(include_archived=True)) == 1
    assert db.get_task(t.id) is not None


def test_reopening_a_completed_task_unarchives_it(db):
    t = db.add_task("Ship it")
    db.set_status(t.id, STATUS_COMPLETE)
    reopened = db.set_status(t.id, STATUS_IN_WORK)

    assert reopened.archived is False
    assert reopened.completed_at is None
    assert [e.to_status for e in db.status_events(t.id)] == [
        STATUS_TODO, STATUS_COMPLETE, STATUS_IN_WORK
    ]


def test_setting_same_status_records_no_duplicate_event(db):
    t = db.add_task("Steady")
    db.set_status(t.id, STATUS_TODO)
    assert len(db.status_events(t.id)) == 1


def test_delete_is_the_only_destructive_path(db):
    t = db.add_task("Temporary")
    db.set_status(t.id, STATUS_COMPLETE)
    db.delete_task(t.id)
    assert db.get_task(t.id) is None
    assert db.status_events(t.id) == []  # cascade removed the history too


def test_update_task_persists_fields_and_routes_status_change(db):
    t = db.add_task("Draft", project="Alpha")
    t.title = "Final draft"
    t.project = "Beta"
    t.due_date = date(2026, 12, 25)
    t.note_html = "<p>hello</p>"
    t.note_plain = "hello"
    t.status = STATUS_IN_WORK

    saved = db.update_task(t)
    assert saved.title == "Final draft"
    assert saved.project == "Beta"
    assert saved.due_date == date(2026, 12, 25)
    assert saved.note_plain == "hello"
    assert saved.status == STATUS_IN_WORK
    # the status change went through the history, not around it
    assert [e.to_status for e in db.status_events(t.id)] == [STATUS_TODO, STATUS_IN_WORK]


def test_update_rejects_unknown_task(db):
    ghost = Task(id=999, title="nope")
    with pytest.raises(LookupError):
        db.update_task(ghost)


def test_set_status_rejects_unknown_status(db):
    t = db.add_task("x")
    with pytest.raises(ValueError):
        db.set_status(t.id, "Blocked")


def test_due_order_puts_undated_last(db):
    db.add_task("no date")
    db.add_task("later", due_date=date(2026, 12, 1))
    db.add_task("sooner", due_date=date(2026, 10, 1))

    assert [t.title for t in db.list_tasks(order="due")] == ["sooner", "later", "no date"]


def test_search_covers_title_project_and_note(db):
    db.add_task("Alpha report", project="Finance")
    db.add_task("Unrelated", project="Ops", note_plain="mentions widgets")

    assert [t.title for t in db.list_tasks(search="alpha")] == ["Alpha report"]
    assert [t.title for t in db.list_tasks(search="finance")] == ["Alpha report"]
    assert [t.title for t in db.list_tasks(search="widgets")] == ["Unrelated"]
    assert db.list_tasks(search="nothing here") == []


def test_status_filter(db):
    db.add_task("a", status=STATUS_TODO)
    db.add_task("b", status=STATUS_IN_WORK)
    assert [t.title for t in db.list_tasks(statuses=[STATUS_IN_WORK])] == ["b"]


def test_counts(db):
    db.add_task("a")
    db.add_task("b", status=STATUS_IN_WORK)
    c = db.add_task("c")
    db.set_status(c.id, STATUS_COMPLETE)

    counts = db.counts()
    assert counts[STATUS_TODO] == 1
    assert counts[STATUS_IN_WORK] == 1
    assert counts["Archived"] == 1


def test_projects_lists_distinct_non_empty(db):
    db.add_task("a", project="Alpha")
    db.add_task("b", project="Alpha")
    db.add_task("c", project="")
    db.add_task("d", project="Beta")
    assert db.projects() == ["Alpha", "Beta"]


def test_add_task_as_complete_is_archived_immediately(db):
    t = db.add_task("Already done", status=STATUS_COMPLETE)
    assert t.archived is True
    assert t.completed_at is not None


def test_referenced_image_names_extracts_filenames(db):
    db.add_task("with image", note_html='<p><img src="abc123.png" /> and <img src=\'d/e.jpg\'></p>')
    assert db.referenced_image_names() == {"abc123.png", "e.jpg"}


def test_schema_migrates_in_place(tmp_path):
    path = tmp_path / "m.db"
    first = Database(path)
    first.add_task("survivor")
    first.close()

    second = Database(path)  # re-open runs migrate() again
    assert [t.title for t in second.list_tasks()] == ["survivor"]
    assert second.conn.execute("PRAGMA user_version").fetchone()[0] >= 1
    second.close()


def test_close_is_idempotent(tmp_path):
    """Several shutdown paths can reach close(); a second call must not raise."""
    database = Database(tmp_path / "c.db")
    database.add_task("x")
    database.close()
    database.close()  # must be a no-op, not an error
    assert database.closed is True


def test_context_manager_closes(tmp_path):
    with Database(tmp_path / "ctx.db") as database:
        database.add_task("x")
    assert database.closed is True
