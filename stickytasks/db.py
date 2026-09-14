"""SQLite storage for tasks, their notes and their status history.

Design notes
------------
* Completing a task sets ``archived = 1`` rather than deleting the row.  Nothing
  in this module ever removes a task except :meth:`Database.delete_task`, which
  is only reachable from an explicit "Delete" action in the UI.
* Every status change is appended to ``status_events``.  That history is what
  makes the review report able to say when work started, not just that it ended.
* Schema changes go through :data:`MIGRATIONS`, keyed on ``PRAGMA user_version``,
  so an existing database upgrades in place instead of being rebuilt.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Sequence

from .models import (
    STATUS_COMPLETE,
    STATUSES,
    StatusEvent,
    Task,
    fmt_date,
    fmt_datetime,
    now,
)

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL DEFAULT '',
    project      TEXT    NOT NULL DEFAULT '',
    due_date     TEXT,
    status       TEXT    NOT NULL DEFAULT 'To Do',
    note_html    TEXT    NOT NULL DEFAULT '',
    note_plain   TEXT    NOT NULL DEFAULT '',
    archived     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL,
    completed_at TEXT,
    sort_order   REAL    NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS status_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status   TEXT NOT NULL,
    changed_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_archived  ON tasks(archived);
CREATE INDEX IF NOT EXISTS idx_tasks_due       ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_project   ON tasks(project);
CREATE INDEX IF NOT EXISTS idx_events_task     ON status_events(task_id);
"""

# user_version -> list of statements taking the schema to that version.
MIGRATIONS: dict[int, list[str]] = {
    1: [SCHEMA_V1],
}
LATEST_VERSION = max(MIGRATIONS)


