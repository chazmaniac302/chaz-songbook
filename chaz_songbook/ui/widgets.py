"""Custom widgets: song list delegate, tag chips, lyric editor with syllable gutter, timeline."""
from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen,
                           QTextCursor)
from PySide6.QtWidgets import (QCompleter, QHBoxLayout, QLayout, QLineEdit, QPlainTextEdit, QSizePolicy,
                               QStyle, QStyledItemDelegate, QToolButton, QWidget, QWidgetItem)

from .. import music
from ..lyrics import line_syllables
from . import theme

SONG_ROLE = Qt.ItemDataRole.UserRole + 1


def relative_time(iso: str) -> str:
    try:
        t = datetime.fromisoformat(iso)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
    except ValueError:
        return ""
    secs = (datetime.now(timezone.utc) - t).total_seconds()
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    if secs < 86400 * 7:
        return f"{int(secs // 86400)}d ago"
    return t.astimezone().strftime("%b %d")


class SongItemDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(200, 62)

    def paint(self, p: QPainter, option, index):
        song = index.data(SONG_ROLE)
        if song is None:
            return super().paint(p, option, index)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(option.rect).adjusted(4, 2, -4, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected:
            g = QLinearGradient(r.topLeft(), r.topRight())
            g.setColorAt(0, QColor("#3A0C16"))
            g.setColorAt(1, QColor("#1E1210"))
            p.setBrush(g)
            p.setPen(QPen(QColor(theme.CRIMSON), 1))
        elif hover:
            p.setBrush(QColor(theme.PANEL2))
            p.setPen(Qt.PenStyle.NoPen)
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, 8, 8)
        if selected:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.GOLD))
            p.drawRoundedRect(QRectF(r.left(), r.top() + 10, 3, r.height() - 20), 1.5, 1.5)

        x = r.left() + 14
        # title
        tf = QFont(option.font)
        tf.setPixelSize(14)
        tf.setWeight(QFont.Weight.DemiBold)
        p.setFont(tf)
        p.setPen(QColor("#FFFFFF" if selected else theme.TEXT))
        right_reserved = 70
        title = QFontMetrics(tf).elidedText(song.title or "Untitled", Qt.TextElideMode.ElideRight,
                                            int(r.width() - (x - r.left()) - right_reserved))
        p.drawText(QRectF(x, r.top() + 8, r.width(), 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)
        # star + date on the right
        sf = QFont(option.font)
        sf.setPixelSize(11)
        p.setFont(sf)
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(r.right() - 80, r.top() + 8, 70, 20),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, relative_time(song.updated))
        if song.favorite:
            stf = QFont(option.font)
            stf.setPixelSize(13)
            p.setFont(stf)
            p.setPen(QColor(theme.GOLD))
            p.drawText(QRectF(r.right() - 80, r.top() + 33, 70, 20),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "★")
        # status pill
        pf = QFont(option.font)
        pf.setPixelSize(10)
        pf.setWeight(QFont.Weight.Bold)
        p.setFont(pf)
        col = QColor(theme.STATUS_COLORS.get(song.status, theme.MUTED))
        fm = QFontMetrics(pf)
        pw = fm.horizontalAdvance(song.status.upper()) + 14
        pill = QRectF(x, r.top() + 35, pw, 17)
        bg = QColor(col)
        bg.setAlpha(45)
        p.setBrush(bg)
        p.setPen(QPen(col, 1))
        p.drawRoundedRect(pill, 8.5, 8.5)
        p.setPen(col)
        p.drawText(pill, Qt.AlignmentFlag.AlignCenter, song.status.upper())
        # meta
        meta = []
        if song.bpm:
            meta.append(f"{song.bpm:g} BPM")
        k = music.short_key(song.key_tonic, song.key_scale)
        if k:
            meta.append(f"{k} · {song.camelot}")
        if song.tags:
            meta.append("#" + " #".join(song.tags[:2]))
        p.setFont(sf)
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(pill.right() + 8, r.top() + 34, r.width() - pw - 110, 19),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   QFontMetrics(sf).elidedText("  ·  ".join(meta), Qt.TextElideMode.ElideRight,
                                               int(r.right() - pill.right() - 40)))
        p.restore()


