# Handoff: what the first session decided, and why

StickyTasks was built in a single Claude Code session in a cloud Linux
container. That session's conversation does not travel, so this file records the
decisions behind the code and the state the work was left in. `CLAUDE.md` covers
how to run and change things day to day; this is the background.

## What was asked for

A task tracker in the spirit of MS Sticky Notes: docked to the side of a chosen
monitor, one card per task, background colour driven by due date (red soonest,
green furthest out), with a title, project/category, rich-text notes, pasteable
images, and three statuses. Completed tasks archived rather than deleted, so a
report can be produced at employee review time.

## Decisions taken, and the alternatives rejected

| Decision | Why |
| --- | --- |
| **PySide6 (Qt 6)** rather than Tkinter | Rich text plus clipboard image paste is close to free in Qt's text widget and painful-to-impossible in Tkinter. Qt also handles multi-monitor geometry properly. |
| **One docked list panel** rather than separate floating notes per task | Chosen by the user. Scales past ten tasks, and it is the only layout where a due-date colour ramp reads as a ramp. |
| **Fixed colour bands with user-editable thresholds** rather than a smooth gradient | Chosen by the user. Adjacent due dates stay distinguishable; a continuous blend makes two tasks days apart look identical. |
| **Markdown / plain-text reports** rather than Excel or HTML | Chosen by the user. |
| **SQLite** | Questioned mid-build, then kept: `sqlite3` is in Python's standard library, so nothing is installed and the data is one file in the user's own profile. The storage layer is isolated behind `Database` if that ever needs revisiting. |
| **Archive as a flag, not a delete** | The review-reporting requirement is only possible if finished work persists. |
| **Status history table** | Added beyond the brief: a review report is more useful when it can say when work started, not only that it ended. |
| **Images as content-addressed files on disk** rather than blobs in the database or base64 in the note | Keeps the database small, stores a repeated screenshot once, and lets orphaned images be swept at startup. |

## What is verified, and how

The suite is 132 tests, about 1.5 seconds, no display required. It covers colour
bands and their boundaries, archive semantics and status history, report
generation and date windows, settings validation and repair, the image store,
and the widgets themselves under Qt's offscreen platform.

Verified end to end: a pasted image survives a full application restart;
completed tasks still reach the report after reopening; settings persist.

## What is not verified

- **`ui/winappbar.py`** — reserving screen space via the Windows AppBar API.
  Cannot run outside Windows. Off by default, fails safe to floating.
- **Real Windows rendering.** Fonts, DPI scaling and clipboard image formats all
  differ from a Linux container. Clipboard paste is the likeliest surprise,
  because the tests use synthetic `QImage` objects rather than whatever Windows
  actually puts on the clipboard.
- **Multi-monitor.** Only ever exercised against a single simulated screen.

## Bugs found during the build, and what they teach

1. **Cards overflowed the panel width**, clipping the ✓ and ⋯ buttons off-screen.
   Long note text forced the card wider than the viewport, because a plain
   `QLabel` reports its full text width as its size hint. Fixed with
   `ui/elidedlabel.py`.
2. **`Database.close()` raised on a second call.** Several shutdown paths can
   reach it. Now idempotent.
3. **The empty list area rendered light grey** against the dark panel, leaving
   the empty-state text nearly unreadable. A `QScrollArea`'s viewport does not
   inherit the scroll area's background.

The third is the instructive one: **Qt's offscreen platform did not reproduce
it**, and every screenshot taken until then had enough sample tasks to cover the
area completely. It only appeared when the app was run against a real X server
with an empty database.

The lesson for whoever picks this up: the automated suite is good at logic and
blind to some classes of visual defect. Look at the real window, with no data in
it, before trusting a UI change.

## Suggested first session on a real Windows desktop

1. Add a task due a few days out — confirms the band you will look at most.
2. Paste a screenshot into a note, save, close the app, reopen it. This exercises
   the path most likely to behave differently on Windows.
3. Mark something Complete, then switch the view dropdown to "Completed" —
   confirms archiving rather than deleting.
4. Ctrl+R, pick "This year to date" — confirms reporting.
5. Settings → Placement, try a second monitor.

Leave **Reserve screen space** off until the rest is known good. If it
misbehaves, close the app and delete `%APPDATA%\StickyTasks\settings.json` to
return to floating.

## Deliberately not built

No reminders or notifications, no recurring tasks, no sync or multi-device
support, no sub-tasks, tags or priorities, no global hotkey (Qt has no
cross-platform API for one — the tray icon covers it). These are choices, not
oversights; `README.md` lists them for the user's benefit too.
