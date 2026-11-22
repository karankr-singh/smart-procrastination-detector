"""Create a clearly-labelled SYNTHETIC demo profile. Nothing here is real activity.

Run:  python scripts/seed_demo.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import repositories as repo  # noqa: E402
from database.db import session_scope  # noqa: E402
from database.models import ActivityEvent, StudySession, Task  # noqa: E402

SUBJECTS = [("Data Structures", "#8B7CFF", 300), ("Linear Algebra", "#3DDBC0", 240), ("Operating Systems", "#FFB86B", 240),
            ("Technical Writing", "#FF6F91", 120), ("Statistics", "#5AB8FF", 180)]
TITLES = ["Problem set", "Lab report", "Reading chapter", "Revision notes", "Mini project", "Quiz prep", "Assignment"]


def seed(username: str = "demo_student", weeks: int = 12, seed_value: int = 42, now: datetime | None = None) -> int:
    rng = np.random.default_rng(seed_value)
    now = now or datetime.now()
    uid = repo.create_user(username, daily_goal_minutes=120, start="17:00", end="21:00")
    with session_scope() as s:
        from database.models import User
        s.get(User, uid).created_at = now - timedelta(weeks=weeks)
    repo.set_settings(uid, {"is_synthetic": True})
    sub_ids = [repo.add_subject(uid, n, c, t) for n, c, t in SUBJECTS]

    drift = 0.45
    with session_scope() as s:
        for w in range(weeks, 0, -1):
            week_start = now - timedelta(weeks=w)
            drift = float(np.clip(drift + rng.normal(0, 0.12), 0.1, 0.9))     # procrastination tendency
            for _ in range(8):
                sid = int(rng.choice(sub_ids))
                created = week_start + timedelta(days=int(rng.integers(0, 7)), hours=int(rng.integers(8, 20)))
                deadline = created + timedelta(days=int(rng.integers(3, 11)), hours=int(rng.integers(0, 12)))
                est = int(rng.choice([45, 60, 90, 120, 180, 240]))
                p = float(np.clip(drift + (0.12 if est >= 180 else 0) + rng.normal(0, 0.1), 0.05, 0.95))
                late = rng.random() < 0.12 + 0.6 * p
                future = deadline > now
                done_at = None
                if not future:
                    done_at = deadline + timedelta(hours=float(rng.uniform(6, 72))) if late else \
                        deadline - timedelta(hours=float(rng.uniform(3, 48)))
                    if late and rng.random() < 0.18:
                        done_at = None                              # never finished
                    elif done_at > now:
                        done_at = now - timedelta(hours=1)
                status = "Completed" if done_at else ("Overdue" if deadline < now else "Pending")
                task = Task(user_id=uid, subject_id=sid, title=f"{rng.choice(TITLES)} {int(rng.integers(1, 9))}",
                            description="Synthetic demo task", priority=str(rng.choice(["Low", "Medium", "High", "Urgent"], p=[.15, .4, .3, .15])),
                            status=status, deadline=deadline, estimated_minutes=est, created_at=created,
                            completed_at=done_at, postponement_count=int(rng.poisson(0.2 + 2.2 * p * late)),
                            extension_count=int(rng.poisson(0.1 + 1.4 * p * late)))
                s.add(task)
                s.flush()
                end_day = done_at or min(now, deadline)
                n_sessions = int(max(1, round(est / 30 * rng.uniform(0.25, 0.7) * (1.25 - 0.5 * p))))
                logged = 0.0
                for _k in range(n_sessions):
                    span = max((end_day - created).total_seconds(), 3600)
                    day = created + timedelta(seconds=float(rng.uniform(0, span)))
                    start = day.replace(hour=int(rng.choice([9, 10, 15, 17, 18, 19, 20])), minute=int(rng.integers(0, 60)), second=0, microsecond=0)
                    if start > now - timedelta(hours=1):
                        continue
                    planned = float(rng.choice([25, 25, 45, 50]))
                    early = rng.random() < 0.08 + 0.55 * p
                    actual = round(planned * float(rng.uniform(0.3, 0.8)), 1) if early else planned
                    inter = int(rng.poisson(0.5 + 3 * p))
                    tracked = (now - start).days <= 35 and rng.random() < 0.7
                    idle_share = float(np.clip(rng.normal(0.08 + 0.35 * p, 0.05), 0.0, 0.8))
                    sess = StudySession(user_id=uid, subject_id=sid, task_id=task.id, start_time=start,
                                        end_time=start + timedelta(minutes=actual), planned_minutes=planned,
                                        actual_minutes=actual, interruption_count=inter,
                                        session_status="Stopped Early" if early else "Completed",
                                        active_minutes=round(actual * (1 - idle_share), 2) if tracked else None,
                                        idle_minutes=round(actual * idle_share, 2) if tracked else None)
                    s.add(sess)
                    s.flush()
                    logged += actual
                    if tracked:
                        s.add(ActivityEvent(session_id=sess.id, event_type="category",
                                            category=str(rng.choice(["Study", "Programming", "Research", "Communication", "Entertainment"],
                                                                    p=[.3, .3, .25, .08, .07])),
                                            duration_seconds=actual * 60, created_at=start))
                task.actual_minutes = round(logged, 1)
                if status == "Pending" and logged > 0:
                    task.status = "In Progress"
    return uid


if __name__ == "__main__":
    import database.db as db
    db.get_engine()
    if any(u["username"] == "demo_student" for u in repo.list_users()):
        print("demo_student already exists – delete it in Settings > Data first.")
    else:
        print(f"Created synthetic demo profile (user id {seed()}).")
