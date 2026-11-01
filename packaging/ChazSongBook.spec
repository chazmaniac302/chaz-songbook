# PyInstaller spec: builds both a one-folder app and a single-file portable exe.
# Run from the repo root:  pyinstaller packaging/ChazSongBook.spec --noconfirm
import os
from pathlib import Path

ROOT = Path(os.getcwd())
datas = [
    (str(ROOT / "chaz_songbook" / "data"), "chaz_songbook/data"),
    (str(ROOT / "chaz_songbook" / "assets"), "chaz_songbook/assets"),
]
excludes = ["tkinter", "unittest", "pydoc", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
            "PySide6.Qt3DCore", "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtCharts",
            "PySide6.QtDataVisualization", "PySide6.QtPdf", "PySide6.QtSql", "PySide6.QtTest"]
icon = str(ROOT / "chaz_songbook" / "assets" / "icon.ico")
version = str(ROOT / "packaging" / "version_info.txt")

a = Analysis([str(ROOT / "run_songbook.py")], pathex=[str(ROOT)], datas=datas,
             hiddenimports=["PySide6.QtMultimedia"], excludes=excludes, noarchive=False)

# Drop Qt pieces this widgets app never uses (QML/Quick, virtual keyboard, PDF viewer, software GL, translations)
PRUNE = ("qt6quick", "qt6qml", "virtualkeyboard", "qt6pdf", "opengl32sw", "qt6waylandclient",
         "/translations/", "\\translations\\", "platforminputcontexts", "qt6wlshell", "egldevice",
         "wayland-", "qt6eglfs")


def keep(entry):
    name = entry[0].replace("\\", "/").lower()
    return not any(p.replace("\\", "/") in name for p in PRUNE)


a.binaries = [b for b in a.binaries if keep(b)]
a.datas = [d for d in a.datas if keep(d)]
pyz = PYZ(a.pure)

# one-folder build (fast start; what the installer copies)
exe_dir = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ChazSongBook", console=False,
              icon=icon, version=version, upx=False)
COLLECT(exe_dir, a.binaries, a.datas, name="Chaz SongBook", upx=False)

# single-file portable build
EXE(pyz, a.scripts, a.binaries, a.datas, [], name="ChazSongBook-Portable", console=False,
    icon=icon, version=version, upx=False, runtime_tmpdir=None)
