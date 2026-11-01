"""Renders real UI screenshots from a sample library (used for docs / CI artifacts)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .model import ArrangementBlock, LyricSection, Reference, Song, demo_song

SAMPLES = [
    dict(title="Late Night Pressure", bpm=88, key_tonic=5, key_scale="Minor", status="Recording",
         tags=["rnb", "love"], favorite=True, features="feat. Nia"),
    dict(title="No Brakes", bpm=160, key_tonic=7, key_scale="Minor", status="Mixing", tags=["drill", "hype"]),
    dict(title="Velvet Rope", bpm=96, key_tonic=3, key_scale="Major", status="Done", tags=["rnb", "club"]),
    dict(title="Basement Tapes 3", bpm=92, key_tonic=2, key_scale="Dorian", status="Idea", tags=["boom bap"]),
    dict(title="Ice Cold Summer", bpm=145, key_tonic=11, key_scale="Minor", status="Writing", tags=["trap"]),
    dict(title="Mama's Prayer", bpm=72, key_tonic=10, key_scale="Major", status="Idea", tags=["soul", "sad"]),
]


def build_sample_library(data_dir: Path):
    from .store import Library
    lib = Library(data_dir, create_demo=False)
    demo = demo_song()
    demo.beat_files = [r"E:\FL Projects\Gold Teeth Sunrise.flp", r"E:\Bounces\Gold Teeth Sunrise v3.wav"]
    demo.references.append(Reference("808 Mafia-style bells", "https://soundcloud.com/"))
    for i, kw in enumerate(SAMPLES):
        s = Song(artist="Chazmaniac", **kw)
        s.updated = f"2026-10-{30 - i:02d}T18:00:00+00:00"
        s.lyrics = [LyricSection("Hook", "Hook", "Placeholder hook line\nSecond line")]
        s.arrangement = [ArrangementBlock("Intro", "Intro", 4), ArrangementBlock("Hook", "Hook", 8),
                         ArrangementBlock("Verse", "Verse 1", 16), ArrangementBlock("Hook", "Hook", 8)]
        lib.add(s)
    # two short generated "memos" so the memo list isn't empty
    from .audio import wav_duration, write_click_wav
    from .model import VoiceMemo
    mdir = lib.memo_dir / demo.id
    mdir.mkdir(parents=True, exist_ok=True)
    for name, f, ms in (("Hook melody hum", 440, 1800), ("Verse flow idea", 330, 2400)):
        p = write_click_wav(mdir / f"{name.replace(' ', '-').lower()}.wav", f, ms=ms, volume=0.3)
        demo.memos.append(VoiceMemo(name=name, file=p.relative_to(lib.data_dir).as_posix(),
                                    duration=wav_duration(p), created="2026-10-31T21:15:00+00:00"))
    lib.add(demo)
    lib.save(backup=False)
    return lib, demo


def make_screenshots(app, dest: Path) -> list[Path]:
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QTextCursor
    from .store import Settings
    from .ui.main_window import MainWindow

    dest.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="chaz-shots-"))
    os.environ["CHAZ_SONGBOOK_HOME"] = str(tmp / "cfg")
    lib, demo = build_sample_library(tmp / "data")
    w = MainWindow(Settings(tmp / "cfg"), lib)
    w.resize(1440, 900)
    w.show()
    w.refresh_list(select_id=demo.id)

    def settle(n=8):
        for _ in range(n):
            app.processEvents()

    out = []
    settle()
    w.tabs.setCurrentIndex(0)
    settle()
    out.append(dest / "01-main-overview.png")
    w.grab().save(str(out[-1]))

    w.tabs.setCurrentIndex(1)
    w.lyrics.sections.setCurrentRow(1)  # Hook
    settle()
    c = w.lyrics.editor.textCursor()
    c.movePosition(QTextCursor.MoveOperation.Start)
    c.movePosition(QTextCursor.MoveOperation.EndOfBlock)
    w.lyrics.editor.setTextCursor(c)
    w.lyrics.editor.setFocus()
    w.lyrics.rhyme._lookup()
    settle()
    out.append(dest / "02-lyrics-rhymes.png")
    w.grab().save(str(out[-1]))

    w.tabs.setCurrentIndex(2)
    w.arrangement.list.setCurrentRow(2)
    settle()
    out.append(dest / "03-arrangement.png")
    w.grab().save(str(out[-1]))

    w.tabs.setCurrentIndex(3)
    settle()
    out.append(dest / "04-voice-memos.png")
    w.grab().save(str(out[-1]))
    w.close()
    settle()
    return out
