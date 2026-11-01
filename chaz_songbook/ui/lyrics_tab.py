"""Lyrics tab: sections list, big editor with syllable gutter, stats and rhyme helper."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QListView, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton,
                               QSplitter, QToolButton, QVBoxLayout, QWidget)

from .. import lyrics as lx
from ..model import SECTION_COLORS, SECTION_TYPES, LyricSection
from . import theme
from .common import card, hbox, muted
from .widgets import LyricEditor


class RhymePanel(QFrame):
    wordPicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 14)
        t = QLabel("RHYME HELPER")
        t.setObjectName("SectionTitle")
        t.setFont(theme.head_font(13))
        lay.addWidget(t)
        self.query = QLineEdit()
        self.query.setPlaceholderText("type a word…")
        self.follow = QCheckBox("Follow last word of current line")
        self.follow.setChecked(True)
        lay.addWidget(self.query)
        lay.addWidget(self.follow)
        self.perfect_lbl = QLabel("PERFECT")
        self.perfect_lbl.setStyleSheet(f"color:{theme.GOLD};font-weight:700;font-size:11px;")
        self.perfect = self._chips()
        self.near_lbl = QLabel("NEAR / SLANT")
        self.near_lbl.setStyleSheet(f"color:{theme.CRIMSON_HI};font-weight:700;font-size:11px;")
        self.near = self._chips()
        lay.addWidget(self.perfect_lbl)
        lay.addWidget(self.perfect, 3)
        lay.addWidget(self.near_lbl)
        lay.addWidget(self.near, 2)
        hint = muted("Click a word to insert it. Offline list of ~36k words (CMU dictionary).")
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size:11px")
        lay.addWidget(hint)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._lookup)
        self.query.textChanged.connect(lambda _: self._timer.start())

    def _chips(self):
        w = QListWidget()
        w.setViewMode(QListView.ViewMode.ListMode)
        w.setFlow(QListView.Flow.LeftToRight)
        w.setWrapping(True)
        w.setResizeMode(QListView.ResizeMode.Adjust)
        w.setSpacing(3)
        w.setUniformItemSizes(False)
        w.setStyleSheet(f"""
            QListWidget::item {{ background:{theme.PANEL3}; border:1px solid {theme.BORDER}; border-radius:9px;
                                 padding:3px 8px; margin:0; }}
            QListWidget::item:hover {{ border-color:{theme.GOLD_DIM}; background:#2A2A32; }}
            QListWidget::item:selected {{ background:#3A2E0A; border-color:{theme.GOLD}; color:{theme.GOLD}; }}""")
        w.itemClicked.connect(lambda it: self.wordPicked.emit(it.text()))
        return w

    def set_from_line(self, line: str):
        if self.follow.isChecked():
            w = lx.last_word(line)
            if w and w.lower() != self.query.text().lower():
                self.query.setText(w)

    def _lookup(self):
        word = self.query.text().strip()
        res = lx.rhymes(word, limit=80) if word else {"perfect": [], "near": []}
        for lst, items, lbl, name in ((self.perfect, res["perfect"], self.perfect_lbl, "PERFECT"),
                                      (self.near, res["near"], self.near_lbl, "NEAR / SLANT")):
            lst.clear()
            lst.addItems(items)
            lbl.setText(f"{name}  ({len(items)})" if word else name)


class LyricsTab(QWidget):
    changed = Signal()

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.song = None
        self._loading = False
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(10)
        split.setStyleSheet("QSplitter::handle{background:transparent;}")
        root.addWidget(split)

        # sections column
        c, lay = card("Sections")
        self.sections = QListWidget()
        self.sections.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.sections.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.sections.setToolTip("Drag to reorder · double-click to rename")
        self.sections.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        lay.addWidget(self.sections, 1)
        self.add_btn = QPushButton("+ Section")
        self.add_btn.setObjectName("Primary")
        menu = QMenu(self)
        for t in SECTION_TYPES:
            menu.addAction(t, lambda t=t: self.add_section(t))
        self.add_btn.setMenu(menu)
        self.dup_btn = QPushButton("Duplicate")
        self.del_btn = QPushButton("Delete")
        self.del_btn.setObjectName("Danger")
        lay.addWidget(self.add_btn)
        lay.addWidget(hbox(self.dup_btn, self.del_btn))
        self.total_lbl = muted("")
        self.total_lbl.setWordWrap(True)
        lay.addWidget(self.total_lbl)
        c.setMinimumWidth(190)
        split.addWidget(c)

        # editor column
        mid = QWidget()
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(8)
        self.label_edit = QLineEdit()
        self.label_edit.setFont(theme.head_font(20))
        self.label_edit.setPlaceholderText("Section name")
        self.type_combo = QComboBox()
        self.type_combo.addItems(SECTION_TYPES)
        self.swatch = QLabel()
        self.swatch.setFixedSize(14, 14)
        ml.addWidget(hbox(self.swatch, self.label_edit, self.type_combo))
        self.editor = LyricEditor()
        self.editor.setPlaceholderText("Write here. One line = one bar.\nNumbers on the right = syllables per line.\n"
                                       "Lines in [brackets] are notes and aren't counted.")
        ml.addWidget(self.editor, 1)
        self.stats_lbl = QLabel("")
        self.stats_lbl.setStyleSheet(f"color:{theme.MUTED};")
        ml.addWidget(self.stats_lbl)
        split.addWidget(mid)

        self.rhyme = RhymePanel()
        self.rhyme.setMinimumWidth(230)
        split.addWidget(self.rhyme)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setStretchFactor(2, 0)
        split.setSizes([210, 640, 280])

        self.sections.currentRowChanged.connect(self._select)
        self.sections.model().rowsMoved.connect(self._rows_moved)
        self.sections.itemChanged.connect(self._item_renamed)
        self.dup_btn.clicked.connect(self._duplicate)
        self.del_btn.clicked.connect(self._delete)
        self.label_edit.textEdited.connect(self._label_changed)
        self.type_combo.currentTextChanged.connect(self._type_changed)
        self.editor.textChanged.connect(self._text_changed)
        self.editor.currentLineChanged.connect(self.rhyme.set_from_line)
        self.rhyme.wordPicked.connect(self.editor.replace_or_insert_word)

    # ---------------------------------------------------------------------
    def load(self, song):
        self._loading = True
        self.song = song
        self._fill()
        self._loading = False
        self.sections.setCurrentRow(0 if song.lyrics else -1)
        self._select(self.sections.currentRow())
        self._update_totals()

    def _fill(self):
        cur = self.sections.currentRow()
        self.sections.blockSignals(True)
        self.sections.clear()
        for sec in self.song.lyrics:
            it = QListWidgetItem(self._item_text(sec))
            it.setData(Qt.ItemDataRole.UserRole, sec.id)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
            it.setForeground(QColor(theme.TEXT))
            it.setData(Qt.ItemDataRole.DecorationRole, QColor(SECTION_COLORS.get(sec.type, "#444")))
            self.sections.addItem(it)
        self.sections.blockSignals(False)
        if 0 <= cur < self.sections.count():
            self.sections.setCurrentRow(cur)

    @staticmethod
    def _item_text(sec):
        return sec.label or sec.type

    def current(self):
        i = self.sections.currentRow()
        return self.song.lyrics[i] if self.song and 0 <= i < len(self.song.lyrics) else None

    def _select(self, i):
        sec = self.current()
        self._loading = True
        enabled = sec is not None
        for w in (self.editor, self.label_edit, self.type_combo, self.dup_btn, self.del_btn):
            w.setEnabled(enabled)
        if sec:
            self.label_edit.setText(sec.label)
            self.type_combo.setCurrentText(sec.type)
            self.editor.setPlainText(sec.text)
            self.swatch.setStyleSheet(f"background:{SECTION_COLORS.get(sec.type, '#444')};border-radius:7px;")
        else:
            self.label_edit.clear()
            self.editor.setPlainText("")
            self.editor.setPlaceholderText("Add a section (Hook, Verse…) to start writing.")
        self._loading = False
        self._update_stats()

    def add_section(self, sec_type="Verse"):
        if not self.song:
            return
        sec = LyricSection(type=sec_type, label=self.song.next_section_label(sec_type))
        i = self.sections.currentRow()
        pos = i + 1 if i >= 0 else len(self.song.lyrics)
        self.song.lyrics.insert(pos, sec)
        self._fill()
        self.sections.setCurrentRow(pos)
        self.editor.setFocus()
        self._changed()

    def _duplicate(self):
        sec = self.current()
        if not sec:
            return
        i = self.sections.currentRow()
        self.song.lyrics.insert(i + 1, LyricSection(sec.type, sec.label, sec.text))
        self._fill()
        self.sections.setCurrentRow(i + 1)
        self._changed()

    def _delete(self):
        sec = self.current()
        if not sec:
            return
        if sec.text.strip() and QMessageBox.question(
                self, "Delete section", f"Delete “{sec.label}” and its lyrics?") != QMessageBox.StandardButton.Yes:
            return
        i = self.sections.currentRow()
        del self.song.lyrics[i]
        self._fill()
        self.sections.setCurrentRow(min(i, len(self.song.lyrics) - 1))
        self._select(self.sections.currentRow())
        self._changed()

    def _rows_moved(self, *_):
        by_id = {s.id: s for s in self.song.lyrics}
        order = [self.sections.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.sections.count())]
        self.song.lyrics = [by_id[x] for x in order if x in by_id]
        self._changed()

    def _item_renamed(self, it):
        if self._loading:
            return
        sid = it.data(Qt.ItemDataRole.UserRole)
        for s in self.song.lyrics:
            if s.id == sid and it.text().strip() and it.text() != s.label:
                s.label = it.text().strip()
                if s is self.current():
                    self.label_edit.setText(s.label)
                self._changed()

    def _label_changed(self, text):
        sec = self.current()
        if self._loading or not sec:
            return
        sec.label = text
        it = self.sections.currentItem()
        self.sections.blockSignals(True)
        it.setText(text or sec.type)
        self.sections.blockSignals(False)
        self._changed()

    def _type_changed(self, t):
        sec = self.current()
        if self._loading or not sec:
            return
        old = sec.type
        sec.type = t
        if not sec.label or sec.label.startswith(old):
            sec.label = self.song.next_section_label(t, [s for s in self.song.lyrics if s is not sec])
            self.label_edit.setText(sec.label)
        self.swatch.setStyleSheet(f"background:{SECTION_COLORS.get(t, '#444')};border-radius:7px;")
        self._fill()
        self._changed()

    def _text_changed(self):
        sec = self.current()
        if self._loading or not sec:
            return
        sec.text = self.editor.toPlainText()
        self._update_stats()
        self._changed()

    def _update_stats(self):
        sec = self.current()
        if not sec:
            self.stats_lbl.setText("")
        else:
            st = lx.stats(sec.text)
            self.stats_lbl.setText(f"<b style='color:{theme.GOLD}'>{st['bars']}</b> bars &nbsp;·&nbsp; "
                                   f"<b style='color:{theme.TEXT}'>{st['words']}</b> words &nbsp;·&nbsp; "
                                   f"<b style='color:{theme.TEXT}'>{st['syllables']}</b> syllables &nbsp;·&nbsp; "
                                   f"avg <b style='color:{theme.TEXT}'>{st['avg_syllables']}</b> syl/bar")
        self._update_totals()

    def _update_totals(self):
        if not self.song:
            return
        allt = "\n".join(s.text for s in self.song.lyrics)
        st = lx.stats(allt)
        self.total_lbl.setText(f"Whole song: {st['bars']} bars · {st['words']} words")

    def _changed(self):
        if not self._loading:
            self.changed.emit()
