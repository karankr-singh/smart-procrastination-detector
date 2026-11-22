"""Loads records and assembles analytics for the UI and reports."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

from analytics import metrics, procrastination, recommendations, scoring
from database import repositories as repo


@dataclass
class Snapshot:
    user: dict
    settings: dict
    sessions: pd.DataFrame
    tasks: pd.DataFrame
    subjects: pd.DataFrame
    today: date

    @property
    def account_start(self) -> date:
        first = self.user["created_at"].date()
        if not self.sessions.empty:
            first = min(first, self.sessions["date"].min())
        return first


def load_snapshot(user_id: int, today: Optional[date] = None) -> Snapshot:
    return Snapshot(repo.get_user(user_id), repo.get_settings(user_id),
                    repo.list_sessions_df(user_id), repo.list_tasks_df(user_id),
                    repo.list_subjects_df(user_id), today or date.today())


def current_score(snap: Snapshot) -> scoring.ScoreResult:
    return scoring.compute_score(snap.sessions, snap.tasks, snap.user["daily_goal_minutes"], snap.today, 7,
                                 snap.account_start)


def trend(snap: Snapshot, days: int = 14) -> pd.DataFrame:
    start = snap.today - timedelta(days=days - 1)
    df = scoring.rolling_scores(snap.sessions, snap.tasks, snap.user["daily_goal_minutes"], start, snap.today,
                                snap.account_start)
    df["minutes"] = metrics.daily_minutes(snap.sessions, start, snap.today).values
    return df


def indicators(snap: Snapshot):
    return procrastination.detect(snap.sessions, snap.tasks, snap.user["daily_goal_minutes"], snap.today)


def recs(snap: Snapshot, dismissed: Optional[set] = None):
    return recommendations.generate(snap.sessions, snap.tasks, snap.subjects, snap.user["daily_goal_minutes"],
                                    snap.settings["focus_minutes"], snap.today, snap.account_start,
                                    dismissed=dismissed)


def persist_daily(snap: Snapshot, days: int = 30) -> None:
    """Cache per-day aggregates in daily_analytics (rolling 7-day score ending on each day)."""
    rows = []
    for d in metrics.date_range(snap.today - timedelta(days=days - 1), snap.today):
        w = metrics.in_window(snap.sessions, d, d)
        tc, _ = metrics.task_completion(snap.tasks, d, d)
        sc = scoring.compute_score(snap.sessions, snap.tasks, snap.user["daily_goal_minutes"], d, 7, snap.account_start)
        tot = metrics.active_idle_totals(w)
        rows.append({"date": d, "study_minutes": tot["total"], "active_minutes": tot["active"],
                     "task_completion_rate": tc, "productivity_score": sc.score})
    repo.upsert_daily(snap.user["id"], rows)


def period_summary(snap: Snapshot, start: date, end: date) -> dict:
    """Everything a daily/weekly/monthly report needs."""
    s = metrics.in_window(snap.sessions, start, end)
    daily = metrics.daily_minutes(snap.sessions, start, end)
    tc, tc_info = metrics.task_completion(snap.tasks, start, end)
    fr, fr_info = metrics.focus_ratio(s)
    tot = metrics.active_idle_totals(s)
    days = max(1, (end - start).days + 1)
    score = scoring.compute_score(snap.sessions, snap.tasks, snap.user["daily_goal_minutes"], end, min(days, 30),
                                  snap.account_start)
    return {"start": start, "end": end, "days": days, "total_minutes": float(daily.sum()),
            "sessions": len(s), "study_days": int((daily > 0).sum()),
            "avg_per_day": float(daily.sum()) / days, "goal_minutes": snap.user["daily_goal_minutes"] * days,
            "task_completion": tc, "tasks_info": tc_info, "focus_ratio": fr, "focus_info": fr_info,
            "active_idle": tot, "interruptions": metrics.interruption_stats(s),
            "plan_vs_actual": metrics.planned_vs_actual(s), "score": score, "daily": daily,
            "subjects": metrics.subject_summary(snap.sessions, snap.subjects, start, end), "sessions_df": s}
