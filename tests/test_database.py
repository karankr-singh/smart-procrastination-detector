import sqlite3

import pytest
from sqlalchemy import text

import database.db as db
from database import repositories as repo
from database.models import Task
from utils.validation import ValidationError


def test_schema_and_version(tmpdb):
    con = sqlite3.connect(tmpdb)
    tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    assert {"users", "subjects", "tasks", "study_sessions", "activity_events", "daily_analytics", "user_settings"} <= tables
    assert con.execute("pragma user_version").fetchone()[0] == db.SCHEMA_VERSION


def test_indexes_exist(tmpdb):
    con = sqlite3.connect(tmpdb)
    idx = {r[0] for r in con.execute("select name from sqlite_master where type='index'")}
    assert "ix_sessions_user_start" in idx and "ix_tasks_deadline" in idx


def test_foreign_keys_enforced(uid):
    with pytest.raises(db.DatabaseError):
        with db.session_scope() as s:
            s.add(Task(user_id=9999, title="x"))


def test_check_constraint_rejects_bad_priority(uid):
    with pytest.raises(db.DatabaseError):
        with db.session_scope() as s:
            s.add(Task(user_id=uid, title="x", priority="Nope"))


def test_transaction_rolls_back(uid):
    with pytest.raises(RuntimeError):
        with db.session_scope() as s:
            s.add(Task(user_id=uid, title="temp"))
            s.flush()
            raise RuntimeError("boom")
    assert repo.list_tasks_df(uid).empty


def test_validation_rejects_bad_input(uid):
    with pytest.raises(ValidationError): repo.create_user("")
    with pytest.raises(ValidationError): repo.create_user("x" * 41)
    with pytest.raises(ValidationError): repo.create_user("Bad", daily_goal_minutes=-5)
    with pytest.raises(ValidationError): repo.add_subject(uid, "Math", color="red")
    with pytest.raises(ValidationError): repo.add_task(uid, "  ")
    with pytest.raises(ValidationError): repo.add_task(uid, "t", priority="Critical")
    with pytest.raises(ValidationError): repo.add_task(uid, "t", estimated_minutes="abc")
    with pytest.raises(ValidationError): repo.add_task(uid, "t", subject_id=12345)


def test_duplicate_names_rejected(uid):
    repo.add_subject(uid, "Maths")
    with pytest.raises(ValidationError):
        repo.add_subject(uid, "maths")
    with pytest.raises(ValidationError):
        repo.create_user("tester")


def test_persistence_after_reconnect(tmpdb, uid):
    repo.add_subject(uid, "Physics", "#3DDBC0", 90)
    db.configure(tmpdb)   # simulates an app restart
    subs = repo.list_subjects_df(uid)
    assert list(subs["name"]) == ["Physics"] and subs.iloc[0]["target_minutes"] == 90


def test_delete_subject_keeps_tasks(uid):
    sid = repo.add_subject(uid, "Chem")
    tid = repo.add_task(uid, "Lab", sid)
    repo.delete_subject(sid, uid)
    t = repo.list_tasks_df(uid)
    assert len(t) == 1 and t.iloc[0]["subject_name"] == "No subject" and t.iloc[0]["id"] == tid


def test_backup_is_valid_database(uid, tmp_path):
    repo.add_subject(uid, "Bio")
    path = db.backup_database(tmp_path / "bk")
    con = sqlite3.connect(path)
    assert con.execute("select count(*) from subjects").fetchone()[0] == 1


def test_settings_defaults_and_roundtrip(uid):
    assert repo.get_settings(uid)["tracking_consent"] is False
    repo.set_setting(uid, "focus_minutes", 40)
    repo.set_setting(uid, "notify_sound", False)
    s = repo.get_settings(uid)
    assert s["focus_minutes"] == 40 and s["notify_sound"] is False
    with pytest.raises(ValidationError):
        repo.set_setting(uid, "not_a_setting", 1)
    repo.reset_settings(uid)
    assert repo.get_settings(uid)["focus_minutes"] == 25
