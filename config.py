"""Central configuration for Smart Procrastination Detector (SPD)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

APP_NAME = "Smart Procrastination Detector"
APP_SHORT = "SPD"
APP_VERSION = "1.0.0"

DATA_DIR = Path(os.getenv("SPD_DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.getenv("SPD_DB_PATH", DATA_DIR / "spd.sqlite3"))
BACKUP_DIR = DATA_DIR / "backups"

PRIORITIES = ["Low", "Medium", "High", "Urgent"]
TASK_STATUSES = ["Pending", "In Progress", "Completed", "Overdue"]
SESSION_STATUSES = ["Running", "Completed", "Stopped Early", "Abandoned", "Manual"]
APP_CATEGORIES = ["Study", "Programming", "Research", "Communication", "Entertainment", "Other"]

SUBJECT_COLORS = ["#8B7CFF", "#3DDBC0", "#FFB86B", "#FF6F91", "#5AB8FF", "#C792EA", "#9BE564", "#F7768E"]

# Defaults for user_settings (stored as strings in the DB, parsed by type of default).
DEFAULT_SETTINGS: dict = {
    "focus_minutes": 25,
    "short_break_minutes": 5,
    "long_break_minutes": 15,
    "sessions_before_long_break": 4,
    "idle_threshold_minutes": 5,
    "tracking_consent": False,      # privacy: off by default
    "tracking_consent_at": "",
    "track_idle": False,
    "track_apps": False,
    "notify_toast": True,
    "notify_sound": True,
    "auto_start_breaks": True,
    "is_synthetic": False,          # set by the demo-data script
}
