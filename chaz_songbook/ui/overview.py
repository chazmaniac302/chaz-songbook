"""Overview tab: tempo, key, details, beat files, references, notes."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from .. import music
from ..model import Reference, SUGGESTED_TAGS
from . import theme
from .common import card, hbox, muted, open_path, show_in_explorer
from .widgets import TagEditor


class OverviewTab(QWidget):
    changed = Signal()
    tempoChanged = Signal()

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.song = None
        self._loading = False
        self.tap = music.TapTempo()

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        grid = QGridLayout(body)
        grid.setContentsMargins(22, 18, 22, 22)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        # ---- tempo & key ---------------------------------------------------
        c, lay = card("Tempo & Key")
        self.bpm = QDoubleSpinBox()
        self.bpm.setRange(20, 400)
        self.bpm.setDecimals(1)
        self.bpm.setSuffix("  BPM")
        self.bpm.setKeyboardTracking(False)
        self.bpm.setMinimumWidth(120)
        self.bpm.setFont(theme.head_font(20))
        self.tap_btn = QPushButton("TAP")
        self.tap_btn.setObjectName("Tap")
        self.tap_btn.setToolTip("Tap along to set the BPM (or press T while this tab is focused)")
        self.tap_btn.setShortcut("T")
        self.half_btn = QPushButton("½×")
        self.double_btn = QPushButton("2×")
        self.half_btn.setToolTip("Half-time")
        self.double_btn.setToolTip("Double-time")
        self.metro_btn = QPushButton("♩ Click")
        self.metro_btn.setCheckable(True)
        self.metro_btn.setToolTip("Metronome at the song BPM")
        lay.addWidget(hbox(self.bpm, self.tap_btn, self.half_btn, self.double_btn, self.metro_btn, None))
        self.tap_info = muted("")
        lay.addWidget(self.tap_info)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(12)
        self.tonic = QComboBox()
        self.tonic.addItem("— none —", None)
        for i, n in enumerate(music.NOTE_LABELS):
            self.tonic.addItem(n, i)
        self.scale = QComboBox()
        self.scale.addItems(music.SCALE_NAMES)
        self.ts = QComboBox()
        self.ts.setEditable(True)
        self.ts.addItems(music.TIME_SIGNATURES)
        form.addRow(muted("Key"), hbox(self.tonic, self.scale, None))
        form.addRow(muted("Time sig"), hbox(self.ts, None))
        lay.addLayout(form)

        self.key_big = QLabel("—")
        self.key_big.setFont(theme.head_font(26))
        self.key_big.setStyleSheet(f"color:{theme.TEXT}")
        self.camelot_badge = QLabel("")
        self.camelot_badge.setObjectName("Pill")
        self.camelot_badge.setStyleSheet(
            f"background:#3A0C16;border:1px solid {theme.CRIMSON};color:#FFD9DF;border-radius:10px;padding:3px 10px;font-weight:700;")
        lay.addWidget(hbox(self.key_big, self.camelot_badge, None))
        self.relative = QLabel("")
        self.relative.setStyleSheet(f"color:{theme.GOLD}")
        self.notes_lbl = muted("")
        self.compat = muted("")
        self.timing = muted("")
        for w in (self.relative, self.notes_lbl, self.compat, self.timing):
            w.setWordWrap(True)
            lay.addWidget(w)
        grid.addWidget(c, 0, 0)

        # ---- details -------------------------------------------------------
        c, lay = card("Details")
        f2 = QFormLayout()
        f2.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        f2.setHorizontalSpacing(12)
        self.artist = QLineEdit()
        self.artist.setPlaceholderText("Chazmaniac")
        self.features = QLineEdit()
        self.features.setPlaceholderText("feat. …")
        f2.addRow(muted("Artist"), self.artist)
        f2.addRow(muted("Features"), self.features)
        lay.addLayout(f2)
        lay.addWidget(muted("Mood / genre tags"))
        self.tags = TagEditor()
        lay.addWidget(self.tags)
        self.created_lbl = muted("")
        lay.addWidget(self.created_lbl)
        grid.addWidget(c, 0, 1)

        # ---- beat files ----------------------------------------------------
        c, lay = card("Beat files  (FL .flp, Maschine .mxprj, audio…)")
        self.files = QListWidget()
        self.files.setMinimumHeight(96)
        self.files.setToolTip("Double-click to open in its app (FL Studio, Maschine, your player…)")
        lay.addWidget(self.files)
        self.add_file_btn = QPushButton("+ File…")
        self.add_folder_btn = QPushButton("+ Folder…")
        self.open_file_btn = QPushButton("Open")
        self.reveal_btn = QPushButton("Show in Explorer")
        self.rm_file_btn = QPushButton("Remove")
        self.rm_file_btn.setObjectName("Danger")
        lay.addWidget(hbox(self.add_file_btn, self.add_folder_btn, None, self.open_file_btn, self.reveal_btn,
                           self.rm_file_btn))
        grid.addWidget(c, 1, 0)

        # ---- references ----------------------------------------------------
        c, lay = card("Reference tracks & links")
        self.refs = QListWidget()
        self.refs.setMinimumHeight(96)
        self.refs.setToolTip("Double-click to open the link")
        lay.addWidget(self.refs)
        self.ref_title = QLineEdit()
        self.ref_title.setPlaceholderText("Artist – Song / what you like about it")
        self.ref_url = QLineEdit()
        self.ref_url.setPlaceholderText("https://… (YouTube, Spotify, SoundCloud)")
        self.add_ref_btn = QPushButton("Add")
        self.add_ref_btn.setObjectName("Primary")
        self.rm_ref_btn = QPushButton("Remove")
        self.rm_ref_btn.setObjectName("Danger")
        lay.addWidget(self.ref_title)
        lay.addWidget(hbox(self.ref_url, self.add_ref_btn, self.rm_ref_btn))
        grid.addWidget(c, 1, 1)

        # ---- notes ---------------------------------------------------------
        c, lay = card("Notes")
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Sound selection, mix notes, who to send it to, ideas for the video…")
        self.notes.setMinimumHeight(150)
        lay.addWidget(self.notes)
        grid.addWidget(c, 2, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(3, 1)

        # ---- wiring --------------------------------------------------------
        self.bpm.valueChanged.connect(self._on_bpm)
        self.tap_btn.clicked.connect(self._on_tap)
        self.half_btn.clicked.connect(lambda: self.bpm.setValue(music.halftime(self.bpm.value())))
        self.double_btn.clicked.connect(lambda: self.bpm.setValue(music.doubletime(self.bpm.value())))
        self.metro_btn.toggled.connect(self._on_metro)
        self.tonic.currentIndexChanged.connect(self._on_key)
        self.scale.currentIndexChanged.connect(self._on_key)
        self.ts.currentTextChanged.connect(self._on_ts)
        self.artist.textEdited.connect(lambda t: self._set("artist", t))
        self.features.textEdited.connect(lambda t: self._set("features", t))
        self.tags.changed.connect(lambda tags: self._set("tags", tags))
        self.notes.textChanged.connect(lambda: self._set("notes", self.notes.toPlainText()))
        self.add_file_btn.clicked.connect(self._add_file)
        self.add_folder_btn.clicked.connect(self._add_folder)
        self.open_file_btn.clicked.connect(self._open_file)
        self.reveal_btn.clicked.connect(self._reveal_file)
        self.rm_file_btn.clicked.connect(self._remove_file)
        self.files.itemDoubleClicked.connect(lambda *_: self._open_file())
        self.add_ref_btn.clicked.connect(self._add_ref)
        self.ref_url.returnPressed.connect(self._add_ref)
        self.rm_ref_btn.clicked.connect(self._remove_ref)
        self.refs.itemDoubleClicked.connect(self._open_ref)
        self.ctx.metronome.beat.connect(self._flash)

    # ---------------------------------------------------------------------
    def load(self, song):
        self._loading = True
        self.song = song
        self.tap.reset()
        self.tap_info.setText("Tap at least twice to set the tempo.")
        self.bpm.setValue(song.bpm or 140)
        self.tonic.setCurrentIndex(0 if song.key_tonic is None else song.key_tonic + 1)
        self.scale.setCurrentText(song.key_scale)
        self.ts.setCurrentText(song.time_signature)
        self.artist.setText(song.artist)
        self.features.setText(song.features)
        self.tags.set_tags(song.tags)
        self.tags.set_suggestions(list(self.ctx.library.all_tags()) + SUGGESTED_TAGS)
        self.notes.setPlainText(song.notes)
        self._fill_files()
        self._fill_refs()
        from .widgets import relative_time
        self.created_lbl.setText(f"Created {relative_time(song.created)} · edited {relative_time(song.updated)}")
        self._loading = False
        self._refresh_key()

    def _set(self, attr, value):
        if self._loading or not self.song:
            return
        setattr(self.song, attr, value)
        self.changed.emit()

    def _on_bpm(self, v):
        if self._loading or not self.song:
            return
        self.song.bpm = round(float(v), 2)
        self._refresh_key()
        self.ctx.metronome.set_tempo(self.song.bpm, music.parse_time_signature(self.song.time_signature)[0])
        self.changed.emit()
        self.tempoChanged.emit()

    def _on_tap(self):
        bpm = self.tap.tap()
        n = len(self.tap.taps)
        if bpm:
            bpm = max(20.0, min(400.0, bpm))
            self.bpm.setValue(round(bpm))
            self.tap_info.setText(f"{n} taps → {bpm:.1f} BPM (rounded to {round(bpm)}). Keep tapping to refine.")
        else:
            self.tap_info.setText("Tap again…")

    def _on_metro(self, on):
        m = self.ctx.metronome
        if on and self.song:
            m.set_tempo(self.song.bpm, music.parse_time_signature(self.song.time_signature)[0])
            m.start()
        else:
            m.stop()

    def stop_metronome(self):
        self.metro_btn.setChecked(False)

    def _flash(self, n):
        self.metro_btn.setText("♩ Click  " + "●" * (n + 1) if self.metro_btn.isChecked() else "♩ Click")

    def _on_key(self, *_):
        if self._loading or not self.song:
            return
        self.song.key_tonic = self.tonic.currentData()
        self.song.key_scale = self.scale.currentText()
        self._refresh_key()
        self.changed.emit()

    def _on_ts(self, text):
        if self._loading or not self.song:
            return
        num, den = music.parse_time_signature(text)
        if text.strip() == f"{num}/{den}":
            self.song.time_signature = text.strip()
            self._refresh_key()
            self.changed.emit()
            self.tempoChanged.emit()

    def _refresh_key(self):
        s = self.song
        if not s:
            return
        pc, sc = s.key_tonic, s.key_scale
        self.key_big.setText(music.key_name(pc, sc) if pc is not None else "No key set")
        code = music.camelot(pc, sc)
        self.camelot_badge.setText(f"Camelot {code}" if code else "")
        self.camelot_badge.setVisible(bool(code))
        self.relative.setText(music.relative_label(pc, sc))
        notes = music.scale_notes(pc, sc)
        self.notes_lbl.setText("Notes: " + "  ".join(notes) if notes else "Pick a key to see its notes, relative key and Camelot code.")
        comp = music.compatible_camelot(code)
        self.compat.setText("Mixes well with: " + ", ".join(comp[1:]) if comp else "")
        if s.bpm:
            spb = music.seconds_per_bar(s.bpm, s.time_signature)
            self.timing.setText(f"1 beat = {music.ms_per_beat(s.bpm):.0f} ms · 1 bar = {spb:.2f} s · "
                                f"16 bars = {music.format_duration(spb * 16)} · half-time {music.halftime(s.bpm):g} · "
                                f"double {music.doubletime(s.bpm):g}")

    # ---- beat files --------------------------------------------------
    def _fill_files(self):
        self.files.clear()
        for p in self.song.beat_files:
            parent = str(Path(p).parent)
            it = QListWidgetItem(("▣  " if Path(p).suffix == "" else "♪  ") + Path(p).name + f"     —  {parent}")
            it.setData(Qt.ItemDataRole.UserRole, p)
            it.setToolTip(p + ("" if Path(p).exists() else "\n(not found on this PC)"))
            if not Path(p).exists():
                it.setForeground(Qt.GlobalColor.gray)
            self.files.addItem(it)

    def _add_paths(self, paths):
        for p in paths:
            if p and p not in self.song.beat_files:
                self.song.beat_files.append(p)
        self._fill_files()
        self.changed.emit()

    def _add_file(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Add beat / project files", self.ctx.settings.get("last_beat_dir", ""),
            "Beats & projects (*.flp *.mxprj *.mxgrp *.wav *.mp3 *.flac *.aif *.aiff *.ogg *.m4a *.mid *.zip);;All files (*)")
        if files:
            self.ctx.settings.set("last_beat_dir", str(Path(files[0]).parent))
            self._add_paths(files)

    def _add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Add beat folder", self.ctx.settings.get("last_beat_dir", ""))
        if d:
            self._add_paths([d])

    def _selected_file(self):
        it = self.files.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _open_file(self):
        p = self._selected_file()
        if p and not Path(p).exists():
            QMessageBox.warning(self, "Not found", f"Can't find:\n{p}")
        elif p:
            open_path(p)

    def _reveal_file(self):
        p = self._selected_file()
        if p and not show_in_explorer(p):
            QMessageBox.warning(self, "Not found", f"Can't find:\n{p}")

    def _remove_file(self):
        p = self._selected_file()
        if p:
            self.song.beat_files.remove(p)
            self._fill_files()
            self.changed.emit()

    # ---- references --------------------------------------------------
    def _fill_refs(self):
        self.refs.clear()
        for r in self.song.references:
            it = QListWidgetItem(f"♫  {r.title or r.url}" + (f"   ·   {r.url}" if r.title and r.url else ""))
            it.setToolTip(r.url)
            self.refs.addItem(it)

    def _add_ref(self):
        t, u = self.ref_title.text().strip(), self.ref_url.text().strip()
        if not (t or u):
            return
        if u and "://" not in u and "." in u:
            u = "https://" + u
        self.song.references.append(Reference(t, u))
        self.ref_title.clear()
        self.ref_url.clear()
        self._fill_refs()
        self.changed.emit()

    def _remove_ref(self):
        i = self.refs.currentRow()
        if 0 <= i < len(self.song.references):
            del self.song.references[i]
            self._fill_refs()
            self.changed.emit()

    def _open_ref(self, *_):
        i = self.refs.currentRow()
        if 0 <= i < len(self.song.references) and self.song.references[i].url:
            QDesktopServices.openUrl(QUrl(self.song.references[i].url))