class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing=6):
        super().__init__(parent)
        self._items = []
        self.setSpacing(spacing)
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._do_layout(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        return s + QSize(2, 2)

    def _do_layout(self, rect, test):
        x, y, line_h = rect.x(), rect.y(), 0
        sp = self.spacing()
        for it in self._items:
            hint = it.sizeHint()
            nx = x + hint.width() + sp
            if nx - sp > rect.right() and line_h > 0:
                x = rect.x()
                y += line_h + sp
                nx = x + hint.width() + sp
                line_h = 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x = nx
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y()


class TagEditor(QWidget):
    """Chips with × plus an input (Enter or comma adds)."""
    changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tags: list[str] = []
        self.flow = FlowLayout(self)
        self.input = QLineEdit()
        self.input.setPlaceholderText("add tag…")
        self.input.setFixedWidth(130)
        self.input.returnPressed.connect(self._commit)
        self.input.textEdited.connect(lambda t: self._commit() if t.endswith(",") else None)
        self._completer = QCompleter([])
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.input.setCompleter(self._completer)
        self._rebuild()

    def set_suggestions(self, tags):
        from PySide6.QtCore import QStringListModel
        self._completer.setModel(QStringListModel(sorted(set(tags), key=str.lower)))

    def tags(self):
        return list(self._tags)

    def set_tags(self, tags):
        self._tags = list(tags)
        self._rebuild()

    def _commit(self):
        for t in self.input.text().split(","):
            t = t.strip().lower()
            if t and t not in self._tags:
                self._tags.append(t)
        self.input.clear()
        self._rebuild()
        self.changed.emit(self.tags())

    def _remove(self, tag):
        if tag in self._tags:
            self._tags.remove(tag)
            self._rebuild()
            self.changed.emit(self.tags())

    def _rebuild(self):
        while self.flow.count():
            it = self.flow.takeAt(0)
            w = it.widget()
            if w is not None and w is not self.input:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        for t in self._tags:
            b = QToolButton()
            b.setObjectName("Chip")
            b.setText(f"#{t}  ×")
            b.setToolTip("Remove tag")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, tag=t: self._remove(tag))
            self.flow.addWidget(b)
        self.flow.addWidget(self.input)
        self.updateGeometry()


class _Gutter(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def paintEvent(self, ev):
        self.editor.paint_gutter(self, ev)


class LyricEditor(QPlainTextEdit):
    """Big lyric editor that shows the syllable count of each line on the right."""
    currentLineChanged = Signal(str)
    GUTTER = 54

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LyricEditor")
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.gutter = _Gutter(self)
        self.setViewportMargins(0, 0, self.GUTTER, 0)
        self.updateRequest.connect(lambda *_: self.gutter.update())
        self.cursorPositionChanged.connect(self._emit_line)
        self.setTabChangesFocus(False)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.right() - self.GUTTER + 1, cr.top(), self.GUTTER, cr.height()))

    def _emit_line(self):
        self.currentLineChanged.emit(self.textCursor().block().text())
        self.gutter.update()

    def paint_gutter(self, w, ev):
        p = QPainter(w)
        p.fillRect(ev.rect(), QColor("#0E0E11"))
        p.setPen(QColor(theme.BORDER))
        p.drawLine(0, ev.rect().top(), 0, ev.rect().bottom())
        f = QFont(self.font())
        f.setPixelSize(11)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        block = self.firstVisibleBlock()
        offset = self.contentOffset()
        cur = self.textCursor().blockNumber()
        vm_top = self.viewport().geometry().top() - self.contentsRect().top()
        while block.isValid():
            geo = self.blockBoundingGeometry(block).translated(offset)
            top = geo.top() + vm_top
            if top > ev.rect().bottom():
                break
            if block.isVisible():
                text = block.text().strip()
                if text and not (text.startswith("[") and text.endswith("]")):
                    n = line_syllables(text)
                    lh = QFontMetrics(self.document().defaultFont()).height()
                    col = QColor(theme.GOLD) if block.blockNumber() == cur else QColor(theme.MUTED)
                    p.setPen(col)
                    p.drawText(QRectF(0, top + 4, self.GUTTER - 10, lh),
                               Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(n))
            block = block.next()
        p.end()

    def replace_or_insert_word(self, word: str):
        c = self.textCursor()
        if not c.hasSelection():
            c.insertText(("" if c.positionInBlock() == 0 or c.block().text()[c.positionInBlock() - 1:c.positionInBlock()] == " " else " ") + word)
        else:
            c.insertText(word)
        self.setTextCursor(c)
        self.setFocus()


