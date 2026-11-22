"""Data-driven recommendations. Every item is built from recorded data and states *why* it is shown.
Nothing is generated unless the data supports it, so there are no generic filler tips."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from analytics import metrics, scoring


@dataclass
class Recommendation:
    key: str
    title: str
    body: str
    reason: str
    priority: int          # 1 = most important
    category: str


def _round5(x: float) -> int:
    return int(max(5, round(x / 5) * 5))


def generate(sessions: pd.DataFrame, tasks: pd.DataFrame, subjects: pd.DataFrame, daily_goal: float,
             focus_minutes: int, today: Optional[date] = None, account_start: Optional[date] = None,
             now: Optional[datetime] = None, dismissed: Optional[set] = None) -> list[Recommendation]:
    today = today or date.today()
    dismissed = dismissed or set()
    recs: list[Recommendation] = []
    s14 = metrics.in_window(sessions, today - timedelta(days=13), today)

    # overdue tasks
    if not tasks.empty:
        od = tasks[tasks["status"] == "Overdue"].copy()
        if not od.empty:
            rank = {"Urgent": 0, "High": 1, "Medium": 2, "Low": 3}
            od["r"] = od["priority"].map(rank)
            od = od.sort_values(["r", "deadline"])
            names = ", ".join(f"“{t}”" for t in od["title"].head(3))
            oldest = (today - od["deadline"].min().date()).days
            recs.append(Recommendation("overdue_tasks", f"Clear {len(od)} overdue task(s) first",
                                       f"Start with {names}. Finish or re-plan these before taking on new work.",
                                       f"{len(od)} task(s) are past their deadline; the oldest by {oldest} day(s).", 1, "Tasks"))

    # realistic daily target
    daily = metrics.daily_minutes(sessions, today - timedelta(days=13), today)
    active_days = daily[daily > 0]
    if len(active_days) >= 4:
        med = float(active_days.median())
        if daily_goal > 1.4 * med:
            new = _round5(max(30, med * 1.15))
            recs.append(Recommendation("lower_goal", f"Try a daily goal of {new} minutes",
                                       f"Your goal is {daily_goal:.0f} min but on days you study you typically do {med:.0f} min. "
                                       "A goal you can hit builds the streak that matters.",
                                       f"Median of {len(active_days)} active days in the last 14: {med:.0f} min.", 2, "Goals"))
        elif daily_goal < 0.7 * med:
            new = _round5(med * 1.1)
            recs.append(Recommendation("raise_goal", f"You can raise your daily goal to {new} minutes",
                                       f"You regularly study {med:.0f} min on active days, above your {daily_goal:.0f}-minute goal.",
                                       f"Median of {len(active_days)} active days in the last 14: {med:.0f} min.", 4, "Goals"))

    # shorter focus sessions
    done = s14[s14["session_status"].isin(["Completed", "Stopped Early", "Abandoned"])] if not s14.empty else s14
    if len(done) >= 4:
        stopped = done[done["session_status"] != "Completed"]
        if len(stopped) / len(done) >= 0.4 and done["planned_minutes"].median() >= 20:
            suggestion = _round5(max(10, stopped["actual_minutes"].median()))
            if suggestion < focus_minutes:
                recs.append(Recommendation("shorter_sessions", f"Try {suggestion}-minute focus sessions",
                                           f"{len(stopped)} of your last {len(done)} sessions ended early, usually after about "
                                           f"{stopped['actual_minutes'].median():.0f} min. Match the plan to that, then build up.",
                                           f"{len(stopped) / len(done):.0%} of recent sessions were stopped early.", 2, "Focus"))

    # breaks after extended focus
    if not s14.empty:
        long_sessions = s14[s14["actual_minutes"] >= 75]
        chain, best, prev_end = 0.0, 0.0, None
        for _, r in s14.sort_values("start_time").iterrows():
            gap = (r["start_time"] - prev_end).total_seconds() / 60 if prev_end is not None else 999
            chain = r["actual_minutes"] if not (0 <= gap <= 5) else chain + r["actual_minutes"]
            best = max(best, chain)
            prev_end = r["end_time"] if pd.notna(r["end_time"]) else r["start_time"] + timedelta(minutes=r["actual_minutes"])
        if len(long_sessions) >= 2 or best >= 120:
            recs.append(Recommendation("take_breaks", "Add a break every 50–60 minutes",
                                       "Long unbroken stretches are where focus drops. Use the Pomodoro cycle, or at least stand up "
                                       "for 5 minutes between blocks.",
                                       f"{len(long_sessions)} session(s) of 75+ min; longest back-to-back stretch {best:.0f} min.", 3, "Focus"))

    # subjects with too little time
    if not subjects.empty:
        week = metrics.subject_summary(sessions, subjects, today - timedelta(days=6), today)
        short = week[(week["target_minutes"] > 0) & (week["minutes"] < 0.5 * week["target_minutes"])
                     & (week["subject"] != "No subject")].sort_values("progress")
        if not short.empty:
            r = short.iloc[0]
            recs.append(Recommendation(f"subject_low:{r['subject']}", f"{r['subject']} needs more time this week",
                                       f"You've studied {r['minutes']:.0f} of {r['target_minutes']:.0f} planned minutes. "
                                       f"Book one {focus_minutes}-minute session for it in the next two days.",
                                       f"Only {r['progress']:.0%} of the weekly goal so far.", 2, "Subjects"))
        if not tasks.empty:
            pend = tasks[(tasks["status"] != "Completed") & tasks["subject_id"].notna()]
            counts = pend.groupby("subject_id").size()
            month = metrics.subject_summary(sessions, subjects, today - timedelta(days=13), today).set_index("subject")
            for sid, n in counts.items():
                name = subjects.loc[subjects["id"] == sid, "name"]
                if name.empty:
                    continue
                name = name.iloc[0]
                if name in month.index and month.loc[name, "minutes"] == 0 and n >= 2 and not any(
                        r.key == f"subject_low:{name}" for r in recs):
                    recs.append(Recommendation(f"subject_idle:{name}", f"No study time on {name} in 2 weeks",
                                               f"{n} open tasks are waiting in this subject. Start with the smallest one.",
                                               f"0 minutes logged in 14 days while {n} tasks are open.", 3, "Subjects"))

    # break big tasks into smaller steps
    if not tasks.empty:
        big = tasks[(tasks["status"] != "Completed") & (tasks["estimated_minutes"].fillna(0) >= 120)
                    & ((tasks["postponement_count"] >= 1) | (tasks["actual_minutes"] == 0))]
        if not big.empty:
            t = big.sort_values("estimated_minutes", ascending=False).iloc[0]
            recs.append(Recommendation(f"split_task:{int(t['id'])}", f"Split “{t['title']}” into smaller steps",
                                       f"Estimated at {t['estimated_minutes']:.0f} min. Create 3–4 sub-tasks of 30–45 minutes each.",
                                       "Large tasks with no progress or postponements are the ones most often put off.", 3, "Tasks"))

    # weekly improvement
    this_week = scoring.compute_score(sessions, tasks, daily_goal, today, 7, account_start, now)
    if this_week.score is not None:
        weakest = min((c for c in this_week.components if c.available), key=lambda c: c.value)
        tips = {"task_completion": "Pick your top 3 tasks each morning and finish them before anything new.",
                "focus_ratio": "Put the phone out of reach during focus blocks and log each interruption.",
                "goal_progress": "Schedule your study blocks in the hours you picked in your profile.",
                "consistency": "Aim for a small daily minimum rather than occasional long sessions."}
        prev = metrics.daily_minutes(sessions, today - timedelta(days=13), today - timedelta(days=7)).sum()
        cur = metrics.daily_minutes(sessions, today - timedelta(days=6), today).sum()
        trend = f" Study time is {'up' if cur >= prev else 'down'} {abs(cur - prev):.0f} min versus the week before." if prev > 0 else ""
        recs.append(Recommendation(f"weekly:{today.isocalendar().year}-W{today.isocalendar().week}",
                                   f"This week: strengthen {weakest.label.lower()}",
                                   tips[weakest.key] + trend,
                                   f"{weakest.label} is your lowest score component ({weakest.value:.0%}).", 5, "Weekly"))
    recs = [r for r in recs if r.key not in dismissed]
    return sorted(recs, key=lambda r: r.priority)
