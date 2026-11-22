"""Core metrics computed from stored records only. Pure functions over DataFrames; no database access."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd


def date_range(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def valid_sessions(sessions: pd.DataFrame) -> pd.DataFrame:
    """Sessions that actually happened (not running, more than zero minutes)."""
    if sessions.empty:
        return sessions
    return sessions[(sessions["session_status"] != "Running") & (sessions["actual_minutes"] > 0)]


def in_window(sessions: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    s = valid_sessions(sessions)
    if s.empty:
        return s
    return s[(s["date"] >= start) & (s["date"] <= end)]


def daily_minutes(sessions: pd.DataFrame, start: date, end: date) -> pd.Series:
    """Study minutes per calendar day, zero-filled for days without sessions."""
    days = date_range(start, end)
    s = in_window(sessions, start, end)
    grouped = s.groupby("date")["actual_minutes"].sum() if not s.empty else pd.Series(dtype=float)
    return pd.Series([float(grouped.get(d, 0.0)) for d in days], index=days, name="minutes")


def tracked_mask(s: pd.DataFrame) -> pd.Series:
    return s["active_minutes"].notna() & s["idle_minutes"].notna() & ((s["active_minutes"] + s["idle_minutes"]) > 0)


def focus_ratio(s: pd.DataFrame) -> tuple[Optional[float], dict]:
    """Share of session time spent focused, in 0..1.

    * Tracked sessions (idle detection on): active / (active + idle).
    * Untracked sessions: a proxy, min(actual / planned, 1) – i.e. how much of the planned time was kept.
    Both are weighted by minutes. Returns (ratio or None, {'tracked_minutes', 'proxy_minutes'}).
    """
    s = valid_sessions(s)
    if s.empty:
        return None, {"tracked_minutes": 0.0, "proxy_minutes": 0.0}
    mask = tracked_mask(s)
    t, u = s[mask], s[~mask]
    t_total = float((t["active_minutes"] + t["idle_minutes"]).sum())
    t_active = float(t["active_minutes"].sum())
    proxy = np.minimum(u["actual_minutes"] / u["planned_minutes"].clip(lower=1e-9), 1.0)
    u_total = float(u["actual_minutes"].sum())
    u_good = float((proxy * u["actual_minutes"]).sum())
    denom = t_total + u_total
    return (None if denom <= 0 else (t_active + u_good) / denom), {"tracked_minutes": t_total, "proxy_minutes": u_total}


def task_completion(tasks: pd.DataFrame, start: date, end: date, now: Optional[datetime] = None) -> tuple[Optional[float], dict]:
    """Completed / relevant tasks in the window. Relevant = deadline fell in the window (and has passed)
    or the task was completed in the window."""
    if tasks.empty:
        return None, {"relevant": 0, "completed": 0}
    now = now or datetime.now()
    s_dt, e_dt = datetime.combine(start, datetime.min.time()), datetime.combine(end + timedelta(days=1), datetime.min.time())
    due = tasks["deadline"].notna() & (tasks["deadline"] >= s_dt) & (tasks["deadline"] < e_dt) & (tasks["deadline"] <= now)
    done = tasks["completed_at"].notna() & (tasks["completed_at"] >= s_dt) & (tasks["completed_at"] < e_dt)
    relevant = tasks[due | done]
    if relevant.empty:
        return None, {"relevant": 0, "completed": 0}
    completed = int((relevant["status"] == "Completed").sum())
    return completed / len(relevant), {"relevant": int(len(relevant)), "completed": completed}


def interruption_stats(s: pd.DataFrame) -> dict:
    s = valid_sessions(s)
    if s.empty:
        return {"total": 0, "per_session": None, "per_hour": None}
    total = int(s["interruption_count"].sum())
    hours = s["actual_minutes"].sum() / 60
    return {"total": total, "per_session": total / len(s), "per_hour": total / hours if hours > 0 else None}


def planned_vs_actual(s: pd.DataFrame) -> dict:
    s = valid_sessions(s)
    s = s[s["session_status"] != "Manual"] if not s.empty else s
    if s.empty:
        return {"planned": 0.0, "actual": 0.0, "ratio": None}
    planned, actual = float(s["planned_minutes"].sum()), float(s["actual_minutes"].sum())
    return {"planned": planned, "actual": actual, "ratio": actual / planned if planned > 0 else None}


def active_idle_totals(s: pd.DataFrame) -> dict:
    s = valid_sessions(s)
    total = float(s["actual_minutes"].sum()) if not s.empty else 0.0
    if s.empty:
        return {"total": 0.0, "active": None, "idle": None}
    m = tracked_mask(s)
    return {"total": total, "active": float(s.loc[m, "active_minutes"].sum()) if m.any() else None,
            "idle": float(s.loc[m, "idle_minutes"].sum()) if m.any() else None}


def consistency(daily: pd.Series, goal_minutes: float, first_day: Optional[date] = None, threshold: float = 0.5) -> tuple[Optional[float], dict]:
    """Fraction of days (since the first day of use) that reached `threshold` x daily goal."""
    if daily.empty or goal_minutes <= 0:
        return None, {"days": 0, "hit": 0}
    d = daily[daily.index >= first_day] if first_day else daily
    if d.empty:
        return None, {"days": 0, "hit": 0}
    hit = int((d >= goal_minutes * threshold).sum())
    return hit / len(d), {"days": len(d), "hit": hit}


def low_focus_hours(sessions: pd.DataFrame, min_sessions: int = 3) -> pd.DataFrame:
    """Per hour-of-day focus ratio. Flags hours that are clearly below the person's own average."""
    s = valid_sessions(sessions)
    if s.empty:
        return pd.DataFrame(columns=["hour", "sessions", "minutes", "focus_ratio", "low_focus"])
    rows = []
    for hour, g in s.groupby("hour"):
        ratio, _ = focus_ratio(g)
        rows.append({"hour": int(hour), "sessions": len(g), "minutes": float(g["actual_minutes"].sum()), "focus_ratio": ratio})
    out = pd.DataFrame(rows)
    overall, _ = focus_ratio(s)
    out["low_focus"] = (out["sessions"] >= min_sessions) & (out["focus_ratio"] < (overall or 0) - 0.10)
    return out


