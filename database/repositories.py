"""Data-access layer. All functions validate input, use transactions, and return plain dicts/DataFrames."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable, Optional

import pandas as pd
from sqlalchemy import delete, func, select, update

import config
from database.db import DatabaseError, session_scope
from database.models import (ActivityEvent, DailyAnalytics, StudySession, Subject, Task, User, UserSetting)
from utils import validation as v
from utils.validation import ValidationError

SESSION_COLS = ["id", "user_id", "subject_id", "task_id", "start_time", "end_time", "planned_minutes",
                "actual_minutes", "active_minutes", "idle_minutes", "interruption_count", "session_status"]
TASK_COLS = ["id", "user_id", "subject_id", "title", "description", "priority", "status", "deadline",
             "estimated_minutes", "actual_minutes", "postponement_count", "extension_count", "created_at",
             "completed_at"]
SUBJECT_COLS = ["id", "user_id", "name", "color", "target_minutes", "created_at"]
EVENT_COLS = ["id", "session_id", "event_type", "category", "duration_seconds", "created_at"]
DAILY_COLS = ["id", "user_id", "date", "study_minutes", "active_minutes", "task_completion_rate",
              "productivity_score"]
USER_COLS = ["id", "username", "daily_goal_minutes", "preferred_study_start", "preferred_study_end", "created_at"]


def _d(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def _df(rows: Iterable, cols: list[str]) -> pd.DataFrame:
    return pd.DataFrame([_d(r) for r in rows], columns=cols)


# --------------------------------------------------------------------------- users
def create_user(username: str, daily_goal_minutes: int = 120, start: str = "18:00", end: str = "21:00") -> int:
    username = v.clean_text(username, "Name", max_len=40)
    goal = int(v.validate_minutes(daily_goal_minutes, "Daily goal", minimum=10, maximum=1000))
    start, end = v.validate_hhmm(start, "Study start"), v.validate_hhmm(end, "Study end")
    with session_scope() as s:
        if s.scalar(select(User).where(func.lower(User.username) == username.lower())):
            raise ValidationError("A profile with that name already exists.")
        user = User(username=username, daily_goal_minutes=goal, preferred_study_start=start,
                    preferred_study_end=end)
        s.add(user)
        s.flush()
        return user.id


def get_user(user_id: int) -> Optional[dict]:
    with session_scope() as s:
        u = s.get(User, user_id)
        return _d(u) if u else None


def list_users() -> list[dict]:
    with session_scope() as s:
        return [_d(u) for u in s.scalars(select(User).order_by(User.id))]


def update_user(user_id: int, **fields) -> dict:
    allowed = {"username", "daily_goal_minutes", "preferred_study_start", "preferred_study_end"}
    bad = set(fields) - allowed
    if bad:
        raise ValidationError(f"Can't edit: {', '.join(sorted(bad))}")
    if "username" in fields:
        fields["username"] = v.clean_text(fields["username"], "Name", max_len=40)
    if "daily_goal_minutes" in fields:
        fields["daily_goal_minutes"] = int(v.validate_minutes(fields["daily_goal_minutes"], "Daily goal",
                                                              minimum=10, maximum=1000))
    if "preferred_study_start" in fields:
        v.validate_hhmm(fields["preferred_study_start"], "Study start")
    if "preferred_study_end" in fields:
        v.validate_hhmm(fields["preferred_study_end"], "Study end")
    with session_scope() as s:
        u = s.get(User, user_id)
        if not u:
            raise ValidationError("Profile not found.")
        if "username" in fields:
            clash = s.scalar(select(User).where(func.lower(User.username) == fields["username"].lower(),
                                                User.id != user_id))
            if clash:
                raise ValidationError("A profile with that name already exists.")
        for k, val in fields.items():
            setattr(u, k, val)
        s.flush()
        return _d(u)


# ------------------------------------------------------------------------- settings
def _parse(default, raw: str):
    if isinstance(default, bool):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        try:
            return int(float(raw))
        except ValueError:
            return default
    return raw


def get_settings(user_id: int) -> dict:
    out = dict(config.DEFAULT_SETTINGS)
    with session_scope() as s:
        for row in s.scalars(select(UserSetting).where(UserSetting.user_id == user_id)):
            if row.setting_key in out:
                out[row.setting_key] = _parse(config.DEFAULT_SETTINGS[row.setting_key], row.setting_value)
    return out


def set_setting(user_id: int, key: str, value) -> None:
    if key not in config.DEFAULT_SETTINGS and not key.startswith("dismissed_rec:"):
        raise ValidationError(f"Unknown setting: {key}")
    raw = ("true" if value else "false") if isinstance(value, bool) else str(value)
    with session_scope() as s:
        row = s.scalar(select(UserSetting).where(UserSetting.user_id == user_id, UserSetting.setting_key == key))
        if row:
            row.setting_value = raw
        else:
            s.add(UserSetting(user_id=user_id, setting_key=key, setting_value=raw))


def set_settings(user_id: int, values: dict) -> None:
    for key, value in values.items():
        set_setting(user_id, key, value)


def reset_settings(user_id: int) -> None:
    """Reset preferences to defaults (keeps the synthetic-data flag and dismissed recommendations)."""
    keep = {"is_synthetic"}
    with session_scope() as s:
        s.execute(delete(UserSetting).where(UserSetting.user_id == user_id,
                                            UserSetting.setting_key.in_(set(config.DEFAULT_SETTINGS) - keep)))


def dismiss_recommendation(user_id: int, key: str) -> None:
    set_setting(user_id, f"dismissed_rec:{key}", datetime.now().isoformat(timespec="seconds"))


def dismissed_recommendations(user_id: int) -> set[str]:
    with session_scope() as s:
        rows = s.scalars(select(UserSetting.setting_key).where(
            UserSetting.user_id == user_id, UserSetting.setting_key.like("dismissed_rec:%")))
        return {r.split(":", 1)[1] for r in rows}


def restore_recommendations(user_id: int) -> None:
    with session_scope() as s:
        s.execute(delete(UserSetting).where(UserSetting.user_id == user_id,
                                            UserSetting.setting_key.like("dismissed_rec:%")))


# ------------------------------------------------------------------------- subjects
def add_subject(user_id: int, name: str, color: str = "#8B7CFF", target_minutes: int = 0) -> int:
    name = v.clean_text(name, "Subject name", max_len=60)
    color = v.validate_color(color)
    target = int(v.validate_minutes(target_minutes, "Weekly goal", minimum=0, maximum=10000))
    with session_scope() as s:
        if s.scalar(select(Subject).where(Subject.user_id == user_id, func.lower(Subject.name) == name.lower())):
            raise ValidationError("You already have a subject with that name.")
        sub = Subject(user_id=user_id, name=name, color=color, target_minutes=target)
        s.add(sub)
        s.flush()
        return sub.id


def update_subject(subject_id: int, user_id: int, **fields) -> dict:
    allowed = {"name", "color", "target_minutes"}
    if set(fields) - allowed:
        raise ValidationError("Only name, colour and weekly goal can be edited.")
    if "name" in fields:
        fields["name"] = v.clean_text(fields["name"], "Subject name", max_len=60)
    if "color" in fields:
        fields["color"] = v.validate_color(fields["color"])
    if "target_minutes" in fields:
        fields["target_minutes"] = int(v.validate_minutes(fields["target_minutes"], "Weekly goal",
                                                          minimum=0, maximum=10000))
    with session_scope() as s:
        sub = s.get(Subject, subject_id)
        if not sub or sub.user_id != user_id:
            raise ValidationError("Subject not found.")
        if "name" in fields:
            clash = s.scalar(select(Subject).where(Subject.user_id == user_id, Subject.id != subject_id,
                                                   func.lower(Subject.name) == fields["name"].lower()))
            if clash:
                raise ValidationError("You already have a subject with that name.")
        for k, val in fields.items():
            setattr(sub, k, val)
        s.flush()
        return _d(sub)


def delete_subject(subject_id: int, user_id: int) -> None:
    with session_scope() as s:
        sub = s.get(Subject, subject_id)
        if not sub or sub.user_id != user_id:
            raise ValidationError("Subject not found.")
        s.delete(sub)   # tasks/sessions keep their records; subject_id becomes NULL


def list_subjects_df(user_id: int) -> pd.DataFrame:
    with session_scope() as s:
        return _df(s.scalars(select(Subject).where(Subject.user_id == user_id).order_by(Subject.name)), SUBJECT_COLS)


# ---------------------------------------------------------------------------- tasks
def _check_subject(s, subject_id, user_id):
    if subject_id is not None:
        sub = s.get(Subject, subject_id)
        if not sub or sub.user_id != user_id:
            raise ValidationError("Choose a valid subject.")


def add_task(user_id: int, title: str, subject_id: Optional[int] = None, description: str = "",
             priority: str = "Medium", deadline: Optional[datetime] = None,
             estimated_minutes: Optional[int] = None) -> int:
    title = v.clean_text(title, "Title", max_len=120)
    description = v.clean_text(description, "Description", max_len=2000, required=False)
    priority = v.validate_priority(priority)
    deadline = v.validate_deadline(deadline)
    est = v.validate_minutes(estimated_minutes, "Estimate", minimum=1, maximum=10000, allow_none=True)
    with session_scope() as s:
        _check_subject(s, subject_id, user_id)
        task = Task(user_id=user_id, subject_id=subject_id, title=title, description=description,
                    priority=priority, deadline=deadline, estimated_minutes=int(est) if est else None)
        if deadline and deadline < datetime.now():
            task.status = "Overdue"
        s.add(task)
        s.flush()
        return task.id


def update_task(task_id: int, user_id: int, **fields) -> dict:
    allowed = {"title", "description", "subject_id", "priority", "status", "deadline", "estimated_minutes"}
    if set(fields) - allowed:
        raise ValidationError("That field can't be edited.")
    if "title" in fields:
        fields["title"] = v.clean_text(fields["title"], "Title", max_len=120)
    if "description" in fields:
        fields["description"] = v.clean_text(fields["description"], "Description", max_len=2000, required=False)
    if "priority" in fields:
        v.validate_priority(fields["priority"])
    if "status" in fields:
        v.validate_status(fields["status"])
    if "deadline" in fields:
        v.validate_deadline(fields["deadline"])
    if "estimated_minutes" in fields:
        est = v.validate_minutes(fields["estimated_minutes"], "Estimate", minimum=1, maximum=10000, allow_none=True)
        fields["estimated_minutes"] = int(est) if est else None
    with session_scope() as s:
        t = s.get(Task, task_id)
        if not t or t.user_id != user_id:
            raise ValidationError("Task not found.")
        if "subject_id" in fields:
            _check_subject(s, fields["subject_id"], user_id)
        if "deadline" in fields:
            old, new = t.deadline, fields["deadline"]
            if old and new and new > old:
                t.extension_count += 1          # a deadline moved later counts as an extension
            if t.status == "Overdue" and (new is None or new >= datetime.now()):
                t.status = "Pending"
        for k, val in fields.items():
            setattr(t, k, val)
        if fields.get("status") == "Completed" and not t.completed_at:
            t.completed_at = datetime.now()
        if "status" in fields and fields["status"] != "Completed":
            t.completed_at = None
        s.flush()
        return _d(t)


def complete_task(task_id: int, user_id: int, when: Optional[datetime] = None) -> None:
    with session_scope() as s:
        t = s.get(Task, task_id)
        if not t or t.user_id != user_id:
            raise ValidationError("Task not found.")
        t.status, t.completed_at = "Completed", when or datetime.now()


def reopen_task(task_id: int, user_id: int) -> None:
    update_task(task_id, user_id, status="Pending")
    refresh_overdue(user_id)


def postpone_task(task_id: int, user_id: int, new_deadline: datetime) -> None:
    """Explicit 'postpone': moves the deadline later and counts one postponement."""
    v.validate_deadline(new_deadline, allow_none=False)
    with session_scope() as s:
        t = s.get(Task, task_id)
        if not t or t.user_id != user_id:
            raise ValidationError("Task not found.")
        if t.status == "Completed":
            raise ValidationError("Completed tasks can't be postponed.")
        if t.deadline and new_deadline <= t.deadline:
            raise ValidationError("The new deadline must be later than the current one.")
        t.deadline, t.postponement_count = new_deadline, t.postponement_count + 1
        if t.status == "Overdue" and new_deadline >= datetime.now():
            t.status = "Pending"


def delete_task(task_id: int, user_id: int) -> None:
    with session_scope() as s:
        t = s.get(Task, task_id)
        if not t or t.user_id != user_id:
            raise ValidationError("Task not found.")
        s.delete(t)


def add_task_minutes(s, task_id: Optional[int], minutes: float) -> None:
    if task_id is None or minutes == 0:
        return
    t = s.get(Task, task_id)
    if t:
        t.actual_minutes = max(0.0, (t.actual_minutes or 0.0) + minutes)
        if minutes > 0 and t.status == "Pending":
            t.status = "In Progress"


def refresh_overdue(user_id: int, now: Optional[datetime] = None) -> int:
    now = now or datetime.now()
    with session_scope() as s:
        res = s.execute(update(Task).where(Task.user_id == user_id, Task.status.in_(["Pending", "In Progress"]),
                                           Task.deadline.is_not(None), Task.deadline < now).values(status="Overdue"))
        return res.rowcount or 0


def list_tasks_df(user_id: int) -> pd.DataFrame:
    refresh_overdue(user_id)
    with session_scope() as s:
        df = _df(s.scalars(select(Task).where(Task.user_id == user_id).order_by(Task.id)), TASK_COLS)
        subs = {x.id: (x.name, x.color) for x in s.scalars(select(Subject).where(Subject.user_id == user_id))}
    df["subject_name"] = df["subject_id"].map(lambda i: subs.get(i, ("No subject", "#9AA0C8"))[0]
                                              if pd.notna(i) else "No subject")
    df["subject_color"] = df["subject_id"].map(lambda i: subs.get(i, ("", "#9AA0C8"))[1] if pd.notna(i) else "#9AA0C8")
    for col in ("deadline", "created_at", "completed_at"):
        df[col] = pd.to_datetime(df[col])
    return df


# -------------------------------------------------------------------------- sessions
def start_session(user_id: int, subject_id: Optional[int], task_id: Optional[int], planned_minutes: float,
                  start_time: Optional[datetime] = None) -> int:
    planned = v.validate_minutes(planned_minutes, "Planned duration", minimum=1, maximum=600)
    with session_scope() as s:
        _check_subject(s, subject_id, user_id)
        sess = StudySession(user_id=user_id, subject_id=subject_id, task_id=task_id, planned_minutes=planned,
                            start_time=start_time or datetime.now(), session_status="Running")
        s.add(sess)
        s.flush()
        return sess.id


def heartbeat_session(session_id: int, actual_minutes: float) -> None:
    with session_scope() as s:
        sess = s.get(StudySession, session_id)
        if sess and sess.session_status == "Running":
            sess.actual_minutes = round(actual_minutes, 3)


def finish_session(session_id: int, *, actual_minutes: float, status: str, end_time: Optional[datetime] = None,
                   active_minutes: Optional[float] = None, idle_minutes: Optional[float] = None,
                   interruption_count: int = 0, events: Optional[list[dict]] = None) -> dict:
    if status not in ("Completed", "Stopped Early", "Abandoned"):
        raise ValidationError("Invalid final session status.")
    with session_scope() as s:
        sess = s.get(StudySession, session_id)
        if not sess:
            raise ValidationError("Session not found.")
        sess.end_time = end_time or datetime.now()
        sess.actual_minutes = round(max(0.0, actual_minutes), 3)
        sess.active_minutes, sess.idle_minutes = active_minutes, idle_minutes
        sess.interruption_count = max(0, int(interruption_count))
        sess.session_status = status
        for ev in events or []:
            s.add(ActivityEvent(session_id=sess.id, event_type=ev["event_type"], category=ev.get("category"),
                                duration_seconds=float(ev.get("duration_seconds", 0)),
                                created_at=ev.get("created_at") or datetime.now()))
        add_task_minutes(s, sess.task_id, sess.actual_minutes)
        s.flush()
        return _d(sess)


def delete_empty_session(session_id: int) -> None:
    with session_scope() as s:
        sess = s.get(StudySession, session_id)
        if sess:
            s.delete(sess)


def add_manual_session(user_id: int, subject_id: Optional[int], task_id: Optional[int], start_time: datetime,
                       actual_minutes: float, planned_minutes: Optional[float] = None,
                       interruption_count: int = 0) -> int:
    actual = v.validate_minutes(actual_minutes, "Duration", minimum=1, maximum=1000)
    planned = v.validate_minutes(planned_minutes if planned_minutes else actual, "Planned duration",
                                 minimum=1, maximum=1000)
    if start_time > datetime.now() + timedelta(minutes=1):
        raise ValidationError("A study session can't start in the future.")
    with session_scope() as s:
        _check_subject(s, subject_id, user_id)
        sess = StudySession(user_id=user_id, subject_id=subject_id, task_id=task_id, start_time=start_time,
                            end_time=start_time + timedelta(minutes=actual), planned_minutes=planned,
                            actual_minutes=actual, interruption_count=max(0, int(interruption_count)),
                            session_status="Manual")
        s.add(sess)
        add_task_minutes(s, task_id, actual)
        s.flush()
        return sess.id


def update_session(session_id: int, user_id: int, **fields) -> dict:
    """Manual correction of a stored session (subject, task, start, durations, interruptions)."""
    allowed = {"subject_id", "task_id", "start_time", "actual_minutes", "planned_minutes", "interruption_count"}
    if set(fields) - allowed:
        raise ValidationError("That field can't be edited.")
    if "actual_minutes" in fields:
        fields["actual_minutes"] = v.validate_minutes(fields["actual_minutes"], "Actual duration", maximum=1000)
    if "planned_minutes" in fields:
        fields["planned_minutes"] = v.validate_minutes(fields["planned_minutes"], "Planned duration",
                                                       minimum=1, maximum=1000)
    if "interruption_count" in fields:
        fields["interruption_count"] = int(v.validate_minutes(fields["interruption_count"], "Interruptions",
                                                              maximum=500))
    with session_scope() as s:
        sess = s.get(StudySession, session_id)
        if not sess or sess.user_id != user_id:
            raise ValidationError("Session not found.")
        if sess.session_status == "Running":
            raise ValidationError("Stop the running session before editing it.")
        if "subject_id" in fields:
            _check_subject(s, fields["subject_id"], user_id)
        old_task, old_minutes = sess.task_id, sess.actual_minutes
        for k, val in fields.items():
            setattr(sess, k, val)
        sess.end_time = sess.start_time + timedelta(minutes=sess.actual_minutes)
        if sess.active_minutes is not None:   # keep tracked splits consistent with the corrected total
            sess.active_minutes = min(sess.active_minutes, sess.actual_minutes)
            sess.idle_minutes = max(0.0, sess.actual_minutes - sess.active_minutes)
        add_task_minutes(s, old_task, -old_minutes)
        add_task_minutes(s, sess.task_id, sess.actual_minutes)
        s.flush()
        return _d(sess)


def delete_session(session_id: int, user_id: int) -> None:
    with session_scope() as s:
        sess = s.get(StudySession, session_id)
        if not sess or sess.user_id != user_id:
            raise ValidationError("Session not found.")
        if sess.session_status in ("Completed", "Stopped Early", "Manual", "Abandoned"):
            add_task_minutes(s, sess.task_id, -sess.actual_minutes)
        s.delete(sess)


def abandon_orphaned_sessions(user_id: int) -> int:
    """Sessions left 'Running' by a closed browser tab/app restart are closed as 'Abandoned'
    with the minutes recorded at the last heartbeat."""
    with session_scope() as s:
        rows = list(s.scalars(select(StudySession).where(StudySession.user_id == user_id,
                                                         StudySession.session_status == "Running")))
        for r in rows:
            r.session_status = "Abandoned"
            r.end_time = r.start_time + timedelta(minutes=r.actual_minutes)
        return len(rows)


def list_sessions_df(user_id: int, start: Optional[date] = None, end: Optional[date] = None,
                     include_running: bool = False) -> pd.DataFrame:
    with session_scope() as s:
        q = select(StudySession).where(StudySession.user_id == user_id)
        if not include_running:
            q = q.where(StudySession.session_status != "Running")
        if start:
            q = q.where(StudySession.start_time >= datetime.combine(start, datetime.min.time()))
        if end:
            q = q.where(StudySession.start_time < datetime.combine(end + timedelta(days=1), datetime.min.time()))
        df = _df(s.scalars(q.order_by(StudySession.start_time)), SESSION_COLS)
        subs = {x.id: (x.name, x.color) for x in s.scalars(select(Subject).where(Subject.user_id == user_id))}
        tasks = {x.id: x.title for x in s.scalars(select(Task).where(Task.user_id == user_id))}
    df["start_time"] = pd.to_datetime(df["start_time"])
    df["end_time"] = pd.to_datetime(df["end_time"])
    df["subject_name"] = df["subject_id"].map(lambda i: subs.get(i, ("No subject", ""))[0] if pd.notna(i) else "No subject")
    df["subject_color"] = df["subject_id"].map(lambda i: subs.get(i, ("", "#9AA0C8"))[1] if pd.notna(i) else "#9AA0C8")
    df["task_title"] = df["task_id"].map(lambda i: tasks.get(i, "") if pd.notna(i) else "")
    df["date"] = df["start_time"].dt.date
    df["hour"] = df["start_time"].dt.hour
    return df


# --------------------------------------------------------------------------- events
def list_events_df(user_id: int) -> pd.DataFrame:
    with session_scope() as s:
        q = (select(ActivityEvent).join(StudySession, ActivityEvent.session_id == StudySession.id)
             .where(StudySession.user_id == user_id).order_by(ActivityEvent.id))
        return _df(s.scalars(q), EVENT_COLS)


def delete_activity_events(user_id: int) -> int:
    """Delete recorded activity (events) and the tracked active/idle split for the user's sessions."""
    with session_scope() as s:
        ids = list(s.scalars(select(StudySession.id).where(StudySession.user_id == user_id)))
        n = s.execute(delete(ActivityEvent).where(ActivityEvent.session_id.in_(ids))).rowcount if ids else 0
        s.execute(update(StudySession).where(StudySession.user_id == user_id)
                  .values(active_minutes=None, idle_minutes=None))
        return n or 0


