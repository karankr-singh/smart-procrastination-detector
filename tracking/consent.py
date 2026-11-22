"""Consent rules for optional activity tracking. Tracking is OFF unless the user has explicitly opted in."""
from __future__ import annotations

from datetime import datetime

from database import repositories as repo

PRIVACY_PROMISES = [
    "Tracking stays off until you switch it on.",
    "Only two things are measured: how long the computer has been idle, and the category of the active app.",
    "App names are mapped to a category (Study, Programming…) and the name itself is never stored.",
    "No keystrokes, passwords, messages, screenshots, document contents or clipboard data are ever read.",
    "You can pause or stop tracking at any time, and delete everything recorded.",
]


def has_consent(settings: dict) -> bool:
    return bool(settings.get("tracking_consent"))


def grant_consent(user_id: int, *, idle: bool, apps: bool) -> None:
    repo.set_settings(user_id, {"tracking_consent": True, "tracking_consent_at": datetime.now().isoformat(timespec="seconds"),
                                "track_idle": bool(idle), "track_apps": bool(apps)})


def revoke_consent(user_id: int) -> None:
    repo.set_settings(user_id, {"tracking_consent": False, "track_idle": False, "track_apps": False})


def effective_flags(settings: dict) -> tuple[bool, bool]:
    """(idle_enabled, apps_enabled) – both are forced False without consent."""
    if not has_consent(settings):
        return False, False
    return bool(settings.get("track_idle")), bool(settings.get("track_apps"))
