from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from analytics import metrics, procrastination, recommendations, scoring
from analytics import service as svc
from database import repositories as repo
from database.db import session_scope
from database.models import StudySession, Task

TODAY = date(2026, 3, 10)
NOW = datetime(2026, 3, 10, 20, 0)


def sess_df(rows):
    cols = ["id", "subject_id", "task_id", "start_time", "end_time", "planned_minutes", "actual_minutes", "active_minutes",
            "idle_minutes", "interruption_count", "session_status", "subject_name", "subject_color", "task_title", "date", "hour"]
    out = []
    for i, r in enumerate(rows):
        st = r["start"]
        out.append({"id": i, "subject_id": r.get("sub", 1), "task_id": None, "start_time": st, "end_time": st + timedelta(minutes=r["actual"]),
                    "planned_minutes": r.get("planned", r["actual"]), "actual_minutes": r["actual"], "active_minutes": r.get("active"),
                    "idle_minutes": r.get("idle"), "interruption_count": r.get("int", 0), "session_status": r.get("status", "Completed"),
                    "subject_name": "S", "subject_color": "#fff", "task_title": "", "date": st.date(), "hour": st.hour})
    df = pd.DataFrame(out, columns=cols)
    df["start_time"] = pd.to_datetime(df["start_time"]); df["end_time"] = pd.to_datetime(df["end_time"])
    return df


def tasks_df(rows):
    cols = ["id", "subject_id", "title", "priority", "status", "deadline", "estimated_minutes", "actual_minutes", "postponement_count",
            "extension_count", "created_at", "completed_at", "subject_name", "subject_color", "description", "user_id"]
    df = pd.DataFrame([{"id": i, "subject_id": 1, "title": r.get("title", f"T{i}"), "priority": "Medium", "status": r["status"],
                        "deadline": r.get("deadline"), "estimated_minutes": r.get("est"), "actual_minutes": r.get("actual", 0),
                        "postponement_count": r.get("post", 0), "extension_count": r.get("ext", 0), "created_at": r.get("created", NOW - timedelta(days=9)),
                        "completed_at": r.get("done"), "subject_name": "S", "subject_color": "#fff", "description": "", "user_id": 1}
                       for i, r in enumerate(rows)], columns=cols)
    for c in ("deadline", "created_at", "completed_at"):
        df[c] = pd.to_datetime(df[c])
    return df


def empty_sessions():
    return sess_df([])


def test_score_none_when_nothing_recorded():
    r = scoring.compute_score(empty_sessions(), tasks_df([]), 120, TODAY, 7, TODAY - timedelta(days=30), NOW)
    assert r.score is None and r.notes


def test_score_is_reproducible_and_bounded():
    s = sess_df([{"start": datetime(2026, 3, 9 - i, 18), "actual": 90} for i in range(5)])
    t = tasks_df([{"status": "Completed", "deadline": NOW - timedelta(days=2), "done": NOW - timedelta(days=3)}])
    a = scoring.compute_score(s, t, 120, TODAY, 7, TODAY - timedelta(days=30), NOW)
    b = scoring.compute_score(s, t, 120, TODAY, 7, TODAY - timedelta(days=30), NOW)
    assert a.score == b.score and 0 <= a.score <= 100


def test_missing_components_are_rescaled_not_zeroed():
    s = sess_df([{"start": datetime(2026, 3, 10 - i, 18), "actual": 120} for i in range(7)])
    r = scoring.compute_score(s, tasks_df([]), 120, TODAY, 7, TODAY - timedelta(days=30), NOW)   # no tasks at all
    tc = next(c for c in r.components if c.key == "task_completion")
    assert not tc.available and r.score == 100                         # perfect study, nothing penalised
    assert sum(c.effective_weight for c in r.components if c.available) == pytest.approx(100)


def test_zero_goal_and_zero_planned_do_not_divide_by_zero():
    s = sess_df([{"start": datetime(2026, 3, 10, 9), "actual": 30, "planned": 0.0}])
    r = scoring.compute_score(s, tasks_df([]), 0, TODAY, 7, TODAY, NOW)
    assert r.score is None or 0 <= r.score <= 100


