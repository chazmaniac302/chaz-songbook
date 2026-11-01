import json

import pytest

from chaz_songbook.model import (ArrangementBlock, LyricSection, Song, demo_song, filter_songs, sort_songs)
from chaz_songbook.store import Library, Settings, payload_to_songs


def make_song(**kw):
    s = Song(**kw)
    s.arrangement = [ArrangementBlock("Intro", "Intro", 4), ArrangementBlock("Verse", "Verse 1", 16)]
    s.lyrics = [LyricSection("Hook", "Hook", "line one\nline two")]
    return s


def test_roundtrip():
    s = demo_song()
    d = json.loads(json.dumps(s.to_dict()))
    s2 = Song.from_dict(d)
    assert s2.to_dict() == s.to_dict()


def test_from_dict_is_tolerant():
    s = Song.from_dict({"title": "X", "bpm": "abc", "key_tonic": "14", "key_scale": "Weird",
                        "status": "Nope", "unknown": 1, "arrangement": [{"bars": "x"}]})
    assert s.bpm == 0 and s.key_tonic == 2 and s.key_scale == "Minor" and s.status == "Idea"
    assert s.arrangement[0].bars == 1


def test_totals():
    s = make_song(bpm=120)
    assert s.total_bars == 20
    assert s.total_seconds == pytest.approx(40.0)
    assert s.block_start_seconds() == [0.0, 8.0]


def test_duplicate_has_new_ids():
    s = make_song(title="A")
    d = s.duplicate()
    assert d.id != s.id and d.title == "A (copy)"
    assert d.lyrics[0].id != s.lyrics[0].id
    assert d.lyrics[0].text == s.lyrics[0].text


def test_filter_and_sort():
    a = Song(title="Bravo", bpm=150, status="Done", tags=["trap"], favorite=True, key_tonic=9, key_scale="Minor")
    b = Song(title="alpha", bpm=90, status="Idea", tags=["rnb"], key_tonic=0, key_scale="Major")
    c = Song(title="Charlie", bpm=120, status="Writing", tags=["trap", "dark"])
    c.lyrics = [LyricSection(text="money on my mind")]
    songs = [a, b, c]
    assert [s.title for s in sort_songs(songs, "title")] == ["alpha", "Bravo", "Charlie"]
    assert [s.title for s in sort_songs(songs, "bpm")] == ["alpha", "Charlie", "Bravo"]
    assert [s.title for s in sort_songs(songs, "status")] == ["alpha", "Charlie", "Bravo"]
    assert [s.title for s in sort_songs(songs, "key")][-1] == "Charlie"  # no key sorts last
    assert filter_songs(songs, tag="trap") == [a, c]
    assert filter_songs(songs, status="Idea") == [b]
    assert filter_songs(songs, favorites_only=True) == [a]
    assert filter_songs(songs, query="money") == [c]
    assert filter_songs(songs, query="8A") == [a]
    assert filter_songs(songs, query="am") == [a]  # short key name


def test_next_section_label():
    s = Song()
    s.lyrics = [LyricSection("Verse", "Verse 1")]
    assert s.next_section_label("Verse") == "Verse 2"
    assert s.next_section_label("Hook") == "Hook"


def test_arrangement_from_lyrics():
    s = Song()
    s.lyrics = [LyricSection("Hook", "Hook", "a\nb\n[ad-lib]\n\nc"), LyricSection("Verse", "Verse 1", "")]
    blocks = s.arrangement_from_lyrics()
    assert [(b.label, b.bars) for b in blocks] == [("Hook", 3), ("Verse 1", 16)]


def test_library_creates_demo_and_persists(tmp_path):
    lib = Library(tmp_path / "data")
    assert len(lib.songs) == 1
    s = lib.create("Hello")
    s.bpm = 97
    lib.save()
    lib2 = Library(tmp_path / "data")
    assert lib2.get(s.id).bpm == 97
    assert len(lib2.songs) == 2


def test_library_no_demo(tmp_path):
    assert Library(tmp_path / "x", create_demo=False).songs == {}


def test_backup_rotation(tmp_path):
    lib = Library(tmp_path)
    p = lib.make_daily_backup()
    assert p and p.exists()
    assert lib.make_daily_backup() is None  # once per day
    for _ in range(20):
        lib.make_daily_backup(force=True)
    assert len(list(lib.backup_dir.glob("songbook-*.json"))) <= 15


def test_corrupt_file_recovers_from_backup(tmp_path):
    lib = Library(tmp_path)
    sid = lib.create("Keep me").id
    lib.save()
    lib.make_daily_backup(force=True)
    lib.path.write_text("{not json", encoding="utf-8")
    lib2 = Library(tmp_path)
    assert sid in lib2.songs
    assert list(tmp_path.glob("songbook.corrupt-*.json"))


def test_corrupt_without_backup_raises(tmp_path):
    (tmp_path / "songbook.json").write_text("garbage", encoding="utf-8")
    with pytest.raises(RuntimeError):
        Library(tmp_path)


def test_export_import_merge(tmp_path):
    a = Library(tmp_path / "a", create_demo=False)
    s = a.create("Shared")
    a.save()
    a.export_json(tmp_path / "backup.json")
    b = Library(tmp_path / "b", create_demo=False)
    assert b.import_json(tmp_path / "backup.json") == (1, 0)
    assert b.import_json(tmp_path / "backup.json") == (0, 0)  # same, not newer
    s.title = "Shared v2"
    s.updated = "2999-01-01T00:00:00+00:00"
    a.export_json(tmp_path / "backup2.json")
    assert b.import_json(tmp_path / "backup2.json") == (0, 1)
    assert b.get(s.id).title == "Shared v2"


def test_payload_variants():
    one = Song(title="Solo").to_dict()
    assert payload_to_songs(one)[0].title == "Solo"
    assert payload_to_songs([one])[0].title == "Solo"
    with pytest.raises(ValueError):
        payload_to_songs({"foo": 1})


def test_move_to_and_conflict_copy(tmp_path):
    lib = Library(tmp_path / "local")
    n = len(lib.songs)
    lib.move_to(tmp_path / "onedrive")
    assert lib.path == tmp_path / "onedrive" / "songbook.json" and len(lib.songs) == n
    # simulate another PC writing the file
    import os, time
    data = lib.path.read_text(encoding="utf-8")
    lib.path.write_text(data, encoding="utf-8")
    os.utime(lib.path, (time.time() + 5, time.time() + 5))
    assert lib.changed_on_disk()
    lib.save(backup=False)
    assert list((tmp_path / "onedrive").glob("songbook.conflict-*.json"))


def test_delete_moves_memos(tmp_path):
    lib = Library(tmp_path, create_demo=False)
    s = lib.create("x")
    d = lib.memo_dir / s.id
    d.mkdir(parents=True)
    (d / "a.wav").write_bytes(b"RIFF")
    lib.delete(s.id)
    assert s.id not in lib.songs
    assert (tmp_path / "deleted-memos" / s.id / "a.wav").exists()


def test_settings(tmp_path):
    st = Settings(tmp_path)
    assert st.data_dir == tmp_path or st.data_dir  # default is config dir
    st.set("data_dir", str(tmp_path / "od"))
    assert Settings(tmp_path).data_dir == tmp_path / "od"
