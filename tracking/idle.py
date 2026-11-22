"""Platform-specific idle-time detection. Reads only 'seconds since last input' – never what was typed."""
from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Optional


def get_idle_seconds() -> Optional[float]:
    """Seconds since the last keyboard/mouse input, or None if this platform can't tell."""
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes

            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

            info = LASTINPUTINFO()
            info.cbSize = ctypes.sizeof(LASTINPUTINFO)
            if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
                return None
            millis = ctypes.windll.kernel32.GetTickCount() - info.dwTime
            return max(0.0, millis / 1000.0)
        if system == "Darwin":
            out = subprocess.run(["ioreg", "-c", "IOHIDSystem"], capture_output=True, text=True, timeout=2).stdout
            for line in out.splitlines():
                if "HIDIdleTime" in line:
                    return int(line.split("=")[-1].strip()) / 1_000_000_000
            return None
        if system == "Linux" and shutil.which("xprintidle"):
            out = subprocess.run(["xprintidle"], capture_output=True, text=True, timeout=2).stdout.strip()
            return int(out) / 1000.0
    except Exception:
        return None
    return None


def is_supported() -> bool:
    return get_idle_seconds() is not None
