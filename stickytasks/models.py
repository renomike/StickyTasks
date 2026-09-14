"""Plain data objects shared by the storage layer and the UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

STATUS_TODO = "To Do"
STATUS_IN_WORK = "In Work"
STATUS_COMPLETE = "Complete"
STATUSES = (STATUS_TODO, STATUS_IN_WORK, STATUS_COMPLETE)

ACTIVE_STATUSES = (STATUS_TODO, STATUS_IN_WORK)


def parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def fmt_date(value: Optional[date]) -> Optional[str]:
    return value.isoformat() if value else None


def fmt_datetime(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat(timespec="seconds") if value else None


def now() -> datetime:
    """Local wall-clock time.

    Deliberately local rather than UTC: every date in this app (due dates,
    "completed this quarter") is something the user reasons about in their own
    timezone, and a personal desktop app gains nothing from UTC storage.
    """
    return datetime.now().replace(microsecond=0)


@dataclass
class Task:
    id: Optional[int] = None
    title: str = ""
    project: str = ""
    due_date: Optional[date] = None
    status: str = STATUS_TODO
    note_html: str = ""
    note_plain: str = ""
    archived: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    sort_order: float = 0.0

    @property
    def is_complete(self) -> bool:
        return self.status == STATUS_COMPLETE

    @classmethod
    def from_row(cls, row) -> "Task":
        return cls(
            id=row["id"],
            title=row["title"],
            project=row["project"] or "",
            due_date=parse_date(row["due_date"]),
            status=row["status"],
            note_html=row["note_html"] or "",
            note_plain=row["note_plain"] or "",
            archived=bool(row["archived"]),
            created_at=parse_datetime(row["created_at"]),
            updated_at=parse_datetime(row["updated_at"]),
            completed_at=parse_datetime(row["completed_at"]),
            sort_order=row["sort_order"] if row["sort_order"] is not None else 0.0,
        )


@dataclass
class StatusEvent:
    id: Optional[int] = None
    task_id: int = 0
    from_status: Optional[str] = None
    to_status: str = STATUS_TODO
    changed_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> "StatusEvent":
        return cls(
            id=row["id"],
            task_id=row["task_id"],
            from_status=row["from_status"],
            to_status=row["to_status"],
            changed_at=parse_datetime(row["changed_at"]),
        )