def subject_summary(sessions: pd.DataFrame, subjects: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    s = in_window(sessions, start, end)
    cols = ["subject", "color", "minutes", "sessions", "avg_session", "focus_ratio", "target_minutes", "progress"]
    rows = []
    for _, sub in subjects.iterrows():
        g = s[s["subject_id"] == sub["id"]] if not s.empty else s
        minutes = float(g["actual_minutes"].sum()) if not g.empty else 0.0
        fr, _ = focus_ratio(g) if not g.empty else (None, {})
        target = int(sub["target_minutes"] or 0)
        rows.append({"subject": sub["name"], "color": sub["color"], "minutes": minutes, "sessions": len(g),
                     "avg_session": minutes / len(g) if len(g) else None, "focus_ratio": fr,
                     "target_minutes": target, "progress": min(minutes / target, 1.0) if target else None})
    if not s.empty and s["subject_id"].isna().any():
        g = s[s["subject_id"].isna()]
        fr, _ = focus_ratio(g)
        rows.append({"subject": "No subject", "color": "#9AA0C8", "minutes": float(g["actual_minutes"].sum()),
                     "sessions": len(g), "avg_session": float(g["actual_minutes"].mean()), "focus_ratio": fr,
                     "target_minutes": 0, "progress": None})
    return pd.DataFrame(rows, columns=cols)


def heatmap_matrix(daily: pd.Series) -> pd.DataFrame:
    """Calendar heat-map data: one row per day with week index and weekday."""
    if daily.empty:
        return pd.DataFrame(columns=["date", "week", "weekday", "minutes"])
    idx = pd.to_datetime(pd.Series(daily.index))
    first_monday = idx.min() - pd.Timedelta(days=idx.min().weekday())
    return pd.DataFrame({"date": daily.index, "week": ((idx - first_monday).dt.days // 7).values,
                         "weekday": idx.dt.weekday.values, "minutes": daily.values})
