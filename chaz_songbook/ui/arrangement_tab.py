"""Arrangement tab: block timeline, section list with drag reorder, per-section notes."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                               QSpinBox, QVBoxLayout, QWidget)

from .. import music
from ..model import DEFAULT_BARS, SECTION_COLORS, SECTION_TYPES, ArrangementBlock
from . import theme
from .common import card, hbox, muted
from .widgets import TimelineWidget

TEMPLATES = {
    "Trap banger (Intro · Hook · Verse · Hook · Verse · Hook · Outro)":
        [("Intro", 4), ("Hook", 8), ("Verse", 16), ("Hook", 8), ("Verse", 16), ("Hook", 8), ("Outro", 4)],
    "R&B (Intro · Verse · Pre · Hook · Verse · Pre · Hook · Bridge · Hook · Outro)":
        [("Intro", 4), ("Verse", 16), ("Pre-Hook", 4), ("Hook", 8), ("Verse", 16), ("Pre-Hook", 4), ("Hook", 8),
         ("Bridge", 8), ("Hook", 8), ("Outro", 4)],
    "Boom bap (Intro · Verse · Hook · Verse · Hook · Verse · Outro)":
        [("Intro", 8), ("Verse", 16), ("Hook", 8), ("Verse", 16), ("Hook", 8), ("Verse", 16), ("Outro", 8)],
    "Short-form / TikTok cut (Hook · Verse 8 · Hook)":
        [("Hook", 8), ("Verse", 8), ("Hook", 8)],
}


class ArrangementTab(QWidget):
    changed = Signal()

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.song = None
        self._loading = False
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(14)

        c, lay = card(None)
        self.total_lbl = QLabel("")
        self.total_lbl.setFont(theme.head_font(18))
        self.total_sub = muted("")
        tmpl = QPushButton("Templates")
        tm = QMenu(self)
        for name in TEMPLATES:
            tm.addAction(name, lambda n=name: self.apply_template(n))
        tmpl.setMenu(tm)
        self.from_lyrics_btn = QPushButton("Build from lyric sections")
        self.from_lyrics_btn.setToolTip("Create one block per lyric section (bars = lines written)")
        lay.addWidget(hbox(self.total_lbl, 12, self.total_sub, None, self.from_lyrics_btn, tmpl))
        self.timeline = TimelineWidget()
        self.timeline.setToolTip("Click to select · drag a block to move it")
        lay.addWidget(self.timeline)
        root.addWidget(c)

        row = QHBoxLayout()
        row.setSpacing(14)
        c, lay = card("Sections")
        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list.setDefaultDropAction(Qt.DropAction.MoveAction)
        lay.addWidget(self.list, 1)
        self.add_btn = QPushButton("+ Add")
        self.add_btn.setObjectName("Primary")
        am = QMenu(self)
        for t in SECTION_TYPES:
            am.addAction(t, lambda t=t: self.add_block(t))
        self.add_btn.setMenu(am)
        self.up_btn = QPushButton("▲")
        self.down_btn = QPushButton("▼")
        self.dup_btn = QPushButton("Duplicate")
        self.del_btn = QPushButton("Delete")
        self.del_btn.setObjectName("Danger")
        lay.addWidget(hbox(self.add_btn, self.up_btn, self.down_btn, None, self.dup_btn, self.del_btn))
        row.addWidget(c, 3)

        c, lay = card("Section details")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(12)
        self.type_combo = QComboBox()
        self.type_combo.addItems(SECTION_TYPES)
        self.label_edit = QLineEdit()
        self.bars = QSpinBox()
        self.bars.setRange(1, 256)
        self.bars.setSuffix(" bars")
        self.bars.setMinimumWidth(90)
        quick = []
        for n in (2, 4, 8, 12, 16, 24, 32):
            b = QPushButton(str(n))
            b.setFixedWidth(38)
            b.clicked.connect(lambda _=False, n=n: self.bars.setValue(n))
            quick.append(b)
        form.addRow(muted("Type"), self.type_combo)
        form.addRow(muted("Name"), self.label_edit)
        form.addRow(muted("Length"), hbox(self.bars, *quick, None, spacing=4))
        lay.addLayout(form)
        self.pos_lbl = QLabel("")
        self.pos_lbl.setStyleSheet(f"color:{theme.GOLD}")
        lay.addWidget(self.pos_lbl)
        lay.addWidget(muted("Production notes"))
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("e.g. drop the 808, add hat roll on bar 4, mute kick, riser into hook…")
        lay.addWidget(self.notes, 1)
        row.addWidget(c, 4)
        root.addLayout(row, 1)

        self.timeline.selected.connect(self.list.setCurrentRow)
        self.timeline.moved.connect(self.move_block)
        self.list.currentRowChanged.connect(self._select)
        self.list.model().rowsMoved.connect(self._rows_moved)
        self.up_btn.clicked.connect(lambda: self._nudge(-1))
        self.down_btn.clicked.connect(lambda: self._nudge(1))
        self.dup_btn.clicked.connect(self._duplicate)
        self.del_btn.clicked.connect(self._delete)
        self.from_lyrics_btn.clicked.connect(self._from_lyrics)
        self.type_combo.currentTextChanged.connect(self._type_changed)
        self.label_edit.textEdited.connect(self._label_changed)
        self.bars.valueChanged.connect(self._bars_changed)
        self.notes.textChanged.connect(self._notes_changed)

    # ---------------------------------------------------------------------
    def load(self, song):
        self.song = song
        self._refresh(select=0 if song.arrangement else -1)

    def refresh_tempo(self):
        if self.song:
            self._refresh(select=self.list.currentRow())

    def _refresh(self, select=None):
        s = self.song
        cur = self.list.currentRow() if select is None else select
        self._loading = True
        self.list.blockSignals(True)
        self.list.clear()
        starts = s.block_start_seconds()
        bar = 1
        for b, t in zip(s.arrangement, starts):
            it = QListWidgetItem(f"{b.label or b.type}    ·  {b.bars} bars   ·  bar {bar}  ·  {music.format_duration(t)}"
                                 + ("    ✎" if b.notes.strip() else ""))
            it.setData(Qt.ItemDataRole.UserRole, b.id)
            it.setData(Qt.ItemDataRole.DecorationRole, QColor(b.color))
            it.setToolTip(b.notes or "")
            self.list.addItem(it)
            bar += b.bars
        self.list.blockSignals(False)
        self._loading = False
        cur = min(cur, len(s.arrangement) - 1)
        self.list.setCurrentRow(cur)
        self._select(cur)
        self.total_lbl.setText(f"{s.total_bars} BARS  ·  {music.format_duration(s.total_seconds)}")
        self.total_sub.setText(f"at {s.bpm:g} BPM in {s.time_signature} · {len(s.arrangement)} sections")
        self.timeline.set_data(s.arrangement, s.bpm, s.time_signature, cur)

    def current(self):
        i = self.list.currentRow()
        return self.song.arrangement[i] if self.song and 0 <= i < len(self.song.arrangement) else None

    def _select(self, i):
        b = self.current()
        self._loading = True
        for w in (self.type_combo, self.label_edit, self.bars, self.notes, self.dup_btn, self.del_btn,
                  self.up_btn, self.down_btn):
            w.setEnabled(b is not None)
        if b:
            self.type_combo.setCurrentText(b.type)
            self.label_edit.setText(b.label)
            self.bars.setValue(b.bars)
            self.notes.setPlainText(b.notes)
            self._update_pos()
        else:
            self.label_edit.clear()
            self.notes.clear()
            self.pos_lbl.setText("")
        self._loading = False
        self.timeline.current = i
        self.timeline.update()

    def _update_pos(self):
        i = self.list.currentRow()
        if i < 0:
            return
        s = self.song
        start_bar = sum(b.bars for b in s.arrangement[:i]) + 1
        start_t = s.block_start_seconds()[i]
        b = s.arrangement[i]
        dur = music.bars_to_seconds(b.bars, s.bpm, s.time_signature)
        self.pos_lbl.setText(f"Bars {start_bar}–{start_bar + b.bars - 1}  ·  starts {music.format_duration(start_t)}"
                             f"  ·  lasts {music.format_duration(dur)}")

    def add_block(self, t="Verse"):
        i = self.list.currentRow()
        pos = i + 1 if i >= 0 else len(self.song.arrangement)
        label = self.song.next_section_label(t, self.song.arrangement)
        self.song.arrangement.insert(pos, ArrangementBlock(type=t, label=label, bars=DEFAULT_BARS.get(t, 8)))
        self._refresh(select=pos)
        self.changed.emit()

    def apply_template(self, name):
        if self.song.arrangement and QMessageBox.question(
                self, "Replace arrangement", "Replace the current arrangement with this template?") \
                != QMessageBox.StandardButton.Yes:
            return
        blocks = []
        for t, bars in TEMPLATES[name]:
            blocks.append(ArrangementBlock(type=t, label=self.song.next_section_label(t, blocks), bars=bars))
        self.song.arrangement = blocks
        self._refresh(select=0)
        self.changed.emit()

    def _from_lyrics(self):
        if not self.song.lyrics:
            QMessageBox.information(self, "No lyric sections", "Add some sections in the Lyrics tab first.")
            return
        if self.song.arrangement and QMessageBox.question(
                self, "Replace arrangement", "Replace the current arrangement with one block per lyric section?") \
                != QMessageBox.StandardButton.Yes:
            return
        self.song.arrangement = self.song.arrangement_from_lyrics()
        self._refresh(select=0)
        self.changed.emit()

    def move_block(self, src, dst):
        arr = self.song.arrangement
        if not (0 <= src < len(arr)) or not (0 <= dst < len(arr)):
            return
        arr.insert(dst, arr.pop(src))
        self._refresh(select=dst)
        self.changed.emit()

    def _nudge(self, d):
        i = self.list.currentRow()
        if 0 <= i + d < len(self.song.arrangement):
            self.move_block(i, i + d)

    def _rows_moved(self, *_):
        by_id = {b.id: b for b in self.song.arrangement}
        order = [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())]
        self.song.arrangement = [by_id[x] for x in order if x in by_id]
        self._refresh()
        self.changed.emit()

    def _duplicate(self):
        b = self.current()
        if b:
            i = self.list.currentRow()
            self.song.arrangement.insert(i + 1, ArrangementBlock(b.type, b.label, b.bars, b.notes))
            self._refresh(select=i + 1)
            self.changed.emit()

    def _delete(self):
        i = self.list.currentRow()
        if 0 <= i < len(self.song.arrangement):
            del self.song.arrangement[i]
            self._refresh(select=max(0, i - 1) if self.song.arrangement else -1)
            self.changed.emit()

    def _type_changed(self, t):
        b = self.current()
        if self._loading or not b:
            return
        old = b.type
        b.type = t
        if not b.label or b.label.startswith(old):
            b.label = self.song.next_section_label(t, [x for x in self.song.arrangement if x is not b])
        self._refresh()
        self.changed.emit()

    def _label_changed(self, text):
        b = self.current()
        if self._loading or not b:
            return
        b.label = text
        self._update_item()
        self.changed.emit()

    def _bars_changed(self, v):
        b = self.current()
        if self._loading or not b:
            return
        b.bars = int(v)
        self._refresh()
        self.changed.emit()

    def _notes_changed(self):
        b = self.current()
        if self._loading or not b:
            return
        had = bool(b.notes.strip())
        b.notes = self.notes.toPlainText()
        if had != bool(b.notes.strip()):
            self._update_item()
        self.timeline.update()
        self.changed.emit()

    def _update_item(self):
        i = self.list.currentRow()
        b = self.current()
        if b is None:
            return
        bar = sum(x.bars for x in self.song.arrangement[:i]) + 1
        t = self.song.block_start_seconds()[i]
        self.list.item(i).setText(f"{b.label or b.type}    ·  {b.bars} bars   ·  bar {bar}  ·  {music.format_duration(t)}"
                                  + ("    ✎" if b.notes.strip() else ""))
        self.timeline.update()