class Database:
    """A connection to one StickyTasks database file."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self._closed = False
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.migrate()

    # -- schema ---------------------------------------------------------
    def migrate(self) -> None:
        current = self.conn.execute("PRAGMA user_version").fetchone()[0]
        for version in sorted(MIGRATIONS):
            if version > current:
                for stmt in MIGRATIONS[version]:
                    self.conn.executescript(stmt)
                self.conn.execute(f"PRAGMA user_version = {version}")
        self.conn.commit()

    def close(self) -> None:
        """Commit and close.  Safe to call more than once.

        Shutdown can reach here by several paths at once — the window's close
        handler, the ``with`` block, and the ``finally`` in :func:`app.run` —
        and a second close must not raise.
        """
        if self._closed:
            return
        self._closed = True
        try:
            self.conn.commit()
        except sqlite3.Error:
            pass
        finally:
            try:
                self.conn.close()
            except sqlite3.Error:
                pass

    @property
    def closed(self) -> bool:
        return self._closed

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- create / update ------------------------------------------------
    def add_task(
        self,
        title: str,
        project: str = "",
        due_date: Optional[date] = None,
        status: str = "To Do",
        note_html: str = "",
        note_plain: str = "",
    ) -> Task:
        status = status if status in STATUSES else "To Do"
        ts = now()
        stamp = fmt_datetime(ts)
        completed = stamp if status == STATUS_COMPLETE else None
        archived = 1 if status == STATUS_COMPLETE else 0
        order = self._next_sort_order()
        cur = self.conn.execute(
            """INSERT INTO tasks
               (title, project, due_date, status, note_html, note_plain,
                archived, created_at, updated_at, completed_at, sort_order)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                title.strip(), project.strip(), fmt_date(due_date), status,
                note_html, note_plain, archived, stamp, stamp, completed, order,
            ),
        )
        task_id = int(cur.lastrowid)
        self._record_event(task_id, None, status, ts)
        self.conn.commit()
        return self.get_task(task_id)  # type: ignore[return-value]

    def update_task(self, task: Task) -> Task:
        """Persist a task's editable fields.

        Status transitions still go through :meth:`set_status` internally so the
        history and archive flag stay consistent no matter which path the UI
        took to change them.
        """
        if task.id is None:
            raise ValueError("update_task requires a task with an id")
        existing = self.get_task(task.id)
        if existing is None:
            raise LookupError(f"task {task.id} does not exist")

        ts = now()
        self.conn.execute(
            """UPDATE tasks
               SET title = ?, project = ?, due_date = ?, note_html = ?,
                   note_plain = ?, updated_at = ?
               WHERE id = ?""",
            (
                task.title.strip(), task.project.strip(), fmt_date(task.due_date),
                task.note_html, task.note_plain, fmt_datetime(ts), task.id,
            ),
        )
        self.conn.commit()
        if task.status != existing.status:
            self.set_status(task.id, task.status, when=ts)
        return self.get_task(task.id)  # type: ignore[return-value]

    def set_status(self, task_id: int, status: str, when: Optional[datetime] = None) -> Optional[Task]:
        """Move a task to ``status``, archiving it when it becomes Complete.

        Moving a task *out* of Complete un-archives it and clears its completion
        timestamp, so a task re-opened after being finished behaves like an
        ordinary open task again.
        """
        if status not in STATUSES:
            raise ValueError(f"unknown status: {status!r}")
        existing = self.get_task(task_id)
        if existing is None:
            return None
        if existing.status == status:
            return existing

        ts = when or now()
        stamp = fmt_datetime(ts)
        if status == STATUS_COMPLETE:
            self.conn.execute(
                "UPDATE tasks SET status=?, archived=1, completed_at=?, updated_at=? WHERE id=?",
                (status, stamp, stamp, task_id),
            )
        else:
            self.conn.execute(
                "UPDATE tasks SET status=?, archived=0, completed_at=NULL, updated_at=? WHERE id=?",
                (status, stamp, task_id),
            )
        self._record_event(task_id, existing.status, status, ts)
        self.conn.commit()
        return self.get_task(task_id)

    def set_archived(self, task_id: int, archived: bool) -> Optional[Task]:
        """Hide or unhide a task without changing its status."""
        self.conn.execute(
            "UPDATE tasks SET archived=?, updated_at=? WHERE id=?",
            (1 if archived else 0, fmt_datetime(now()), task_id),
        )
        self.conn.commit()
        return self.get_task(task_id)

    def set_sort_order(self, task_id: int, order: float) -> None:
        self.conn.execute("UPDATE tasks SET sort_order=? WHERE id=?", (order, task_id))
        self.conn.commit()

    def delete_task(self, task_id: int) -> None:
        """Permanently remove a task and its history.  The only destructive call."""
        self.conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        self.conn.commit()

    # -- read -----------------------------------------------------------
    def get_task(self, task_id: int) -> Optional[Task]:
        row = self.conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return Task.from_row(row) if row else None

    def list_tasks(
        self,
        include_archived: bool = False,
        statuses: Optional[Sequence[str]] = None,
        project: Optional[str] = None,
        search: Optional[str] = None,
        order: str = "due",
    ) -> list[Task]:
        """Return tasks matching the given filters.

        ``order="due"`` sorts soonest-due first with undated tasks last, which
        matches the colour ramp in the panel: red at the top, green below,
        undated at the bottom.
        """
        clauses: list[str] = []
        params: list = []
        if not include_archived:
            clauses.append("archived = 0")
        if statuses:
            clauses.append("status IN (%s)" % ",".join("?" * len(statuses)))
            params.extend(statuses)
        if project:
            clauses.append("project = ?")
            params.append(project)
        if search:
            needle = f"%{search.strip().lower()}%"
            clauses.append(
                "(lower(title) LIKE ? OR lower(project) LIKE ? OR lower(note_plain) LIKE ?)"
            )
            params.extend([needle, needle, needle])

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        if order == "due":
            order_sql = "ORDER BY due_date IS NULL, due_date ASC, sort_order ASC, id ASC"
        elif order == "project":
            order_sql = "ORDER BY project COLLATE NOCASE, due_date IS NULL, due_date ASC, id ASC"
        elif order == "created":
            order_sql = "ORDER BY created_at DESC, id DESC"
        elif order == "manual":
            order_sql = "ORDER BY sort_order ASC, id ASC"
        else:
            order_sql = "ORDER BY id ASC"

        rows = self.conn.execute(f"SELECT * FROM tasks {where} {order_sql}", params).fetchall()
        return [Task.from_row(r) for r in rows]

    def projects(self, include_archived: bool = True) -> list[str]:
        sql = "SELECT DISTINCT project FROM tasks WHERE project <> ''"
        if not include_archived:
            sql += " AND archived = 0"
        sql += " ORDER BY project COLLATE NOCASE"
        return [r[0] for r in self.conn.execute(sql).fetchall()]

    def status_events(self, task_id: int) -> list[StatusEvent]:
        rows = self.conn.execute(
            "SELECT * FROM status_events WHERE task_id=? ORDER BY changed_at ASC, id ASC",
            (task_id,),
        ).fetchall()
        return [StatusEvent.from_row(r) for r in rows]

    def counts(self) -> dict[str, int]:
        """Open-task counts per status, plus the archived total."""
        result = {s: 0 for s in STATUSES}
        for row in self.conn.execute(
            "SELECT status, COUNT(*) c FROM tasks WHERE archived=0 GROUP BY status"
        ):
            result[row["status"]] = row["c"]
        result["Archived"] = self.conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE archived=1"
        ).fetchone()[0]
        return result

    # -- reporting ------------------------------------------------------
    def tasks_completed_between(self, start: date, end: date) -> list[Task]:
        """Tasks whose completion timestamp falls in ``[start, end]`` inclusive."""
        rows = self.conn.execute(
            """SELECT * FROM tasks
               WHERE completed_at IS NOT NULL
                 AND date(completed_at) BETWEEN ? AND ?
               ORDER BY project COLLATE NOCASE, completed_at ASC""",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [Task.from_row(r) for r in rows]

    def tasks_active_between(self, start: date, end: date) -> list[Task]:
        """Tasks with any activity in the window.

        "Activity" means created, completed, or a recorded status change inside
        the range.  This is the wider net used for "everything I touched", as
        opposed to "everything I finished".
        """
        rows = self.conn.execute(
            """SELECT DISTINCT t.* FROM tasks t
               LEFT JOIN status_events e ON e.task_id = t.id
               WHERE date(t.created_at) BETWEEN ? AND ?
                  OR (t.completed_at IS NOT NULL AND date(t.completed_at) BETWEEN ? AND ?)
                  OR date(e.changed_at) BETWEEN ? AND ?
               ORDER BY t.project COLLATE NOCASE, t.due_date IS NULL, t.due_date ASC, t.id ASC""",
            (start.isoformat(), end.isoformat()) * 3,
        ).fetchall()
        return [Task.from_row(r) for r in rows]

    def events_between(self, start: date, end: date) -> dict[int, list[StatusEvent]]:
        rows = self.conn.execute(
            """SELECT * FROM status_events
               WHERE date(changed_at) BETWEEN ? AND ?
               ORDER BY changed_at ASC, id ASC""",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        grouped: dict[int, list[StatusEvent]] = {}
        for r in rows:
            grouped.setdefault(r["task_id"], []).append(StatusEvent.from_row(r))
        return grouped

    def referenced_image_names(self) -> set[str]:
        """Every image filename mentioned by any note, for orphan cleanup."""
        import re

        pattern = re.compile(r'src\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
        names: set[str] = set()
        for (html,) in self.conn.execute("SELECT note_html FROM tasks WHERE note_html <> ''"):
            for match in pattern.findall(html or ""):
                names.add(Path(match.replace("\\", "/")).name)
        return names

    # -- internals ------------------------------------------------------
    def _record_event(
        self, task_id: int, from_status: Optional[str], to_status: str, when: datetime
    ) -> None:
        self.conn.execute(
            "INSERT INTO status_events (task_id, from_status, to_status, changed_at) VALUES (?,?,?,?)",
            (task_id, from_status, to_status, fmt_datetime(when)),
        )

    def _next_sort_order(self) -> float:
        row = self.conn.execute("SELECT COALESCE(MAX(sort_order), 0) FROM tasks").fetchone()
        return float(row[0]) + 1.0
