"""Main window: library sidebar + song editor tabs, autosave, import/export, data folder."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QByteArray, QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox,
                               QPushButton, QSplitter, QStackedWidget, QTabWidget, QToolButton, QVBoxLayout,
                               QWidget)

from .. import APP_NAME, __version__, music
from .. import export as ex
from ..audio import Metronome
from ..model import STATUSES, filter_songs, sort_songs
from ..paths import default_data_dir, suggested_onedrive_data_dir
from ..store import LIBRARY_FILE, Library, Settings
from . import theme
from .arrangement_tab import ArrangementTab
from .common import hbox, muted, open_path
from .lyrics_tab import LyricsTab
from .memos_tab import MemosTab
from .overview import OverviewTab
from .widgets import SONG_ROLE, SongItemDelegate

SORTS = [("Recently edited", "updated"), ("Newest", "created"), ("Title A–Z", "title"),
         ("BPM", "bpm"), ("Key (Camelot)", "key"), ("Status", "status")]


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, library: Library):
        super().__init__()
        self.settings = settings
        self.library = library
        self.metronome = Metronome(self)
        self.song = None
        self._dirty = False
        self._save_error_shown = False
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1060, 680)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(700)
        self._save_timer.timeout.connect(self.save_now)

        self._build_menu()
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(1)
        root.addWidget(split)
        split.addWidget(self._build_sidebar())
        split.addWidget(self._build_editor())
        split.setStretchFactor(1, 1)
        split.setSizes([330, 1100])
        self.splitter = split

        self.save_lbl = QLabel("")
        self.path_lbl = QLabel("")
        self.statusBar().addWidget(self.save_lbl)
        self.statusBar().addPermanentWidget(self.path_lbl)
        self._update_path_label()

        geo = settings.get("geometry")
        if geo:
            self.restoreGeometry(QByteArray.fromBase64(geo.encode()))
        else:
            self.resize(1400, 880)
        self.refresh_list(select_id=settings.get("last_song"))

    # ------------------------------------------------------------------ ui
    def _build_menu(self):
        mb = self.menuBar()
        f = mb.addMenu("&File")
        self.act_new = QAction("New song", self, shortcut=QKeySequence.StandardKey.New, triggered=self.new_song)
        self.act_dup = QAction("Duplicate song", self, shortcut="Ctrl+D", triggered=self.duplicate_song)
        self.act_del = QAction("Delete song…", self, triggered=self.delete_song)
        self.act_ren = QAction("Rename song", self, shortcut="F2", triggered=self.focus_title)
        f.addActions([self.act_new, self.act_dup, self.act_ren, self.act_del])
        f.addSeparator()
        exp = f.addMenu("Export song sheet")
        exp.addAction("PDF…", lambda: self.export_song("pdf"))
        exp.addAction("Markdown…", lambda: self.export_song("md"))
        exp.addAction("Text…", lambda: self.export_song("txt"))
        exp.addAction("JSON (this song)…", lambda: self.export_song("json"))
        f.addAction("Back up whole library to JSON…", self.backup_all)
        f.addAction("Import songs from JSON…", self.import_json)
        f.addSeparator()
        f.addAction("Data folder (OneDrive sync)…", self.data_folder_dialog)
        f.addAction("Open data folder", lambda: open_path(self.library.data_dir))
        f.addSeparator()
        f.addAction(QAction("Save now", self, shortcut=QKeySequence.StandardKey.Save, triggered=self.save_now))
        f.addAction(QAction("Exit", self, shortcut="Ctrl+Q", triggered=self.close))
        h = mb.addMenu("&Help")
        h.addAction("Keyboard shortcuts", self._shortcuts)
        h.addAction(f"About {APP_NAME}", self._about)
        self.addAction(QAction(self, shortcut="Ctrl+F", triggered=lambda: (self.search.setFocus(), self.search.selectAll())))
        for i in range(4):
            self.addAction(QAction(self, shortcut=f"Ctrl+{i + 1}", triggered=lambda i=i: self.tabs.setCurrentIndex(i)))

    def _build_sidebar(self):
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setMinimumWidth(290)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(14, 16, 14, 10)
        lay.setSpacing(10)
        brand = QLabel("CHAZ <span style='color:%s'>SONGBOOK</span>" % theme.CRIMSON_HI)
        brand.setObjectName("Brand")
        brand.setFont(theme.head_font(24, weight=QFont.Weight.Bold))
        sub = muted("ideas · bars · arrangements")
        sub.setStyleSheet("font-size:11px;letter-spacing:1px;")
        lay.addWidget(brand)
        lay.addWidget(sub)
        self.new_btn = QPushButton("+  New song")
        self.new_btn.setObjectName("Primary")
        self.new_btn.setMinimumHeight(36)
        self.new_btn.clicked.connect(self.new_song)
        lay.addWidget(self.new_btn)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search title, lyrics, tags, key, BPM…   Ctrl+F")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _: self.refresh_list())
        lay.addWidget(self.search)
        self.status_filter = QComboBox()
        self.status_filter.addItem("All statuses", None)
        for s in STATUSES:
            self.status_filter.addItem(s, s)
        self.tag_filter = QComboBox()
        self.sort_combo = QComboBox()
        for label, key in SORTS:
            self.sort_combo.addItem(label, key)
        self.fav_btn = QToolButton()
        self.fav_btn.setText("★")
        self.fav_btn.setCheckable(True)
        self.fav_btn.setToolTip("Favorites only")
        idx = self.sort_combo.findData(self.settings.get("sort", "updated"))
        self.sort_combo.setCurrentIndex(max(0, idx))
        lay.addWidget(hbox(self.status_filter, self.tag_filter, spacing=6))
        lay.addWidget(hbox(self.sort_combo, self.fav_btn, spacing=6))
        for w in (self.status_filter, self.tag_filter, self.sort_combo):
            w.currentIndexChanged.connect(lambda _: self.refresh_list())
        self.fav_btn.toggled.connect(lambda _: self.refresh_list())
        self.list = QListWidget()
        self.list.setItemDelegate(SongItemDelegate(self.list))
        self.list.setMouseTracking(True)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._list_menu)
        self.list.currentItemChanged.connect(self._on_select)
        lay.addWidget(self.list, 1)
        self.count_lbl = muted("")
        self.count_lbl.setStyleSheet("font-size:11px")
        lay.addWidget(self.count_lbl)
        return side

    def _build_editor(self):
        self.stack = QStackedWidget()
        empty = QWidget()
        el = QVBoxLayout(empty)
        el.addStretch(1)
        t = QLabel("No song selected")
        t.setFont(theme.head_font(28))
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet(f"color:{theme.GOLD}")
        el.addWidget(t)
        m = muted("Hit “New song” (Ctrl+N) to catch that idea before it's gone.")
        m.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(m)
        b = QPushButton("+  New song")
        b.setObjectName("Primary")
        b.clicked.connect(self.new_song)
        el.addWidget(hbox(None, b, None))
        el.addStretch(2)
        self.stack.addWidget(empty)

        page = QWidget()
        pl = QVBoxLayout(page)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)
        header = QFrame()
        header.setObjectName("Header")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(20, 14, 20, 0)
        hl.setSpacing(4)
        self.star = QToolButton()
        self.star.setObjectName("Star")
        self.star.setText("★")
        self.star.setCheckable(True)
        self.star.setToolTip("Favorite")
        self.title = QLineEdit()
        self.title.setObjectName("TitleEdit")
        self.title.setFont(theme.head_font(28))
        self.title.setPlaceholderText("Song title")
        self.status = QComboBox()
        self.status.addItems(STATUSES)
        self.status.setMinimumWidth(130)
        self.export_btn = QPushButton("Export")
        em = QMenu(self)
        em.addAction("Song sheet → PDF…", lambda: self.export_song("pdf"))
        em.addAction("Song sheet → Markdown…", lambda: self.export_song("md"))
        em.addAction("Song sheet → Text…", lambda: self.export_song("txt"))
        em.addAction("This song → JSON…", lambda: self.export_song("json"))
        em.addSeparator()
        em.addAction("Back up whole library…", self.backup_all)
        self.export_btn.setMenu(em)
        self.more_btn = QPushButton("⋯")
        mm = QMenu(self)
        mm.addAction("Duplicate song", self.duplicate_song)
        mm.addAction("Delete song…", self.delete_song)
        self.more_btn.setMenu(mm)
        hl.addWidget(hbox(self.star, self.title, self.status, self.export_btn, self.more_btn, spacing=8))
        self.summary = QLabel("")
        self.summary.setStyleSheet(f"color:{theme.MUTED};padding-left:40px;")
        hl.addWidget(self.summary)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.overview = OverviewTab(self)
        self.lyrics = LyricsTab(self)
        self.arrangement = ArrangementTab(self)
        self.memos = MemosTab(self)
        self.tabs.addTab(self.overview, "OVERVIEW")
        self.tabs.addTab(self.lyrics, "LYRICS")
        self.tabs.addTab(self.arrangement, "ARRANGEMENT")
        self.tabs.addTab(self.memos, "VOICE MEMOS")
        pl.addWidget(header)
        pl.addWidget(self.tabs, 1)
        self.stack.addWidget(page)

        self.title.textEdited.connect(self._title_changed)
        self.status.currentTextChanged.connect(self._status_changed)
        self.star.toggled.connect(self._star_changed)
        for t in (self.overview, self.lyrics, self.arrangement, self.memos):
            t.changed.connect(self.mark_dirty)
        self.overview.tempoChanged.connect(self.arrangement.refresh_tempo)
        self.tabs.currentChanged.connect(self._tab_changed)
        return self.stack

    # -------------------------------------------------------------- library
    def refresh_list(self, select_id=None):
        if select_id is None and self.song:
            select_id = self.song.id
        cur_tag = self.tag_filter.currentData()
        self.tag_filter.blockSignals(True)
        self.tag_filter.clear()
        self.tag_filter.addItem("All tags", None)
        for t in self.library.all_tags():
            self.tag_filter.addItem("#" + t, t)
        i = self.tag_filter.findData(cur_tag)
        self.tag_filter.setCurrentIndex(max(0, i))
        self.tag_filter.blockSignals(False)
        sort_key = self.sort_combo.currentData()
        self.settings.data["sort"] = sort_key
        songs = filter_songs(self.library.all(), self.search.text(), self.status_filter.currentData(),
                             self.tag_filter.currentData(), self.fav_btn.isChecked())
        songs = sort_songs(songs, sort_key)
        self.list.blockSignals(True)
        self.list.clear()
        sel_row = -1
        for row, s in enumerate(songs):
            it = QListWidgetItem(s.title)
            it.setData(SONG_ROLE, s)
            it.setData(Qt.ItemDataRole.UserRole, s.id)
            self.list.addItem(it)
            if s.id == select_id:
                sel_row = row
        self.list.blockSignals(False)
        total = len(self.library.songs)
        self.count_lbl.setText(f"{len(songs)} of {total} songs" if len(songs) != total else f"{total} songs")
        if sel_row < 0 and songs and (self.song is None or self.song.id not in {s.id for s in songs}):
            sel_row = 0
        if sel_row >= 0:
            self.list.setCurrentRow(sel_row)
            self._show_song(songs[sel_row])
        elif not songs and not self.library.songs:
            self._show_song(None)

    def _on_select(self, item, _prev=None):
        if item is None:
            return
        s = self.library.get(item.data(Qt.ItemDataRole.UserRole))
        if s is not self.song:
            self._show_song(s)

    def _show_song(self, song):
        if self.song is not None and self._dirty:
            self.save_now()
        self.overview.stop_metronome()
        self.metronome.stop()
        self.song = song
        if song is None:
            self.stack.setCurrentIndex(0)
            return
        self.stack.setCurrentIndex(1)
        self.title.setText(song.title)
        self.status.blockSignals(True)
        self.status.setCurrentText(song.status)
        self.status.blockSignals(False)
        self.star.blockSignals(True)
        self.star.setChecked(song.favorite)
        self.star.blockSignals(False)
        self.overview.load(song)
        self.lyrics.load(song)
        self.arrangement.load(song)
        self.memos.load(song)
        self._update_summary()
        self.settings.data["last_song"] = song.id

    def _update_summary(self):
        s = self.song
        if not s:
            return
        parts = []
        if s.bpm:
            parts.append(f"{s.bpm:g} BPM")
        if s.key_tonic is not None:
            parts.append(f"{s.key_display} ({s.camelot})")
        parts.append(s.time_signature)
        if s.arrangement:
            parts.append(f"{s.total_bars} bars · {music.format_duration(s.total_seconds)}")
        bars = sum(len([l for l in sec.text.splitlines() if l.strip()]) for sec in s.lyrics)
        if bars:
            parts.append(f"{bars} lyric bars")
        if s.artist or s.features:
            parts.append(" ft. ".join(x for x in (s.artist, s.features) if x))
        self.summary.setText("   ·   ".join(parts))

    def _current_item(self):
        for i in range(self.list.count()):
            it = self.list.item(i)
            if self.song and it.data(Qt.ItemDataRole.UserRole) == self.song.id:
                return it
        return None

    # ------------------------------------------------------------- editing
    def mark_dirty(self):
        if not self.song:
            return
        self.song.touch()
        self._dirty = True
        self.save_lbl.setText("Editing…")
        self._save_timer.start()
        self._update_summary()
        it = self._current_item()
        if it:
            it.setText(self.song.title)  # triggers repaint via dataChanged
            self.list.viewport().update()

    def _title_changed(self, t):
        if self.song:
            self.song.title = t.strip() or "Untitled"
            self.mark_dirty()

    def _status_changed(self, t):
        if self.song and t != self.song.status:
            self.song.status = t
            self.mark_dirty()

    def _star_changed(self, on):
        if self.song:
            self.song.favorite = on
            self.mark_dirty()

    def focus_title(self):
        self.title.setFocus()
        self.title.selectAll()

    def _tab_changed(self, i):
        if self.tabs.widget(i) is self.arrangement and self.song:
            self.arrangement.refresh_tempo()

    def save_now(self):
        self._save_timer.stop()
        try:
            self.library.save()
            self.settings.save()
        except OSError as e:
            self.save_lbl.setText(f"<span style='color:{theme.CRIMSON_HI}'>⚠ Not saved: {e}</span>")
            if not self._save_error_shown:
                self._save_error_shown = True
                QMessageBox.critical(self, "Save failed", f"Couldn't save your library:\n{e}\n\n"
                                     "Check the data folder (File › Data folder) is available.")
            return False
        self._dirty = False
        self._save_error_shown = False
        self.save_lbl.setText(f"<span style='color:{theme.GOLD}'>✓</span> Saved {datetime.now():%I:%M:%S %p}".replace(" 0", " "))
        return True

    def new_song(self):
        s = self.library.create("New Song")
        if self.song:
            s.artist = self.song.artist
        self.search.clear()
        self.status_filter.setCurrentIndex(0)
        self.tag_filter.setCurrentIndex(0)
        self.fav_btn.setChecked(False)
        self.save_now()
        self.refresh_list(select_id=s.id)
        self.tabs.setCurrentIndex(0)
        self.focus_title()
        return s

    def duplicate_song(self):
        if not self.song:
            return
        s = self.library.duplicate(self.song.id)
        self.save_now()
        self.refresh_list(select_id=s.id)
        self.focus_title()

    def delete_song(self):
        if not self.song:
            return
        r = QMessageBox.question(self, "Delete song",
                                 f"Delete “{self.song.title}”?\n\nA dated backup of your library is kept in the "
                                 "backups folder, so you can still get it back.")
        if r != QMessageBox.StandardButton.Yes:
            return
        self.library.make_daily_backup(force=True)
        sid = self.song.id
        self.song = None
        self.library.delete(sid)
        self.save_now()
        self.refresh_list()
        if not self.library.songs:
            self._show_song(None)

    def _list_menu(self, pos):
        it = self.list.itemAt(pos)
        if not it:
            return
        self.list.setCurrentItem(it)
        m = QMenu(self)
        m.addAction("Rename", self.focus_title)
        m.addAction("Unstar" if self.song.favorite else "Star", lambda: self.star.toggle())
        st = m.addMenu("Status")
        for s in STATUSES:
            a = st.addAction(s, lambda s=s: self.status.setCurrentText(s))
            a.setCheckable(True)
            a.setChecked(self.song.status == s)
        m.addAction("Duplicate", self.duplicate_song)
        m.addSeparator()
        m.addAction("Export PDF…", lambda: self.export_song("pdf"))
        m.addSeparator()
        m.addAction("Delete…", self.delete_song)
        m.exec(self.list.viewport().mapToGlobal(pos))

    # -------------------------------------------------------- import/export
    def _export_dir(self):
        return self.settings.get("last_export_dir") or str(Path.home() / "Documents")

    def export_song(self, kind):
        if not self.song:
            return
        filters = {"pdf": "PDF (*.pdf)", "md": "Markdown (*.md)", "txt": "Text (*.txt)", "json": "JSON (*.json)"}
        name = ex.safe_filename(self.song.title) + "." + kind
        path, _ = QFileDialog.getSaveFileName(self, "Export song", str(Path(self._export_dir()) / name), filters[kind])
        if not path:
            return
        try:
            if kind == "json":
                self.library.export_json(Path(path), [self.song])
            else:
                ex.export_song(self.song, path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", str(e))
            return
        self.settings.set("last_export_dir", str(Path(path).parent))
        self.statusBar().showMessage(f"Exported {path}", 6000)
        if QMessageBox.question(self, "Exported", f"Saved to\n{path}\n\nOpen it now?") == QMessageBox.StandardButton.Yes:
            open_path(path)

    def backup_all(self):
        name = f"ChazSongBook-backup-{datetime.now():%Y-%m-%d}.json"
        path, _ = QFileDialog.getSaveFileName(self, "Back up library", str(Path(self._export_dir()) / name),
                                              "JSON (*.json)")
        if path:
            self.library.export_json(Path(path))
            self.settings.set("last_export_dir", str(Path(path).parent))
            self.statusBar().showMessage(f"Backed up {len(self.library.songs)} songs to {path}", 8000)

    def import_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import songs", self._export_dir(), "JSON (*.json)")
        if not path:
            return
        try:
            added, updated = self.library.import_json(Path(path))
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Import failed", f"That file couldn't be imported:\n{e}")
            return
        self.save_now()
        self.refresh_list()
        QMessageBox.information(self, "Import done", f"Added {added} new song(s), updated {updated}.")

    # ---------------------------------------------------------- data folder
    def _update_path_label(self):
        self.path_lbl.setText(f"Library: {self.library.path}")

    def data_folder_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Data folder")
        dlg.setMinimumWidth(620)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(10)
        t = QLabel("WHERE YOUR SONGS LIVE")
        t.setObjectName("SectionTitle")
        t.setFont(theme.head_font(15))
        lay.addWidget(t)
        cur = QLabel(str(self.library.data_dir))
        cur.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cur.setStyleSheet(f"color:{theme.GOLD};font-size:14px;")
        lay.addWidget(cur)
        info = muted("Point this at a OneDrive folder to sync your SongBook between PCs. Your songs, voice memos "
                     "and backups move with it. Only run SongBook on one PC at a time.")
        info.setWordWrap(True)
        lay.addWidget(info)
        od = suggested_onedrive_data_dir()
        b_od = QPushButton(f"Use OneDrive  →  {od}" if od else "OneDrive not found on this PC")
        b_od.setObjectName("Primary")
        b_od.setEnabled(od is not None)
        b_pick = QPushButton("Choose another folder…")
        b_def = QPushButton(f"Reset to default  ({default_data_dir()})")
        b_open = QPushButton("Open current folder")
        for b in (b_od, b_pick, b_def, b_open):
            lay.addWidget(b)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)

        def go(target):
            if target and self.change_data_dir(Path(target)):
                cur.setText(str(self.library.data_dir))
        b_od.clicked.connect(lambda: go(od))
        b_pick.clicked.connect(lambda: go(QFileDialog.getExistingDirectory(dlg, "Choose data folder",
                                                                           str(self.library.data_dir))))
        b_def.clicked.connect(lambda: go(default_data_dir()))
        b_open.clicked.connect(lambda: open_path(self.library.data_dir))
        dlg.exec()

    def change_data_dir(self, target: Path) -> bool:
        target = Path(target)
        if target.resolve() == self.library.data_dir.resolve():
            return False
        self.save_now()
        use_existing = False
        merge = False
        if (target / LIBRARY_FILE).exists():
            box = QMessageBox(self)
            box.setWindowTitle("Library found")
            box.setText(f"There's already a SongBook library in\n{target}")
            b_use = box.addButton("Use that library", QMessageBox.ButtonRole.AcceptRole)
            b_merge = box.addButton("Merge my songs into it", QMessageBox.ButtonRole.AcceptRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.exec()
            if box.clickedButton() is b_use:
                use_existing = True
            elif box.clickedButton() is b_merge:
                use_existing = merge = True
            else:
                return False
        old_songs = self.library.all()
        old_memos = self.library.memo_dir
        try:
            self.library.move_to(target, use_existing=use_existing)
            if merge:
                for s in old_songs:
                    cur = self.library.get(s.id)
                    if cur is None or s.updated > cur.updated:
                        self.library.add(s)
                if old_memos.is_dir():
                    shutil.copytree(old_memos, self.library.memo_dir, dirs_exist_ok=True)
                self.library.save(backup=False)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Couldn't switch folder", str(e))
            return False
        self.settings.set("data_dir", str(target))
        self._update_path_label()
        self.song = None
        self.refresh_list()
        self.statusBar().showMessage(f"Now using {target}", 8000)
        return True

    # ----------------------------------------------------------------- misc
    def _shortcuts(self):
        QMessageBox.information(self, "Keyboard shortcuts",
                                "Ctrl+N  New song\nCtrl+D  Duplicate song\nF2  Rename\nCtrl+F  Search\n"
                                "Ctrl+1…4  Overview / Lyrics / Arrangement / Memos\nCtrl+S  Save now (autosave is on)\n"
                                "T  Tap tempo (Overview tab)")

    def _about(self):
        QMessageBox.about(self, f"About {APP_NAME}",
                          f"<h3 style='color:{theme.GOLD}'>{APP_NAME} {__version__}</h3>"
                          "<p>Capture song ideas: BPM & key, lyrics, arrangement, voice memos.</p>"
                          f"<p>Library file:<br><code>{self.library.path}</code></p>"
                          "<p>Built for Chazmaniac. Fonts: Inter & Oswald (SIL OFL). Rhymes: CMU Pronouncing Dictionary.</p>")

    def changeEvent(self, ev):
        if ev.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            # picked up a newer copy (e.g. OneDrive synced from another PC) while we had nothing unsaved
            if not self._dirty and self.library.changed_on_disk():
                try:
                    sid = self.song.id if self.song else None
                    self.library.load(create_demo=False)
                    self.song = None
                    self.refresh_list(select_id=sid)
                    self.statusBar().showMessage("Reloaded library (changed on disk)", 6000)
                except Exception:  # noqa: BLE001
                    pass
        super().changeEvent(ev)

    def closeEvent(self, ev):
        self.memos.shutdown()
        self.metronome.stop()
        self.settings.data["geometry"] = bytes(self.saveGeometry().toBase64()).decode()
        self.save_now()
        ev.accept()
