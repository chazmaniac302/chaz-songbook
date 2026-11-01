"""Voice memos: record the mic to WAV, list, play, rename, delete."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QInputDialog, QLabel, QListWidget, QListWidgetItem, QMessageBox, QProgressBar,
                               QPushButton, QVBoxLayout, QWidget)

from .. import music
from ..audio import Player, Recorder, wav_duration
from ..model import VoiceMemo
from . import theme
from .common import card, hbox, muted, show_in_explorer
from .widgets import relative_time


class MemosTab(QWidget):
    changed = Signal()

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.song = None
        self.recorder = Recorder(self)
        self.player = Player(self)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(14)

        c, lay = card("Record an idea")
        self.rec_btn = QPushButton("●  Record")
        self.rec_btn.setObjectName("Tap")
        self.rec_btn.setMinimumHeight(44)
        self.rec_btn.setMinimumWidth(150)
        self.rec_btn.setFont(theme.head_font(16))
        self.elapsed = QLabel("0:00")
        self.elapsed.setFont(theme.head_font(22))
        self.level = QProgressBar()
        self.level.setRange(0, 100)
        self.level.setTextVisible(False)
        self.level.setFixedHeight(10)
        self.level.setStyleSheet(f"""QProgressBar{{background:{theme.PANEL2};border:1px solid {theme.BORDER};border-radius:5px;}}
            QProgressBar::chunk{{border-radius:4px;background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 {theme.GOLD_DIM}, stop:0.7 {theme.GOLD}, stop:1 {theme.CRIMSON_HI});}}""")
        self.click_while = QPushButton("♩ Click while recording")
        self.click_while.setCheckable(True)
        self.click_while.setToolTip("Play the metronome at the song BPM while you record (use headphones)")
        lay.addWidget(hbox(self.rec_btn, 14, self.elapsed, 14, self.level, 10, self.click_while))
        hint = muted("Records your default microphone as a WAV file saved next to your library "
                     "(memos folder). Hum melodies, flows, ad-libs.")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        root.addWidget(c)

        c, lay = card("Memos for this song")
        self.list = QListWidget()
        lay.addWidget(self.list, 1)
        self.play_btn = QPushButton("▶  Play")
        self.play_btn.setObjectName("Primary")
        self.stop_btn = QPushButton("■  Stop")
        self.rename_btn = QPushButton("Rename")
        self.reveal_btn = QPushButton("Show in Explorer")
        self.del_btn = QPushButton("Delete")
        self.del_btn.setObjectName("Danger")
        lay.addWidget(hbox(self.play_btn, self.stop_btn, None, self.rename_btn, self.reveal_btn, self.del_btn))
        root.addWidget(c, 1)

        self.rec_btn.clicked.connect(self.toggle_record)
        self.recorder.levelChanged.connect(lambda v: self.level.setValue(int(v * 100)))
        self.recorder.elapsedChanged.connect(lambda s: self.elapsed.setText(music.format_duration(s)))
        self.play_btn.clicked.connect(self._play)
        self.list.itemDoubleClicked.connect(lambda *_: self._play())
        self.stop_btn.clicked.connect(self.player.stop)
        self.rename_btn.clicked.connect(self._rename)
        self.reveal_btn.clicked.connect(self._reveal)
        self.del_btn.clicked.connect(self._delete)

    def load(self, song):
        if self.recorder.recording:
            self.toggle_record()
        self.player.stop()
        self.song = song
        self._fill()

    def _abs(self, memo) -> Path:
        p = Path(memo.file)
        return p if p.is_absolute() else self.ctx.library.data_dir / p

    def _fill(self):
        self.list.clear()
        for m in self.song.memos:
            exists = self._abs(m).exists()
            it = QListWidgetItem(f"{m.name}    ·  {music.format_duration(m.duration)}  ·  {relative_time(m.created)}"
                                 + ("" if exists else "   (file missing)"))
            it.setData(Qt.ItemDataRole.UserRole, m.id)
            self.list.addItem(it)
        if self.song.memos:
            self.list.setCurrentRow(len(self.song.memos) - 1)
        else:
            it = QListWidgetItem("No memos yet — hit Record and hum the idea before it's gone.")
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(it)

    def toggle_record(self):
        if self.recorder.recording:
            path = self.recorder.stop()
            if self.click_while.isChecked():
                self.ctx.metronome.stop()
            self.rec_btn.setText("●  Record")
            if path and path.exists():
                rel = path.relative_to(self.ctx.library.data_dir)
                n = len(self.song.memos) + 1
                self.song.memos.append(VoiceMemo(name=f"Idea {n}", file=rel.as_posix(), duration=wav_duration(path)))
                self._fill()
                self.changed.emit()
            return
        if not self.song:
            return
        d = self.ctx.library.memo_dir / self.song.id
        path = d / f"memo-{datetime.now():%Y%m%d-%H%M%S}.wav"
        try:
            self.recorder.start(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Can't record", str(e))
            return
        if self.click_while.isChecked():
            self.ctx.metronome.set_tempo(self.song.bpm, music.parse_time_signature(self.song.time_signature)[0])
            self.ctx.metronome.start()
        self.rec_btn.setText("■  Stop")

    def _current(self):
        i = self.list.currentRow()
        return self.song.memos[i] if self.song and 0 <= i < len(self.song.memos) else None

    def _play(self):
        m = self._current()
        if m:
            p = self._abs(m)
            if not p.exists():
                QMessageBox.warning(self, "Missing file", f"Can't find {p}")
                return
            self.player.play(p)

    def _rename(self):
        m = self._current()
        if not m:
            return
        name, ok = QInputDialog.getText(self, "Rename memo", "Name:", text=m.name)
        if ok and name.strip():
            m.name = name.strip()
            self._fill()
            self.changed.emit()

    def _reveal(self):
        m = self._current()
        show_in_explorer(self._abs(m) if m else self.ctx.library.memo_dir)

    def _delete(self):
        m = self._current()
        if not m:
            return
        if QMessageBox.question(self, "Delete memo", f"Delete “{m.name}”? The WAV file is removed too.") \
                != QMessageBox.StandardButton.Yes:
            return
        self.player.stop()
        try:
            self._abs(m).unlink(missing_ok=True)
        except OSError:
            pass
        self.song.memos.remove(m)
        self._fill()
        self.changed.emit()

    def shutdown(self):
        if self.recorder.recording:
            self.toggle_record()
        self.player.stop()
