"""Productivity score (0-100).

FORMULA
-------
For a window of ``window_days`` ending on ``end_date`` (default 7 days) four components are each
normalised to 0..1:

  task_completion (weight 35)   completed tasks / tasks that were due or completed in the window
  focus_ratio     (weight 30)   active / (active + idle) for tracked sessions; for untracked sessions the
                                proxy min(actual/planned, 1). Weighted by minutes.
  goal_progress   (weight 20)   minutes studied / (daily goal x days in the window), capped at 1
  consistency     (weight 15)   share of days that reached at least 50% of the daily goal

Missing data: a component with no data (e.g. no tasks due) is *left out* and the remaining weights are
rescaled to sum to 100, so missing data never counts as a zero. If nothing can be measured the score is None.
Days before the person started using the app are not counted. All divisions are guarded against zero.

score = round( sum(value_i x weight_i) / sum(weight_i of available components) x 100 )

This is a transparent self-reflection aid, not a scientific or psychological diagnosis.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

from analytics import metrics

WEIGHTS = {"task_completion": 35, "focus_ratio": 30, "goal_progress": 20, "consistency": 15}
LABELS = {"task_completion": "Task completion", "focus_ratio": "Focus", "goal_progress": "Goal progress",
          "consistency": "Consistency"}
DISCLAIMER = "A self-reflection aid built from your own records – not a scientific or psychological assessment."


@dataclass
class Component:
    key: str
    label: str
    weight: int
    value: Optional[float]          # 0..1, None when there's no data
    explanation: str
    effective_weight: float = 0.0   # after rescaling
    points: float = 0.0

    @property
    def available(self) -> bool:
        return self.value is not None


@dataclass
class ScoreResult:
    score: Optional[int]
    components: list[Component] = field(default_factory=list)
    window_start: Optional[date] = None
    window_end: Optional[date] = None
    notes: list[str] = field(default_factory=list)


def compute_score(sessions: pd.DataFrame, tasks: pd.DataFrame, daily_goal_minutes: float, end_date: date,
                  window_days: int = 7, account_start: Optional[date] = None,
                  now: Optional[datetime] = None) -> ScoreResult:
    start = end_date - timedelta(days=window_days - 1)
    first_day = max(start, account_start) if account_start else start
    result = ScoreResult(None, window_start=start, window_end=end_date)
    if first_day > end_date:
        result.notes.append("Not enough history yet.")
        return result

    window = metrics.in_window(sessions, first_day, end_date)
    daily = metrics.daily_minutes(sessions, first_day, end_date)
    days = max(1, (end_date - first_day).days + 1)

    # task completion
    tc, tc_info = metrics.task_completion(tasks, first_day, end_date, now)
    tc_text = (f"{tc_info['completed']} of {tc_info['relevant']} tasks due or finished in this window are done."
               if tc is not None else "No tasks were due or completed in this window, so this part is left out.")
    # focus
    fr, fr_info = metrics.focus_ratio(window)
    if fr is None:
        fr_text = "No study sessions in this window, so this part is left out."
    elif fr_info["tracked_minutes"] > 0 and fr_info["proxy_minutes"] == 0:
        fr_text = "Based on measured active vs idle time."
    elif fr_info["tracked_minutes"] == 0:
        fr_text = "Based on how much of each planned session you completed (idle tracking was off)."
    else:
        fr_text = "Mix of measured active time and planned-vs-actual completion."
    # goal progress
    total = float(daily.sum())
    gp = min(total / (daily_goal_minutes * days), 1.0) if daily_goal_minutes > 0 else None
    gp_text = f"{total:.0f} of {daily_goal_minutes * days:.0f} target minutes studied over {days} day(s)."
    # consistency
    cons, cons_info = metrics.consistency(daily, daily_goal_minutes, first_day)
    cons_text = (f"{cons_info['hit']} of {cons_info['days']} days reached half of your daily goal."
                 if cons is not None else "Not enough days to measure.")

    comps = [Component("task_completion", LABELS["task_completion"], WEIGHTS["task_completion"], tc, tc_text),
             Component("focus_ratio", LABELS["focus_ratio"], WEIGHTS["focus_ratio"], fr, fr_text),
             Component("goal_progress", LABELS["goal_progress"], WEIGHTS["goal_progress"], gp, gp_text),
             Component("consistency", LABELS["consistency"], WEIGHTS["consistency"], cons, cons_text)]

    has_activity = (not window.empty) or (tc is not None)
    avail_weight = sum(c.weight for c in comps if c.available)
    if not has_activity or avail_weight == 0:
        result.components = comps
        result.notes.append("Nothing recorded in this window yet – the score appears once you log study time or finish tasks.")
        return result

    for c in comps:
        if c.available:
            c.effective_weight = c.weight / avail_weight * 100
            c.points = c.value * c.effective_weight
    result.components = comps
    result.score = int(round(sum(c.points for c in comps)))
    if avail_weight < 100:
        result.notes.append("Some parts had no data, so the remaining parts were rescaled to 100.")
    return result


def rolling_scores(sessions: pd.DataFrame, tasks: pd.DataFrame, goal: float, start: date, end: date,
                   account_start: Optional[date] = None, now: Optional[datetime] = None) -> pd.DataFrame:
    rows = []
    for d in metrics.date_range(start, end):
        r = compute_score(sessions, tasks, goal, d, 7, account_start, now)
        rows.append({"date": d, "score": r.score})
    return pd.DataFrame(rows, columns=["date", "score"])
