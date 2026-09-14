import os
import sys
from pathlib import Path

import pytest

# The UI tests drive real Qt widgets.  Qt's offscreen platform plugin renders
# them into memory, so the whole suite runs headless with no display server.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("STICKYTASKS_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def db(tmp_path):
    from stickytasks.db import Database

    database = Database(tmp_path / "test.db")
    yield database
    database.close()
