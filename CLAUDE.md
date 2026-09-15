# StickyTasks — notes for Claude Code

A docked, colour-coded task panel with rich-text notes and review reporting.
Python 3.9+ and PySide6 (Qt 6). Target platform is Windows; the code runs on
macOS and Linux too.

## Run it

```
pip install -r requirements.txt
python run_stickytasks.py
```

On Windows, `StickyTasks.bat` launches it without a console window. If `python`
is not recognised, use `py`.

## Test it

```
python -m pytest          # 151 tests, ~3s, no display needed
python -m pyflakes stickytasks/ tests/ run_stickytasks.py
```

`tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen`, so the UI tests drive real
Qt widgets headlessly. Do not add a mocking layer for Qt — the widget tests are
meant to exercise the real thing.

## Layout

```
stickytasks/
  colors.py      due date -> colour band; contrast-aware text colour
  config.py      settings as JSON, validated and clamped on load
  db.py          SQLite storage, schema migrations, status history
  humanize.py    "overdue by 3 days", "in 2 weeks"
  imagestore.py  content-addressed image files for note attachments
  models.py      Task, StatusEvent
  report.py      Markdown / plain-text report generation
  paths.py       per-OS data directory
  winautostart.py  Windows sign-in registration (Run key)
  app.py         build() wires everything; run() enters the event loop
  ui/            everything Qt
```

**Nothing outside `ui/` imports Qt.** That separation is why the storage,
colour and reporting logic can be tested directly, and it is worth preserving:
if a new rule is about data rather than presentation, it belongs outside `ui/`.

## Rules that matter

- **Completing a task archives it; it is never deleted.** Only
  `Database.delete_task` removes a row, and only the explicit "Delete
  permanently" action calls it. Review reporting depends on this — do not add
  cleanup that drops completed tasks.
- **Every status change is appended to `status_events`.** Route status changes
  through `Database.set_status`, never a bare `UPDATE tasks SET status`.
- **Colour bands are data, not constants.** Users edit them in Settings. Always
  resolve a colour through `colors.band_for` / `colors.color_for` so a custom
  band list is honoured. Exactly one band has `max_days = None`; loaders repair
  a list that is missing it rather than failing.
- **Colours are relative to today**, so the panel re-colours at midnight via a
  timer. Anything caching a colour needs to survive a date change.
- **Note images are referenced by bare filename** and resolved through
  `NoteEdit.loadResource`. Never write an absolute path into note HTML — it
  breaks the moment the data folder moves.
- **Settings preserve unknown keys** (`Settings._extra`) so a file written by a
  newer build is not truncated by an older one.
- **Starting at sign-in is not a setting.** The registry decides it, and Task
  Manager's Startup tab can switch it off without telling the app, so a copy in
  `settings.json` would be free to disagree. Read it through
  `winautostart.is_enabled()` every time it is displayed.

## Qt gotchas already hit here

- A `QScrollArea`'s **viewport is a separate widget** and does not inherit the
  scroll area's background. It is targeted by object name
  (`TaskScrollViewport`) in `ui/theme.py`. A bare `QScrollArea > QWidget`
  selector would also match the scrollbars, because Qt type selectors match
  subclasses.
- **A plain `QLabel` reports its full text width as its size hint**, which
  pushes cards wider than the docked panel and clips the buttons on the far
  side. Use `ElidedLabel` / `WrapLabel` from `ui/elidedlabel.py` for any text
  inside a card.
- **Offscreen rendering does not reproduce every visual bug.** The light-grey
  viewport above was invisible offscreen. For visual work, prefer a real X
  server or a real desktop (see `docs/HANDOFF.md`).
- Icons are **drawn at runtime** in `ui/icons.py`. There are no binary assets;
  keep it that way, and avoid emoji glyphs in buttons — they render as tofu
  where no emoji font is installed.

## Where user data lives

`%APPDATA%\StickyTasks` on Windows; see `paths.py` for other platforms. Override
with the `STICKYTASKS_HOME` environment variable — the tests rely on this.

## Verified on a real Windows desktop

`ui/winappbar.py` (reserving screen space via the Windows AppBar API) has now
been driven on a real desktop: maximised windows do stop at the panel on both
edges, and the reservation is released when the panel hides or quits. Two bugs
came out of that session, both fixed — see the commit "Stop the panel drifting
inwards when it reserves screen space" for the trap, which is that
`availableGeometry()` excludes the panel's own reserved strip.

`winautostart.py` was exercised the same way, with one caveat: a sandboxed shell
can virtualise HKEY_CURRENT_USER, so a registry value written by the app may not
be the one `reg.exe` reads back in such a shell. Check the Run key from a normal
terminal or Task Manager's Startup tab, not from inside a sandbox.