class TimelineWidget(QWidget):
    """Colored block timeline of the arrangement with drag-to-reorder."""
    selected = Signal(int)
    moved = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.blocks = []
        self.bpm = 140.0
        self.time_signature = "4/4"
        self.current = -1
        self._press = None
        self._drag_from = None
        self._drop_at = None
        self._mouse_x = 0
        self.setMinimumHeight(132)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_data(self, blocks, bpm, ts, current=-1):
        self.blocks, self.bpm, self.time_signature = blocks, bpm, ts
        self.current = current
        self.update()

    def sizeHint(self):
        return QSize(600, 132)

    def _rects(self):
        total = sum(b.bars for b in self.blocks) or 1
        left, right = 12, self.width() - 12
        avail = max(10, right - left - 4 * (len(self.blocks) - 1))
        x = left
        out = []
        for b in self.blocks:
            w = max(28.0, avail * b.bars / total)
            out.append(QRectF(x, 34, w, 64))
            x += w + 4
        if out and out[-1].right() > right:  # squeeze if min widths overflowed
            k = (right - left) / (out[-1].right() - left)
            out = [QRectF(left + (r.left() - left) * k, r.top(), r.width() * k, r.height()) for r in out]
        return out

    def _index_at(self, pos):
        for i, r in enumerate(self._rects()):
            if r.contains(pos):
                return i
        return -1

    def _insert_index(self, x):
        rects = self._rects()
        for i, r in enumerate(rects):
            if x < r.center().x():
                return i
        return len(rects)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            i = self._index_at(ev.position())
            self._press = ev.position()
            self._drag_from = i if i >= 0 else None
            if i >= 0:
                self.current = i
                self.selected.emit(i)
                self.update()

    def mouseMoveEvent(self, ev):
        self._mouse_x = ev.position().x()
        if self._drag_from is not None and self._press is not None:
            if (ev.position() - self._press).manhattanLength() > 6:
                self._drop_at = self._insert_index(ev.position().x())
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                self.update()

    def mouseReleaseEvent(self, ev):
        if self._drag_from is not None and self._drop_at is not None:
            src, dst = self._drag_from, self._drop_at
            if dst > src:
                dst -= 1
            if dst != src:
                self.moved.emit(src, dst)
        self._press = self._drag_from = self._drop_at = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(theme.PANEL))
        rects = self._rects()
        small = QFont(self.font())
        small.setPixelSize(10)
        if not self.blocks:
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "No sections yet — add Intro, Hook, Verse… or build from your lyric sections")
            return
        # ruler
        total = sum(b.bars for b in self.blocks)
        p.setFont(small)
        bar = 1
        for b, r in zip(self.blocks, rects):
            p.setPen(QColor("#5E5A52"))
            p.drawLine(int(r.left()), 22, int(r.left()), 30)
            if r.width() > 26:
                p.drawText(QRectF(r.left() + 3, 8, 60, 14), Qt.AlignmentFlag.AlignLeft, str(bar))
            bar += b.bars
        hf = theme.head_font(14)
        for i, (b, r) in enumerate(zip(self.blocks, rects)):
            col = QColor(b.color)
            g = QLinearGradient(r.topLeft(), r.bottomLeft())
            g.setColorAt(0, col.lighter(125))
            g.setColorAt(1, col.darker(150))
            path = QPainterPath()
            path.addRoundedRect(r, 7, 7)
            if self._drag_from == i and self._drop_at is not None:
                p.setOpacity(0.45)
            p.fillPath(path, g)
            p.setOpacity(1.0)
            p.setBrush(Qt.BrushStyle.NoBrush)
            if i == self.current:
                p.setPen(QPen(QColor(theme.GOLD), 2.4))
            else:
                p.setPen(QPen(QColor(0, 0, 0, 120), 1))
            p.drawPath(path)
            p.setPen(QColor("#FFFFFF"))
            p.setFont(hf)
            fm = QFontMetrics(hf)
            label = fm.elidedText((b.label or b.type).upper(), Qt.TextElideMode.ElideRight, int(r.width() - 10))
            p.drawText(r.adjusted(6, 6, -4, -28), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, label)
            p.setFont(small)
            p.setPen(QColor(255, 255, 255, 210))
            if r.width() > 34:
                p.drawText(r.adjusted(6, 0, -4, -7), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                           f"{b.bars} bars" if r.width() > 52 else str(b.bars))
            if b.notes and r.width() > 20:
                p.setBrush(QColor(theme.GOLD))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(r.right() - 11, r.top() + 6, 5, 5))
        # time axis
        p.setFont(small)
        p.setPen(QColor(theme.MUTED))
        acc = 0
        for b, r in zip(self.blocks, rects):
            if r.width() > 40:
                t = music.format_duration(music.bars_to_seconds(acc, self.bpm, self.time_signature))
                p.drawText(QRectF(r.left() + 2, 102, 60, 14), Qt.AlignmentFlag.AlignLeft, t)
            acc += b.bars
        end = music.format_duration(music.bars_to_seconds(total, self.bpm, self.time_signature))
        p.drawText(QRectF(self.width() - 80, 102, 68, 14), Qt.AlignmentFlag.AlignRight, end)
        if self._drop_at is not None:
            x = rects[self._drop_at].left() - 2 if self._drop_at < len(rects) else rects[-1].right() + 2
            p.setPen(QPen(QColor(theme.GOLD), 3))
            p.drawLine(int(x), 28, int(x), 104)
        p.end()
