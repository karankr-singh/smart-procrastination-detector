"""Pomodoro focus timer. Pure logic with an injectable clock so it can be tested without waiting."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional


class Phase(str, Enum):
    FOCUS = "Focus"
    SHORT_BREAK = "Short break"
    LONG_BREAK = "Long break"


class State(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"


@dataclass
class FocusTimer:
    focus_minutes: float = 25
    short_break_minutes: float = 5
    long_break_minutes: float = 15
    sessions_before_long_break: int = 4
    clock: Callable[[], datetime] = datetime.now

    phase: Phase = Phase.FOCUS
    state: State = State.IDLE
    planned_seconds: float = 0.0
    completed_focus_sessions: int = 0
    _accumulated: float = field(default=0.0, repr=False)
    _resumed_at: Optional[datetime] = field(default=None, repr=False)

    def __post_init__(self):
        self.planned_seconds = self.focus_minutes * 60

    # ---- configuration -------------------------------------------------------------------
    def duration_for(self, phase: Phase) -> float:
        return {Phase.FOCUS: self.focus_minutes, Phase.SHORT_BREAK: self.short_break_minutes,
                Phase.LONG_BREAK: self.long_break_minutes}[phase] * 60

    # ---- controls ----------------------------------------------------------------------------
    def start(self, phase: Optional[Phase] = None, planned_minutes: Optional[float] = None) -> None:
        if self.state != State.IDLE:
            raise RuntimeError("Timer is already active.")
        if phase:
            self.phase = phase
        self.planned_seconds = (planned_minutes * 60) if planned_minutes else self.duration_for(self.phase)
        if self.planned_seconds <= 0:
            raise ValueError("Planned duration must be positive.")
        self._accumulated, self._resumed_at, self.state = 0.0, self.clock(), State.RUNNING

    def pause(self) -> None:
        if self.state != State.RUNNING:
            return
        self._accumulated = self.elapsed()
        self._resumed_at, self.state = None, State.PAUSED

    def resume(self) -> None:
        if self.state != State.PAUSED:
            return
        self._resumed_at, self.state = self.clock(), State.RUNNING

    def stop(self) -> float:
        """Stop the current phase and return elapsed seconds. Timer goes back to idle on the same phase."""
        elapsed = self.elapsed()
        self._reset()
        return elapsed

    def complete(self) -> float:
        """Finish the phase (reached its planned duration). Advances to the next Pomodoro phase."""
        elapsed = min(self.elapsed(), self.planned_seconds)
        finished = self.phase
        self._reset()
        if finished == Phase.FOCUS:
            self.completed_focus_sessions += 1
            due = self.completed_focus_sessions % self.sessions_before_long_break == 0
            self.phase = Phase.LONG_BREAK if due else Phase.SHORT_BREAK
        else:
            self.phase = Phase.FOCUS
        self.planned_seconds = self.duration_for(self.phase)
        return elapsed

    def _reset(self) -> None:
        self._accumulated, self._resumed_at, self.state = 0.0, None, State.IDLE
        self.planned_seconds = self.duration_for(self.phase)

    # ---- readouts ----------------------------------------------------------------------------
    def elapsed(self) -> float:
        if self.state == State.RUNNING and self._resumed_at:
            return self._accumulated + (self.clock() - self._resumed_at).total_seconds()
        return self._accumulated

    def remaining(self) -> float:
        return max(0.0, self.planned_seconds - self.elapsed())

    def progress(self) -> float:
        return min(1.0, self.elapsed() / self.planned_seconds) if self.planned_seconds else 0.0

    def is_done(self) -> bool:
        return self.state == State.RUNNING and self.elapsed() >= self.planned_seconds

    def cycle_position(self) -> int:
        """How many focus sessions are completed in the current long-break cycle."""
        return self.completed_focus_sessions % self.sessions_before_long_break
