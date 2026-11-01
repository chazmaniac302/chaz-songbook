"""Offscreen UI tests: the real windows, driven programmatically."""
import os

from chaz_songbook.app import run_smoke_test


def test_smoke(qapp, tmp_path):
    out = tmp_path / "smoke.txt"
    assert run_smoke_test(str(out)) == 0, out.read_text()
    assert "SMOKE OK" in out.read_text()


def test_main_window_flows(qapp, tmp_path):
    from chaz_songbook.store import Library, Settings
    from chaz_songbook.ui.main_window import MainWindow
    lib = Library(tmp_path / "data")
    w = MainWindow(Settings(tmp_path / "cfg"), lib)
    w.show()
    qapp.processEvents()
    assert w.list.count() == 1
    s = w.new_song()
    assert w.list.count() == 2 and w.song is s
    w.duplicate_song()
    assert len(lib.songs) == 3
    # search filters the list
    w.search.setText("Gold Teeth")
    assert w.list.count() == 1
    w.search.clear()
    w.fav_btn.setChecked(True)
    assert w.list.count() == 1
    w.fav_btn.setChecked(False)
    # tap tempo through the UI
    w.list.setCurrentRow(0)
    song = w.song
    w.overview.tap.tap(0.0)
    w.overview.tap.tap(0.5)
    w.overview._on_tap()
    assert song.bpm > 0
    # arrangement drag-move from the timeline signal
    w.list.setCurrentRow([i for i in range(w.list.count()) if w.list.item(i).text().startswith("Gold")][0])
    first = w.song.arrangement[0].label
    w.arrangement.timeline.moved.emit(0, 2)
    assert w.song.arrangement[2].label == first
    # lyric section add + text
    n = len(w.song.lyrics)
    w.lyrics.add_section("Verse")
    assert len(w.song.lyrics) == n + 1 and w.song.lyrics[-1 if n == 0 else 1].label
    w.lyrics.editor.setPlainText("testing one two")
    assert any("testing one two" == x.text for x in w.song.lyrics)
    # data folder switch
    assert w.change_data_dir(tmp_path / "onedrive")
    assert (tmp_path / "onedrive" / "songbook.json").exists()
    assert len(w.library.songs) == 3
    w.close()
