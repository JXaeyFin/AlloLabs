"""Application and writable-data paths shared by source and desktop builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "AlloLabs"


def application_root() -> Path:
    """Return the directory containing bundled read-only application assets."""
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        return Path(bundled_root).resolve()
    return Path(__file__).resolve().parent


def user_data_dir() -> Path:
    """Return a writable directory for generated reports, results, and caches."""
    configured = os.getenv("ALLOLABS_DATA_DIR")
    if configured:
        path = Path(configured).expanduser().resolve()
    elif getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        elif os.name == "nt":
            local_app_data = os.getenv("LOCALAPPDATA")
            base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        else:
            xdg_data_home = os.getenv("XDG_DATA_HOME")
            base = Path(xdg_data_home).expanduser() if xdg_data_home else Path.home() / ".local" / "share"
        path = base / APP_NAME
    else:
        path = application_root()
    path.mkdir(parents=True, exist_ok=True)
    return path