def test_focus_ratio_tracked_vs_proxy():
    s = sess_df([{"start": datetime(2026, 3, 10, 9), "actual": 20, "active": 15, "idle": 5},
                 {"start": datetime(2026, 3, 10, 11), "actual": 10, "planned": 20}])
    ratio, info = metrics.focus_ratio(s)
    assert info == {"tracked_minutes": 20.0, "proxy_minutes": 10.0}
    assert ratio == pytest.approx((15 + 0.5 * 10) / 30)


def test_task_completion_counts_due_and_completed_only():
    t = tasks_df([{"status": "Completed", "deadline": NOW - timedelta(days=1), "done": NOW - timedelta(days=2)},
                  {"status": "Overdue", "deadline": NOW - timedelta(days=1)},
                  {"status": "Pending", "deadline": NOW + timedelta(days=3)}])        # not due yet: ignored
    rate, info = metrics.task_completion(t, TODAY - timedelta(days=6), TODAY, NOW)
    assert info == {"relevant": 2, "completed": 1} and rate == 0.5


def test_daily_minutes_zero_filled_and_running_excluded():
    s = sess_df([{"start": datetime(2026, 3, 10, 9), "actual": 30}, {"start": datetime(2026, 3, 8, 9), "actual": 45, "status": "Running"}])
    d = metrics.daily_minutes(s, TODAY - timedelta(days=2), TODAY)
    assert list(d.values) == [0.0, 0.0, 30.0]


def test_procrastination_indicators_have_four_part_output():
    t = tasks_df([{"status": "Pending", "deadline": NOW + timedelta(days=2), "post": 3, "ext": 2, "title": "Thesis"}])
    s = sess_df([{"start": datetime(2026, 3, 1 + i, 18), "actual": 10, "planned": 25, "status": "Stopped Early", "int": 3} for i in range(8)])
    inds = procrastination.detect(s, t, 120, TODAY)
    keys = {i.key for i in inds}
    assert {"postponed_tasks", "deadline_extensions", "incomplete_sessions", "interruptions", "plan_vs_actual"} <= keys
    for i in inds:
        assert i.observed and i.data is not None and i.explanation and i.suggestion


def test_no_indicators_for_healthy_history():
    s = sess_df([{"start": datetime(2026, 3, 10 - i, 18), "actual": 45, "planned": 45} for i in range(10)])
    assert procrastination.detect(s, tasks_df([]), 60, TODAY) == []


def test_long_gap_detected():
    days = [1, 2, 3, 4, 9, 10]
    s = sess_df([{"start": datetime(2026, 3, d, 18), "actual": 30} for d in days])
    assert "long_gaps" in {i.key for i in procrastination.detect(s, tasks_df([]), 60, TODAY)}


def test_recommendations_are_data_based_and_dismissable():
    t = tasks_df([{"status": "Overdue", "deadline": NOW - timedelta(days=4), "title": "Lab report"}])
    subs = pd.DataFrame([{"id": 1, "name": "Maths", "color": "#fff", "target_minutes": 200}])
    s = sess_df([{"start": datetime(2026, 3, 10 - i, 18), "actual": 20} for i in range(5)])
    recs = recommendations.generate(s, t, subs, 240, 25, TODAY, TODAY - timedelta(days=20), NOW)
    keys = [r.key for r in recs]
    assert "overdue_tasks" in keys and "lower_goal" in keys
    assert all(r.reason for r in recs)
    assert "Lab report" in next(r for r in recs if r.key == "overdue_tasks").body
    after = recommendations.generate(s, t, subs, 240, 25, TODAY, TODAY - timedelta(days=20), NOW, dismissed={"overdue_tasks"})
    assert "overdue_tasks" not in [r.key for r in after]


def test_no_recommendations_without_data():
    subs = pd.DataFrame(columns=["id", "name", "color", "target_minutes"])
    assert recommendations.generate(empty_sessions(), tasks_df([]), subs, 120, 25, TODAY, TODAY, NOW) == []


def test_persist_daily_uses_stored_records(uid):
    sid = repo.add_subject(uid, "Maths")
    repo.add_manual_session(uid, sid, None, datetime.combine(date.today(), datetime.min.time()) + timedelta(seconds=30), 50)
    snap = svc.load_snapshot(uid)
    svc.persist_daily(snap, days=3)
    daily = repo.list_daily_df(uid)
    assert len(daily) == 3 and daily.iloc[-1]["study_minutes"] == pytest.approx(50.0)
    svc.persist_daily(snap, days=3)                               # idempotent upsert
    assert len(repo.list_daily_df(uid)) == 3
