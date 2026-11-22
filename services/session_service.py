"""Glue between the timer, the optional tracker and the database."""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from database import repositories as repo
from services.timer import FocusTimer, Phase, State
from tracking.tracker import ActivityTracker

MIN_RECORDED_SECONDS = 10       # sessions shorter than this are treated as accidental starts
HEARTBEAT_SECONDS = 30
MAX_SAMPLE_GAP = 5.0            # cap a single tracker sample so a stalled UI can't invent activity


class SessionManager:
    def __init__(self, user_id: int, settings: dict, clock: Callable[[], datetime] = datetime.now,
                 tracker_factory: Callable[..., Optional[ActivityTracker]] = ActivityTracker.from_settings):
        self.user_id, self.settings, self.clock = user_id, settings, clock
        self.tracker_factory = tracker_factory
        self.timer = FocusTimer(settings["focus_minutes"], settings["short_break_minutes"],
                                settings["long_break_minutes"], settings["sessions_before_long_break"], clock=clock)
        self.session_id: Optional[int] = None
        self.subject_id: Optional[int] = None
        self.task_id: Optional[int] = None
        self.interruptions = 0
        self.tracker: Optional[ActivityTracker] = None
        self.auto_paused = False
        self._extra_events: list[dict] = []
        self._last_tick: Optional[datetime] = None
        self._last_beat: Optional[datetime] = None

    # ---- state -------------------------------------------------------------------------------
    @property
    def active(self) -> bool:
        return self.timer.state != State.IDLE

    @property
    def in_focus(self) -> bool:
        return self.timer.phase == Phase.FOCUS

    def apply_settings(self, settings: dict) -> None:
        """Pick up new timer lengths; never changes a phase that is already running."""
        self.settings = settings
        if self.timer.state == State.IDLE:
            t = self.timer
            t.focus_minutes, t.short_break_minutes = settings["focus_minutes"], settings["short_break_minutes"]
            t.long_break_minutes = settings["long_break_minutes"]
            t.sessions_before_long_break = settings["sessions_before_long_break"]
            t.planned_seconds = t.duration_for(t.phase)

    # ---- controls ----------------------------------------------------------------------------
    def start(self, subject_id: Optional[int] = None, task_id: Optional[int] = None,
              planned_minutes: Optional[float] = None) -> None:
        now = self.clock()
        if self.timer.phase == Phase.FOCUS:
            planned = planned_minutes or self.timer.focus_minutes
            self.subject_id, self.task_id = subject_id, task_id
            self.session_id = repo.start_session(self.user_id, subject_id, task_id, planned, start_time=now)
            self.interruptions, self.auto_paused, self._extra_events = 0, False, []
            self.tracker = self.tracker_factory(self.settings)
            self.timer.start(planned_minutes=planned)
        else:
            self.timer.start()
        self._last_tick = self._last_beat = now

    def pause(self, auto: bool = False) -> None:
        if self.timer.state != State.RUNNING:
            return
        self.timer.pause()
        self.auto_paused = auto
        if self.session_id:
            repo.heartbeat_session(self.session_id, self.timer.elapsed() / 60)

    def resume(self) -> None:
        if self.timer.state != State.PAUSED:
            return
        self.auto_paused = False
        self.timer.resume()
        self._last_tick = self.clock()

    def log_interruption(self) -> None:
        if self.session_id and self.in_focus and self.active:
            self.interruptions += 1
            self._extra_events.append({"event_type": "interruption", "duration_seconds": 0})

    def stop(self) -> Optional[dict]:
        """Stop the current phase. Focus sessions are saved (or discarded if accidental)."""
        if not self.active:
            return None
        if not self.in_focus:                        # skipping a break
            self.timer.stop()
            self.timer.phase, self.timer.planned_seconds = Phase.FOCUS, self.timer.duration_for(Phase.FOCUS)
            return None
        elapsed = self.timer.stop()
        if elapsed < MIN_RECORDED_SECONDS:
            if self.session_id:
                repo.delete_empty_session(self.session_id)
            self._clear()
            return None
        return self._finalize("Stopped Early", elapsed)

    def tick(self) -> list[str]:
        """Call about once a second. Returns notable events: 'phase_complete', 'break_over', 'auto_paused'."""
        out: list[str] = []
        now = self.clock()
        if self.timer.state == State.RUNNING:
            dt = min((now - self._last_tick).total_seconds(), MAX_SAMPLE_GAP) if self._last_tick else 0.0
            self._last_tick = now
            if self.tracker and self.in_focus and not self.timer.is_done():
                if self.tracker.sample(dt)["auto_pause"]:
                    self._extra_events.append({"event_type": "auto_pause", "duration_seconds": 0})
                    self.interruptions += 1
                    self.pause(auto=True)
                    out.append("auto_paused")
            if self._last_beat and self.session_id and (now - self._last_beat).total_seconds() >= HEARTBEAT_SECONDS:
                repo.heartbeat_session(self.session_id, self.timer.elapsed() / 60)
                self._last_beat = now
        if self.timer.is_done():
            if self.in_focus:
                elapsed = self.timer.complete()
                self._finalize("Completed", elapsed, already_advanced=True)
                out.append("phase_complete")
                if self.settings.get("auto_start_breaks"):
                    self.timer.start()
                    self._last_tick = self.clock()
            else:
                self.timer.complete()
                out.append("break_over")
        return out

    # ---- persistence -------------------------------------------------------------------------
    def _finalize(self, status: str, elapsed_seconds: float, already_advanced: bool = False) -> dict:
        active = idle = None
        events = list(self._extra_events)
        if self.tracker:
            summ = self.tracker.summary()
            active, idle = summ["active_minutes"], summ["idle_minutes"]
            events += self.tracker.events()
        record = repo.finish_session(self.session_id, actual_minutes=elapsed_seconds / 60, status=status,
                                     end_time=self.clock(), active_minutes=active, idle_minutes=idle,
                                     interruption_count=self.interruptions, events=events)
        self._clear()
        return record

    def _clear(self) -> None:
        self.session_id, self.tracker, self.auto_paused, self.interruptions = None, None, False, 0
        self._extra_events = []
