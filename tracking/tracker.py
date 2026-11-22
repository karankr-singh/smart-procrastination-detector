"""Consent-based session tracker. Created only when the user has consented; samples are injected so the
class is fully testable without a real desktop."""
from __future__ import annotations

from collections import defaultdict
from typing import Callable, Optional

from tracking import apps, consent, idle

IDLE_CLASSIFY_SECONDS = 60   # no input for this long => the time counts as idle


class ActivityTracker:
    def __init__(self, track_idle: bool, track_apps: bool, idle_threshold_minutes: float = 5,
                 idle_fn: Callable[[], Optional[float]] = idle.get_idle_seconds,
                 app_fn: Callable[[], Optional[str]] = apps.get_foreground_process_name):
        self.track_idle, self.track_apps = track_idle, track_apps
        self.idle_threshold_seconds = idle_threshold_minutes * 60
        self._idle_fn, self._app_fn = idle_fn, app_fn
        self.active_seconds = 0.0
        self.idle_seconds = 0.0
        self.category_seconds: dict[str, float] = defaultdict(float)
        self.paused_by_user = False
        self.auto_pauses = 0
        self.idle_supported: Optional[bool] = None

    @classmethod
    def from_settings(cls, settings: dict, **kwargs) -> Optional["ActivityTracker"]:
        """Returns None unless the user consented AND enabled at least one tracking type."""
        idle_on, apps_on = consent.effective_flags(settings)
        if not (idle_on or apps_on):
            return None
        return cls(idle_on, apps_on, settings.get("idle_threshold_minutes", 5), **kwargs)

    @property
    def measures_activity(self) -> bool:
        return self.track_idle and self.idle_supported is not False

    def sample(self, dt_seconds: float) -> dict:
        """Record `dt_seconds` of time. Returns {'auto_pause': bool}."""
        result = {"auto_pause": False}
        if self.paused_by_user or dt_seconds <= 0:
            return result
        if self.track_idle:
            idle_s = self._idle_fn()
            self.idle_supported = idle_s is not None
            if idle_s is not None:
                if idle_s >= IDLE_CLASSIFY_SECONDS:
                    self.idle_seconds += dt_seconds
                else:
                    self.active_seconds += dt_seconds
                if idle_s >= self.idle_threshold_seconds:
                    self.auto_pauses += 1
                    result["auto_pause"] = True
        if self.track_apps:
            self.category_seconds[apps.categorize(self._app_fn())] += dt_seconds
        return result

    def summary(self) -> dict:
        has_idle = self.measures_activity
        return {"active_minutes": round(self.active_seconds / 60, 3) if has_idle else None,
                "idle_minutes": round(self.idle_seconds / 60, 3) if has_idle else None,
                "categories": dict(self.category_seconds)}

    def events(self) -> list[dict]:
        out: list[dict] = []
        if self.measures_activity:
            out.append({"event_type": "active", "duration_seconds": round(self.active_seconds, 1)})
            out.append({"event_type": "idle", "duration_seconds": round(self.idle_seconds, 1)})
        for cat, secs in self.category_seconds.items():
            out.append({"event_type": "category", "category": cat, "duration_seconds": round(secs, 1)})
        return out
