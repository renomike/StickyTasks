"""Review-season reporting.

Produces a Markdown or plain-text write-up of what happened in a date range.
The generator works off :class:`~stickytasks.db.Database` queries and returns a
string, so it is testable without a GUI and can be piped, saved, or pasted.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Sequence

from .db import Database
from .models import STATUS_COMPLETE, StatusEvent, Task

SCOPE_COMPLETED = "completed"
SCOPE_ACTIVITY = "activity"

FORMAT_MARKDOWN = "markdown"
FORMAT_TEXT = "text"


@dataclass
class ReportOptions:
    start: date
    end: date
    scope: str = SCOPE_COMPLETED
    fmt: str = FORMAT_MARKDOWN
    include_notes: bool = True
    include_history: bool = False
    group_by_project: bool = True
    title: str = "Task Report"
    note_char_limit: int = 0  # 0 = no limit


def html_to_text(value: str) -> str:
    """Flatten note HTML to readable plain text.

    Qt stores notes as a full HTML document.  Rather than pull in a parser, this
    strips the parts that never carry content (style/script blocks), turns block
    boundaries into newlines, notes where images were, and unescapes entities.
    """
    if not value:
        return ""
    text = value
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|h[1-6]|li|tr|blockquote)>", "\n", text)
    text = re.sub(r"(?i)<li\b[^>]*>", "- ", text)
    text = re.sub(r"(?i)<img\b[^>]*>", "[image]", text)
    text = re.sub(r"(?s)<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    lines = [ln.rstrip() for ln in text.splitlines()]
    out: list[str] = []
    for ln in lines:
        if ln.strip() or (out and out[-1].strip()):
            out.append(ln.strip())
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out).strip()


def _fmt_date(value: Optional[date]) -> str:
    return value.isoformat() if value else "-"


def _fmt_dt(value: Optional[datetime]) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else "-"


def _truncate(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _note_text(task: Task, limit: int) -> str:
    body = task.note_plain.strip() or html_to_text(task.note_html)
    return _truncate(body.strip(), limit)


def collect(db: Database, opts: ReportOptions) -> list[Task]:
    if opts.scope == SCOPE_ACTIVITY:
        return db.tasks_active_between(opts.start, opts.end)
    return db.tasks_completed_between(opts.start, opts.end)


def _group(tasks: Sequence[Task], by_project: bool) -> list[tuple[str, list[Task]]]:
    if not by_project:
        return [("", list(tasks))]
    buckets: dict[str, list[Task]] = {}
    for t in tasks:
        buckets.setdefault(t.project.strip() or "(no project)", []).append(t)
    return sorted(buckets.items(), key=lambda kv: kv[0].lower())


def _summary_rows(tasks: Sequence[Task]) -> list[tuple[str, int, int, int, int]]:
    """Per-project (project, total, completed, in work, to do) counts."""
    rows: dict[str, list[int]] = {}
    for t in tasks:
        key = t.project.strip() or "(no project)"
        cell = rows.setdefault(key, [0, 0, 0, 0])
        cell[0] += 1
        if t.status == STATUS_COMPLETE:
            cell[1] += 1
        elif t.status == "In Work":
            cell[2] += 1
        else:
            cell[3] += 1
    return [(k, *v) for k, v in sorted(rows.items(), key=lambda kv: kv[0].lower())]


def generate(db: Database, opts: ReportOptions) -> str:
    tasks = collect(db, opts)
    history = db.events_between(opts.start, opts.end) if opts.include_history else {}
    if opts.fmt == FORMAT_TEXT:
        return _render_text(tasks, history, opts)
    return _render_markdown(tasks, history, opts)


# ---------------------------------------------------------------- markdown
def _render_markdown(
    tasks: Sequence[Task],
    history: dict[int, list[StatusEvent]],
    opts: ReportOptions,
) -> str:
    scope_label = (
        "Tasks completed in this period"
        if opts.scope == SCOPE_COMPLETED
        else "Tasks with activity in this period"
    )
    out: list[str] = []
    out.append(f"# {opts.title}")
    out.append("")
    out.append(f"**Period:** {opts.start.isoformat()} to {opts.end.isoformat()}  ")
    out.append(f"**Scope:** {scope_label}  ")
    out.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    out.append("")

    if not tasks:
        out.append("_No tasks matched this period._")
        return "\n".join(out) + "\n"

    completed = sum(1 for t in tasks if t.status == STATUS_COMPLETE)
    rows = _summary_rows(tasks)
    out.append("## Summary")
    out.append("")
    out.append(f"- **{len(tasks)}** task(s) in scope across **{len(rows)}** project(s)")
    out.append(f"- **{completed}** marked Complete")
    out.append("")
    out.append("| Project | Total | Complete | In Work | To Do |")
    out.append("| --- | ---: | ---: | ---: | ---: |")
    for name, total, done, work, todo in rows:
        out.append(f"| {_md_cell(name)} | {total} | {done} | {work} | {todo} |")
    out.append("")

    out.append("## Detail")
    out.append("")
    for project, group in _group(tasks, opts.group_by_project):
        if opts.group_by_project:
            out.append(f"### {project}")
            out.append("")
        for t in group:
            out.append(f"#### {_md_cell(t.title or '(untitled)')}")
            out.append("")
            facts = [
                f"**Status:** {t.status}",
                f"**Due:** {_fmt_date(t.due_date)}",
                f"**Created:** {_fmt_dt(t.created_at)}",
            ]
            if t.completed_at:
                facts.append(f"**Completed:** {_fmt_dt(t.completed_at)}")
            if not opts.group_by_project and t.project:
                facts.insert(0, f"**Project:** {_md_cell(t.project)}")
            out.append(" · ".join(facts))
            out.append("")

            if opts.include_history and t.id in history:
                out.append("Status history in period:")
                out.append("")
                for ev in history[t.id]:
                    arrow = f"{ev.from_status} → {ev.to_status}" if ev.from_status else f"created as {ev.to_status}"
                    out.append(f"- {_fmt_dt(ev.changed_at)} — {arrow}")
                out.append("")

            if opts.include_notes:
                note = _note_text(t, opts.note_char_limit)
                if note:
                    for line in note.splitlines():
                        out.append(f"> {line}" if line.strip() else ">")
                    out.append("")
    return "\n".join(out).rstrip() + "\n"


def _md_cell(value: str) -> str:
    """Escape the characters that would break a Markdown table cell or heading."""
    return value.replace("|", "\\|").replace("\n", " ").strip()


# ------------------------------------------------------------------- text
def _render_text(
    tasks: Sequence[Task],
    history: dict[int, list[StatusEvent]],
    opts: ReportOptions,
) -> str:
    scope_label = (
        "Tasks completed in this period"
        if opts.scope == SCOPE_COMPLETED
        else "Tasks with activity in this period"
    )
    out: list[str] = []
    out.append(opts.title.upper())
    out.append("=" * len(opts.title))
    out.append(f"Period:    {opts.start.isoformat()} to {opts.end.isoformat()}")
    out.append(f"Scope:     {scope_label}")
    out.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    out.append("")

    if not tasks:
        out.append("No tasks matched this period.")
        return "\n".join(out) + "\n"

    completed = sum(1 for t in tasks if t.status == STATUS_COMPLETE)
    rows = _summary_rows(tasks)
    out.append("SUMMARY")
    out.append("-" * 7)
    out.append(f"{len(tasks)} task(s) in scope across {len(rows)} project(s); {completed} Complete.")
    out.append("")
    width = max([len("Project")] + [len(r[0]) for r in rows])
    out.append(f"{'Project'.ljust(width)}  Total  Done  Work  ToDo")
    out.append(f"{'-' * width}  -----  ----  ----  ----")
    for name, total, done, work, todo in rows:
        out.append(f"{name.ljust(width)}  {total:>5}  {done:>4}  {work:>4}  {todo:>4}")
    out.append("")

    out.append("DETAIL")
    out.append("-" * 6)
    out.append("")
    for project, group in _group(tasks, opts.group_by_project):
        if opts.group_by_project:
            out.append(f"[{project}]")
            out.append("")
        for t in group:
            out.append(f"  * {t.title or '(untitled)'}")
            detail = f"    Status: {t.status}   Due: {_fmt_date(t.due_date)}   Created: {_fmt_dt(t.created_at)}"
            if t.completed_at:
                detail += f"   Completed: {_fmt_dt(t.completed_at)}"
            out.append(detail)
            if not opts.group_by_project and t.project:
                out.append(f"    Project: {t.project}")

            if opts.include_history and t.id in history:
                out.append("    History:")
                for ev in history[t.id]:
                    arrow = f"{ev.from_status} -> {ev.to_status}" if ev.from_status else f"created as {ev.to_status}"
                    out.append(f"      {_fmt_dt(ev.changed_at)}  {arrow}")

            if opts.include_notes:
                note = _note_text(t, opts.note_char_limit)
                if note:
                    out.append("    Notes:")
                    for line in note.splitlines():
                        out.append(f"      {line}" if line.strip() else "")
            out.append("")
    return "\n".join(out).rstrip() + "\n"


# ----------------------------------------------------------- date presets
def preset_ranges(today: Optional[date] = None) -> list[tuple[str, date, date]]:
    """Common review windows, newest-relevant first."""
    t = today or date.today()
    year_start = date(t.year, 1, 1)
    last_year = date(t.year - 1, 1, 1)
    q = (t.month - 1) // 3
    q_start = date(t.year, q * 3 + 1, 1)
    twelve_back = _shift_months(t, -12)
    six_back = _shift_months(t, -6)
    return [
        ("This year to date", year_start, t),
        ("Last 12 months", twelve_back, t),
        ("Last 6 months", six_back, t),
        ("This quarter", q_start, t),
        ("Last calendar year", last_year, date(t.year - 1, 12, 31)),
    ]


def _shift_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, _days_in_month(year, month))
    return date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    import calendar

    return calendar.monthrange(year, month)[1]
