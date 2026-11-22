"""End-to-end workflow: profile -> subject -> task -> focus session -> analytics -> exports -> deletion."""
import io
import zipfile
from datetime import date, datetime, timedelta

import pandas as pd

import database.db as db
from analytics import service as svc
from database import repositories as repo
from pages.reports import period_bounds
from services import export_service as ex
from services.session_service import SessionManager


def test_full_workflow(uid, tmpdb, fake_clock):
    sid = repo.add_subject(uid, "Algorithms", "#8B7CFF", 120)
    tid = repo.add_task(uid, "Sorting lab", sid, "", "High", datetime.now() + timedelta(days=2), 50)
    m = SessionManager(uid, repo.get_settings(uid), clock=fake_clock)
    m.start(sid, tid, 25)
    fake_clock.advance(minutes=25, seconds=1)
    assert m.tick() == ["phase_complete"]
    db.configure(tmpdb)                                                          # restart
    snap = svc.load_snapshot(uid, today=fake_clock().date())
    assert len(snap.sessions) == 1 and snap.tasks.iloc[0]["actual_minutes"] == 25
    assert snap.tasks.iloc[0]["status"] == "In Progress"
    summ = svc.period_summary(snap, fake_clock().date(), fake_clock().date())
    assert summ["total_minutes"] == 25 and summ["sessions"] == 1
    # exports contain the correct records
    csv = ex.to_csv_bytes(summ["sessions_df"][ex.EXPORT_SESSION_COLS]).decode("utf-8-sig")
    out = pd.read_csv(io.StringIO(csv))
    assert len(out) == 1 and out.iloc[0]["actual_minutes"] == 25 and out.iloc[0]["subject_name"] == "Algorithms"
    pdf = ex.report_pdf(summ, snap.user, "Daily productivity report")
    assert pdf.startswith(b"%PDF") and len(pdf) > 1500
    with zipfile.ZipFile(io.BytesIO(ex.personal_data_zip(uid))) as z:
        assert {"sessions.csv", "tasks.csv", "subjects.csv", "profile.csv", "README.txt"} <= set(z.namelist())
    # delete everything
    repo.delete_all_records(uid)
    assert repo.list_sessions_df(uid, include_running=True).empty and repo.list_tasks_df(uid).empty and repo.list_subjects_df(uid).empty
    assert repo.get_user(uid) is not None
    repo.delete_all_records(uid, include_profile=True)
    assert repo.get_user(uid) is None


def test_period_bounds():
    assert period_bounds("Daily", date(2026, 3, 11)) == (date(2026, 3, 11),) * 2
    assert period_bounds("Weekly", date(2026, 3, 11)) == (date(2026, 3, 9), date(2026, 3, 15))
    assert period_bounds("Monthly", date(2026, 2, 11)) == (date(2026, 2, 1), date(2026, 2, 28))


def test_empty_user_analytics_do_not_crash(uid):
    snap = svc.load_snapshot(uid)
    assert svc.current_score(snap).score is None
    assert svc.indicators(snap) == [] and svc.recs(snap) == []
    summ = svc.period_summary(snap, snap.today, snap.today)
    assert ex.report_pdf(summ, snap.user, "Empty").startswith(b"%PDF")


def test_manual_session_validation(uid):
    import pytest
    from utils.validation import ValidationError
    with pytest.raises(ValidationError):
        repo.add_manual_session(uid, None, None, datetime.now() + timedelta(days=1), 30)
    with pytest.raises(ValidationError):
        repo.add_manual_session(uid, None, None, datetime.now() - timedelta(hours=1), 0)
    with pytest.raises(ValidationError):
        repo.add_manual_session(uid, None, None, datetime.now() - timedelta(hours=1), float("nan"))
