"""Explainable procrastination indicators.

Each indicator is a *behavioural observation* with four parts: the observed pattern, the supporting data,
a possible explanation and a suggested improvement. They are not medical or psychological diagnoses.
Thresholds are named constants so they can be inspected and tuned.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from analytics import metrics

NOTE = "Procrastination indicators are behavioural observations, not medical or psychological diagnoses."

POSTPONED_MIN = 2            # a task postponed at least this many times
EXTENSION_MIN = 2            # deadline pushed later at least this many times
GAP_DAYS_MIN = 3             # a gap of at least this many days between study days...
GAP_RATIO_MIN = 2.0          # ...and at least this many times the typical gap
INCOMPLETE_SHARE_MIN = 0.30  # share of sessions ended early
INCOMPLETE_COUNT_MIN = 3
INTERRUPTIONS_PER_SESSION = 2.0
PLAN_ACTUAL_RATIO_MAX = 0.75


@dataclass
class Indicator:
    key: str
    title: str
    observed: str
    data: dict = field(default_factory=dict)
    explanation: str = ""
    suggestion: str = ""
    severity: str = "watch"          # "watch" | "notable"


def detect(sessions: pd.DataFrame, tasks: pd.DataFrame, daily_goal: float, today: Optional[date] = None,
           lookback_days: int = 21) -> list[Indicator]:
    today = today or date.today()
    start = today - timedelta(days=lookback_days - 1)
    s = metrics.in_window(sessions, start, today)
    out: list[Indicator] = []
    open_tasks = tasks[tasks["status"] != "Completed"] if not tasks.empty else tasks

    # 1. repeatedly postponed tasks
    if not tasks.empty:
        p = open_tasks[open_tasks["postponement_count"] >= POSTPONED_MIN].sort_values("postponement_count", ascending=False)
        if not p.empty:
            top = p.iloc[0]
            out.append(Indicator(
                "postponed_tasks", "Tasks keep getting pushed back",
                f"{len(p)} open task(s) have been postponed {POSTPONED_MIN}+ times.",
                {"Most postponed": f"{top['title']} ({int(top['postponement_count'])}×)",
                 "Subject": top["subject_name"], "Logged so far": f"{top['actual_minutes']:.0f} min"},
                "Repeated postponing often means a task feels too big, unclear or unpleasant to start.",
                "Split it into a 15–25 minute first step and schedule just that step.",
                "notable" if top["postponement_count"] >= 4 else "watch"))

        # 2. frequent deadline extensions
        e = open_tasks[open_tasks["extension_count"] >= EXTENSION_MIN].sort_values("extension_count", ascending=False)
        if not e.empty:
            top = e.iloc[0]
            out.append(Indicator(
                "deadline_extensions", "Deadlines keep moving",
                f"{len(e)} open task(s) had their deadline moved later {EXTENSION_MIN}+ times.",
                {"Most extended": f"{top['title']} ({int(top['extension_count'])}×)"},
                "If a deadline keeps moving, it may no longer be creating a useful sense of commitment.",
                "Pick a realistic date once, and add a mid-point check-in."))

    # 3. unusually long gaps between study days
    days = sorted(set(s["date"])) if not s.empty else []
    if len(days) >= 4:
        gaps = np.diff([d.toordinal() for d in days])
        typical = float(np.median(gaps))
        longest = int(gaps.max())
        if longest >= GAP_DAYS_MIN and longest >= GAP_RATIO_MIN * max(typical, 1):
            i = int(gaps.argmax())
            out.append(Indicator(
                "long_gaps", "A long gap between study days",
                f"You went {longest} days without studying (typical gap: {typical:.0f} day(s)).",
                {"Gap": f"{days[i].strftime('%d %b')} → {days[i + 1].strftime('%d %b')}", "Study days (3 wks)": str(len(days))},
                "Long breaks often follow a missed deadline, a heavy week or a loss of routine.",
                "Protect a short anchor session (even 15 minutes) on every day of the week.", "watch"))

    # 4. repeated incomplete sessions
    planned = s[s["session_status"].isin(["Completed", "Stopped Early", "Abandoned"])] if not s.empty else s
    if len(planned) >= 5:
        stopped = planned[planned["session_status"].isin(["Stopped Early", "Abandoned"])]
        share = len(stopped) / len(planned)
        if len(stopped) >= INCOMPLETE_COUNT_MIN and share >= INCOMPLETE_SHARE_MIN:
            kept = (stopped["actual_minutes"] / stopped["planned_minutes"]).mean()
            out.append(Indicator(
                "incomplete_sessions", "Sessions often end early",
                f"{len(stopped)} of {len(planned)} recent sessions ({share:.0%}) were stopped before the planned time.",
                {"Average time kept when stopping": f"{kept:.0%} of plan"},
                "Sessions that are longer than your attention span tend to end early.",
                "Try a shorter focus length for a week and extend it once you finish most sessions.",
                "notable" if share >= 0.5 else "watch"))

    # 5. frequent interruptions
    ist = metrics.interruption_stats(s)
    if ist["per_session"] is not None and len(s) >= 4 and ist["per_session"] >= INTERRUPTIONS_PER_SESSION:
        out.append(Indicator(
            "interruptions", "Frequent interruptions",
            f"{ist['per_session']:.1f} interruptions per session on average.",
            {"Total interruptions": str(ist["total"]), "Per study hour": f"{ist['per_hour']:.1f}"},
            "Frequent interruptions fragment attention and make sessions feel longer than they are.",
            "Silence notifications and note each interruption's cause for a few sessions to spot the main one.",
            "notable" if ist["per_session"] >= 3 else "watch"))

    # 6. planned vs actual gap
    pa = metrics.planned_vs_actual(s)
    if pa["ratio"] is not None and len(s) >= 5 and pa["ratio"] < PLAN_ACTUAL_RATIO_MAX:
        out.append(Indicator(
            "plan_vs_actual", "Plans are bigger than what happens",
            f"You studied {pa['ratio']:.0%} of the time you planned.",
            {"Planned": f"{pa['planned']:.0f} min", "Actual": f"{pa['actual']:.0f} min"},
            "A steady gap between plan and reality usually signals over-planning rather than laziness.",
            "Plan about 20% less time than you think you need, then add a bonus session if you finish early.", "watch"))

    # 7. estimate vs actual on finished tasks
    if not tasks.empty:
        fin = tasks[(tasks["status"] == "Completed") & tasks["estimated_minutes"].notna() & (tasks["actual_minutes"] > 0)]
        if len(fin) >= 4:
            ratio = fin["actual_minutes"].sum() / fin["estimated_minutes"].sum()
            if ratio > 1.4:
                out.append(Indicator(
                    "underestimates", "Tasks take longer than estimated",
                    f"Finished tasks took {ratio:.1f}× their estimate on average.",
                    {"Tasks compared": str(len(fin))},
                    "Under-estimating makes plans look easy, which makes starting later feel safe.",
                    "Multiply your next estimates by the ratio shown here.", "watch"))
    return out
