from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout, QWidget

from . import theme


def card(title: str | None = None, spacing: int = 10):
    f = QFrame()
    f.setObjectName("Card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(16, 14, 16, 16)
    lay.setSpacing(spacing)
    if title:
        t = QLabel(title.upper())
        t.setObjectName("SectionTitle")
        t.setFont(theme.head_font(13))
        lay.addWidget(t)
    return f, lay


def muted(text: str = "") -> QLabel:
    l = QLabel(text)
    l.setObjectName("Muted")
    return l


def hbox(*widgets, spacing=8, stretch_last=False):
    w = QWidget()
    l = QHBoxLayout(w)
    l.setContentsMargins(0, 0, 0, 0)
    l.setSpacing(spacing)
    for x in widgets:
        if x is None:
            l.addStretch(1)
        elif isinstance(x, int):
            l.addSpacing(x)
        else:
            l.addWidget(x)
    if stretch_last:
        l.addStretch(1)
    return w


def open_path(path: str | Path) -> bool:
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def show_in_explorer(path: str | Path) -> bool:
    p = Path(path)
    if sys.platform == "win32":
        if p.is_file():
            subprocess.Popen(["explorer", "/select,", str(p)])
            return True
        if p.is_dir():
            os.startfile(str(p))  # type: ignore[attr-defined]
            return True
        if p.parent.is_dir():
            os.startfile(str(p.parent))  # type: ignore[attr-defined]
            return True
        return False
    target = p if p.is_dir() else p.parent
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