# -------------------------------------------------------------------- daily analytics
def upsert_daily(user_id: int, rows: list[dict]) -> None:
    with session_scope() as s:
        for r in rows:
            existing = s.scalar(select(DailyAnalytics).where(DailyAnalytics.user_id == user_id,
                                                             DailyAnalytics.date == r["date"]))
            if existing:
                for k in ("study_minutes", "active_minutes", "task_completion_rate", "productivity_score"):
                    setattr(existing, k, r.get(k))
            else:
                s.add(DailyAnalytics(user_id=user_id, date=r["date"], study_minutes=r.get("study_minutes", 0.0),
                                     active_minutes=r.get("active_minutes"),
                                     task_completion_rate=r.get("task_completion_rate"),
                                     productivity_score=r.get("productivity_score")))


def list_daily_df(user_id: int) -> pd.DataFrame:
    with session_scope() as s:
        return _df(s.scalars(select(DailyAnalytics).where(DailyAnalytics.user_id == user_id)
                             .order_by(DailyAnalytics.date)), DAILY_COLS)


# ------------------------------------------------------------------------ bulk delete
def delete_all_records(user_id: int, include_profile: bool = False) -> None:
    """Delete every personal record (sessions, events, tasks, subjects, analytics, dismissals, consent)."""
    with session_scope() as s:
        ids = list(s.scalars(select(StudySession.id).where(StudySession.user_id == user_id)))
        if ids:
            s.execute(delete(ActivityEvent).where(ActivityEvent.session_id.in_(ids)))
        for model in (StudySession, Task, Subject, DailyAnalytics):
            s.execute(delete(model).where(model.user_id == user_id))
        s.execute(delete(UserSetting).where(UserSetting.user_id == user_id,
                                            UserSetting.setting_key.like("dismissed_rec:%")))
        s.execute(delete(UserSetting).where(UserSetting.user_id == user_id,
                                            UserSetting.setting_key.in_(["tracking_consent", "tracking_consent_at",
                                                                         "track_idle", "track_apps", "is_synthetic"])))
        if include_profile:
            u = s.get(User, user_id)
            if u:
                s.delete(u)
