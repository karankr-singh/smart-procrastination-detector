"""Foreground-application *category* detection. The process name is mapped to a category in memory and
discarded – only the category is ever stored. Window titles and contents are never read."""
from __future__ import annotations

import platform
import subprocess
from typing import Optional

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Programming": ("code", "pycharm", "idea", "devenv", "sublime", "vim", "nvim", "terminal", "powershell",
                    "cmd", "wt", "iterm", "jupyter", "spyder", "rstudio", "xcode", "androidstudio", "github"),
    "Study": ("onenote", "obsidian", "notion", "anki", "word", "winword", "pages", "acrobat", "sumatra",
              "foxit", "kindle", "zotero", "powerpnt", "keynote", "excel", "calibre", "evernote", "goodnotes"),
    "Research": ("chrome", "firefox", "msedge", "safari", "brave", "opera", "arc", "scholar", "mendeley"),
    "Communication": ("slack", "teams", "discord", "whatsapp", "telegram", "zoom", "skype", "outlook",
                      "thunderbird", "mail", "signal", "messenger"),
    "Entertainment": ("spotify", "netflix", "vlc", "steam", "epicgames", "tiktok", "twitch", "primevideo",
                      "games", "minecraft", "valorant", "riot", "origin", "music"),
}


def categorize(process_name: Optional[str]) -> str:
    if not process_name:
        return "Other"
    name = process_name.lower().replace(".exe", "")
    for category, words in CATEGORY_KEYWORDS.items():
        if any(w == name or w in name for w in words):
            return category
    return "Other"


def get_foreground_process_name() -> Optional[str]:
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes
            import psutil
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return psutil.Process(pid.value).name() if pid.value else None
        if system == "Darwin":
            out = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of first application process whose frontmost is true'],
                capture_output=True, text=True, timeout=2).stdout.strip()
            return out or None
    except Exception:
        return None
    return None


def is_supported() -> bool:
    return get_foreground_process_name() is not None
