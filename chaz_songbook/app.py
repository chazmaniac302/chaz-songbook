"""Entry point: python -m chaz_songbook [--data-dir DIR] [--smoke-test] [--screenshots DIR]"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import traceback
from pathlib import Path

from . import APP_NAME, ORG_NAME, __version__


def _make_app(argv):
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from .paths import resource_path
    from .ui import theme

    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(resource_path("assets/icon.png")))
    theme.apply(app)
    return app


def _open_window(data_dir: Path | None, settings_dir: Path | None = None):
    from .store import Library, Settings
    from .ui.main_window import MainWindow
    settings = Settings(settings_dir)
    lib = Library(Path(data_dir) if data_dir else settings.data_dir)
    return MainWindow(settings, lib)


def run_smoke_test(out_file: str | None) -> int:
    """Launch the real UI against a temp library, exercise it, export, reload. Exit 0 on success."""
    lines = []

    def log(msg):
        lines.append(msg)
        print(msg, flush=True)

    code = 1
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        from . import export as ex
        from .store import Library
        app = _make_app(sys.argv[:1])
        QTimer.singleShot(60000, lambda: (log("TIMEOUT"), os._exit(3)))
        tmp = Path(tempfile.mkdtemp(prefix="chaz-songbook-smoke-"))
        os.environ["CHAZ_SONGBOOK_HOME"] = str(tmp / "cfg")
        w = _open_window(tmp / "data", tmp / "cfg")
        w.show()
        app.processEvents()
        log(f"window shown: {w.windowTitle()} platform={QApplication.platformName()}")
        assert len(w.library.songs) == 1, "demo song missing"
        s = w.new_song()
        w.title.setText("Smoke Test Song")
        w._title_changed("Smoke Test Song")
        w.overview.bpm.setValue(150)
        w.overview.tonic.setCurrentIndex(10)  # A
        w.overview.scale.setCurrentText("Minor")
        assert s.bpm == 150 and s.key_tonic == 9 and s.camelot == "8A", (s.bpm, s.key_tonic, s.camelot)
        for i in range(4):
            w.tabs.setCurrentIndex(i)
            app.processEvents()
        w.lyrics.add_section("Hook")
        w.lyrics.editor.setPlainText("I been on my grind every single night\nStackin up the paper till the numbers right")
        app.processEvents()
        assert s.lyrics and "grind" in s.lyrics[0].text
        w.arrangement.apply_template(next(iter(__import__("chaz_songbook.ui.arrangement_tab",
                                                           fromlist=["TEMPLATES"]).TEMPLATES)))
        assert s.total_bars == 64, s.total_bars
        w.arrangement.move_block(0, 2)
        log(f"song: {s.total_bars} bars, {s.total_seconds:.1f}s, camelot {s.camelot}")
        # multimedia: metronome + player + device query must not crash (CI may have no audio device)
        from PySide6.QtMultimedia import QMediaDevices
        from .audio import Player, write_click_wav
        log(f"audio in: {len(QMediaDevices.audioInputs())} out: {len(QMediaDevices.audioOutputs())}")
        w.metronome.set_tempo(150)
        w.metronome.start()
        pl = Player()
        pl.play(write_click_wav(tmp / "beep.wav", 880, ms=200))
        t_end = __import__("time").monotonic() + 0.6
        while __import__("time").monotonic() < t_end:
            app.processEvents()
        w.metronome.stop()
        pl.stop()
        log("multimedia ok")
        out = tmp / "exports"
        out.mkdir()
        for ext in ("pdf", "md", "txt"):
            p = ex.export_song(s, out / f"song.{ext}")
            assert p.stat().st_size > 200, (ext, p.stat().st_size)
        w.library.export_json(out / "all.json")
        w.save_now()
        lib2 = Library(tmp / "data", create_demo=False)
        assert lib2.get(s.id).title == "Smoke Test Song"
        assert lib2.get(s.id).total_bars == 64
        log(f"exports ok: {sorted(x.name for x in out.iterdir())}")
        w.close()
        app.processEvents()
        log("SMOKE OK")
        code = 0
    except Exception:  # noqa: BLE001
        log("SMOKE FAILED\n" + traceback.format_exc())
        code = 1
    if out_file:
        Path(out_file).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return code


def run_screenshots(dest: str) -> int:
    from PySide6.QtCore import QTimer
    from .screenshots import make_screenshots
    app = _make_app(sys.argv[:1])
    make_screenshots(app, Path(dest))
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(prog="ChazSongBook", description=APP_NAME)
    ap.add_argument("--data-dir", help="use this library folder (overrides the saved setting)")
    ap.add_argument("--smoke-test", action="store_true", help="self-test the UI and exit")
    ap.add_argument("--smoke-out", help="write smoke test log to this file")
    ap.add_argument("--screenshots", metavar="DIR", help="render UI screenshots and exit")
    ap.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    args, _unknown = ap.parse_known_args(argv)
    if args.smoke_test:
        return run_smoke_test(args.smoke_out)
    if args.screenshots:
        return run_screenshots(args.screenshots)

    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QMessageBox
    from .paths import config_dir
    app = _make_app(sys.argv[:1])
    config_dir().mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(config_dir() / "songbook.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(200):
        QMessageBox.information(None, APP_NAME, f"{APP_NAME} is already open.")
        return 0
    try:
        w = _open_window(Path(args.data_dir) if args.data_dir else None)
    except Exception as e:  # noqa: BLE001
        QMessageBox.critical(None, APP_NAME, f"Couldn't open your library:\n{e}")
        return 1
    w.show()
    rc = app.exec()
    lock.unlock()
    return rc


if __name__ == "__main__":
    sys.exit(main())
