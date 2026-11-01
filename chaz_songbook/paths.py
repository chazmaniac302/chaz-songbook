"""Filesystem locations (works from source and from a PyInstaller bundle)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent


def resource_path(rel: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", "")) / "chaz_songbook" if hasattr(sys, "_MEIPASS") else PACKAGE_DIR
    return str(base / rel)


def config_dir() -> Path:
    """Where settings live: %APPDATA%\\Chazmaniac\\SongBook on Windows."""
    override = os.environ.get("CHAZ_SONGBOOK_HOME")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "Chazmaniac" / "SongBook"


def default_data_dir() -> Path:
    return config_dir()


def onedrive_dir() -> Path | None:
    for var in ("OneDriveConsumer", "OneDrive", "OneDriveCommercial"):
        v = os.environ.get(var)
        if v and Path(v).is_dir():
            return Path(v)
    p = Path.home() / "OneDrive"
    return p if p.is_dir() else None


def suggested_onedrive_data_dir() -> Path | None:
    od = onedrive_dir()
    return od / "Apps" / "Chaz SongBook" / "Library" if od else None
