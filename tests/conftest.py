import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database.db as db  # noqa: E402
from database import repositories as repo  # noqa: E402


@pytest.fixture()
def tmpdb(tmp_path):
    db.configure(tmp_path / "test.sqlite3")
    yield tmp_path / "test.sqlite3"


@pytest.fixture()
def uid(tmpdb):
    return repo.create_user("Tester", 120)


@pytest.fixture()
def fake_clock():
    class Clock:
        def __init__(self):
            self.t = datetime(2026, 3, 2, 10, 0, 0)
        def __call__(self):
            return self.t
        def advance(self, **kw):
            self.t += timedelta(**kw)
    return Clock()
