from datetime import datetime, timedelta

import pytest

from database import repositories as repo
from utils.validation import ValidationError


def test_task_lifecycle(uid):
    sid = repo.add_subject(uid, "Maths")
    tid = repo.add_task(uid, "Problem set", sid, priority="High", deadline=datetime.now() + timedelta(days=2), estimated_minutes=60)
    df = repo.list_tasks_df(uid)
    assert df.iloc[0]["status"] == "Pending" and df.iloc[0]["subject_name"] == "Maths"
    repo.update_task(tid, uid, title="Problem set 2", priority="Urgent")
    assert repo.list_tasks_df(uid).iloc[0]["title"] == "Problem set 2"
    repo.complete_task(tid, uid)
    row = repo.list_tasks_df(uid).iloc[0]
    assert row["status"] == "Completed" and row["completed_at"] is not None
    repo.reopen_task(tid, uid)
    assert repo.list_tasks_df(uid).iloc[0]["status"] == "Pending"
    repo.delete_task(tid, uid)
    assert repo.list_tasks_df(uid).empty


def test_overdue_detection(uid):
    repo.add_task(uid, "Late", deadline=datetime.now() - timedelta(days=1))
    repo.add_task(uid, "Fine", deadline=datetime.now() + timedelta(days=1))
    st = dict(zip(*[repo.list_tasks_df(uid)[c] for c in ("title", "status")]))
    assert st == {"Late": "Overdue", "Fine": "Pending"}


def test_postpone_counts_and_clears_overdue(uid):
    tid = repo.add_task(uid, "Essay", deadline=datetime.now() - timedelta(hours=2))
    repo.postpone_task(tid, uid, datetime.now() + timedelta(days=2))
    r = repo.list_tasks_df(uid).iloc[0]
    assert r["postponement_count"] == 1 and r["status"] == "Pending"
    with pytest.raises(ValidationError):
        repo.postpone_task(tid, uid, datetime.now())          # not later than the current deadline


def test_extension_counted_only_when_later(uid):
    d = datetime.now() + timedelta(days=3)
    tid = repo.add_task(uid, "Report", deadline=d)
    repo.update_task(tid, uid, deadline=d + timedelta(days=1))
    repo.update_task(tid, uid, deadline=d - timedelta(days=1))
    assert repo.list_tasks_df(uid).iloc[0]["extension_count"] == 1


def test_cannot_touch_other_users_tasks(uid):
    other = repo.create_user("Other")
    tid = repo.add_task(uid, "Mine")
    with pytest.raises(ValidationError):
        repo.update_task(tid, other, title="hack")
    with pytest.raises(ValidationError):
        repo.delete_task(tid, other)


def test_task_minutes_follow_sessions(uid):
    tid = repo.add_task(uid, "Study")
    sid = repo.add_manual_session(uid, None, tid, datetime.now() - timedelta(hours=2), 40)
    r = repo.list_tasks_df(uid).iloc[0]
    assert r["actual_minutes"] == 40 and r["status"] == "In Progress"
    repo.update_session(sid, uid, actual_minutes=25)
    assert repo.list_tasks_df(uid).iloc[0]["actual_minutes"] == 25
    repo.delete_session(sid, uid)
    assert repo.list_tasks_df(uid).iloc[0]["actual_minutes"] == 0
