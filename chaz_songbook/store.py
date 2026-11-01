"""Persistence: a single JSON library file with atomic writes and rolling backups."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from . import __version__
from .model import Song, demo_song
from .paths import config_dir, default_data_dir

LIBRARY_FILE = "songbook.json"
SETTINGS_FILE = "settings.json"
FORMAT_VERSION = 1
MAX_BACKUPS = 15


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class Settings:
    def __init__(self, directory: Path | None = None):
        self.dir = Path(directory) if directory else config_dir()
        self.path = self.dir / SETTINGS_FILE
        self.data: dict = {}
        self.load()

    def load(self) -> None:
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(self.data, dict):
                self.data = {}
        except (OSError, ValueError):
            self.data = {}

    def save(self) -> None:
        atomic_write_text(self.path, json.dumps(self.data, indent=2))

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value) -> None:
        self.data[key] = value
        self.save()

    @property
    def data_dir(self) -> Path:
        d = self.data.get("data_dir")
        return Path(d) if d else default_data_dir()


def songs_to_payload(songs: list[Song]) -> dict:
    return {
        "app": "Chaz SongBook",
        "app_version": __version__,
        "format": FORMAT_VERSION,
        "saved": datetime.now().isoformat(timespec="seconds"),
        "songs": [s.to_dict() for s in songs],
    }


def payload_to_songs(payload) -> list[Song]:
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict) and "songs" in payload:
        items = payload["songs"]
    elif isinstance(payload, dict) and "title" in payload:
        items = [payload]  # a single exported song
    else:
        raise ValueError("Not a Chaz SongBook file")
    if not isinstance(items, list):
        raise ValueError("Not a Chaz SongBook file")
    return [Song.from_dict(x) for x in items if isinstance(x, dict)]


class Library:
    """All songs, persisted in <data_dir>/songbook.json."""

    def __init__(self, data_dir: Path, create_demo: bool = True):
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / LIBRARY_FILE
        self.songs: dict[str, Song] = {}
        self._loaded_mtime: float | None = None
        self.load(create_demo=create_demo)

    # -- io ---------------------------------------------------------------
    def load(self, create_demo: bool = True) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.songs = {}
            if create_demo:
                s = demo_song()
                self.songs[s.id] = s
            self.save(backup=False)
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            songs = payload_to_songs(payload)
        except (OSError, ValueError) as e:
            # keep the unreadable file aside, never overwrite it silently
            bad = self.path.with_name(f"songbook.corrupt-{datetime.now():%Y%m%d-%H%M%S}.json")
            try:
                shutil.copy2(self.path, bad)
            except OSError:
                pass
            restored = self._restore_latest_backup()
            if restored is None:
                raise RuntimeError(f"Could not read {self.path}: {e}. A copy was kept at {bad}") from e
            songs = restored
        self.songs = {s.id: s for s in songs}
        self._loaded_mtime = self._mtime()

    def _restore_latest_backup(self) -> list[Song] | None:
        for b in self._backups_newest_first():
            try:
                return payload_to_songs(json.loads(b.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return None

    def _backups_newest_first(self) -> list[Path]:
        """Daily backups are named songbook-YYYYMMDD (taken at the day's first save, so they are the
        oldest of that day); forced ones songbook-YYYYMMDD-HHMMSS. Order by that, then mtime."""
        def key(p: Path):
            stamp = p.stem[len("songbook-"):]
            stamp = stamp if "-" in stamp else stamp + "-000000"
            try:
                m = p.stat().st_mtime
            except OSError:
                m = 0.0
            return (stamp, m)
        return sorted(self.backup_dir.glob("songbook-*.json"), key=key, reverse=True)

    def _mtime(self) -> float | None:
        try:
            return self.path.stat().st_mtime
        except OSError:
            return None

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def memo_dir(self) -> Path:
        return self.data_dir / "memos"

    def changed_on_disk(self) -> bool:
        m = self._mtime()
        return m is not None and self._loaded_mtime is not None and abs(m - self._loaded_mtime) > 1e-6

    def save(self, backup: bool = True) -> None:
        if backup:
            self.make_daily_backup()
        if self.changed_on_disk():
            # another device (e.g. OneDrive sync) changed the file: keep their copy
            keep = self.path.with_name(f"songbook.conflict-{datetime.now():%Y%m%d-%H%M%S}.json")
            try:
                shutil.copy2(self.path, keep)
            except OSError:
                pass
        atomic_write_text(self.path, json.dumps(songs_to_payload(self.all()), indent=1, ensure_ascii=False))
        self._loaded_mtime = self._mtime()

    def make_daily_backup(self, force: bool = False) -> Path | None:
        if not self.path.exists():
            return None
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d") if not force else datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = self.backup_dir / f"songbook-{stamp}.json"
        if dest.exists() and not force:
            return None
        shutil.copy2(self.path, dest)
        for old in self._backups_newest_first()[MAX_BACKUPS:]:
            try:
                old.unlink()
            except OSError:
                pass
        return dest

    # -- crud -------------------------------------------------------------
    def all(self) -> list[Song]:
        return list(self.songs.values())

    def get(self, song_id: str) -> Song | None:
        return self.songs.get(song_id)

    def add(self, song: Song) -> Song:
        self.songs[song.id] = song
        return song

    def create(self, title: str = "New Song") -> Song:
        return self.add(Song(title=title))

    def delete(self, song_id: str) -> None:
        song = self.songs.pop(song_id, None)
        if song:
            d = self.memo_dir / song_id
            if d.is_dir():
                trash = self.data_dir / "deleted-memos" / song_id
                trash.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(str(d), str(trash))
                except OSError:
                    pass

    def duplicate(self, song_id: str) -> Song | None:
        s = self.get(song_id)
        return self.add(s.duplicate()) if s else None

    def all_tags(self) -> list[str]:
        tags = {t.strip() for s in self.songs.values() for t in s.tags if t.strip()}
        return sorted(tags, key=str.lower)

    # -- import / export ------------------------------------------------
    def export_json(self, dest: Path, songs: list[Song] | None = None) -> None:
        atomic_write_text(Path(dest), json.dumps(songs_to_payload(songs or self.all()), indent=1, ensure_ascii=False))

    def import_json(self, src: Path) -> tuple[int, int]:
        """Import songs. Same id -> keep the newer `updated`. Returns (added, updated)."""
        songs = payload_to_songs(json.loads(Path(src).read_text(encoding="utf-8")))
        added = updated = 0
        for s in songs:
            cur = self.songs.get(s.id)
            if cur is None:
                self.songs[s.id] = s
                added += 1
            elif s.updated > cur.updated:
                self.songs[s.id] = s
                updated += 1
        return added, updated

    def move_to(self, new_dir: Path, use_existing: bool = False) -> None:
        """Point the library at another folder. Copies data unless use_existing."""
        new_dir = Path(new_dir)
        new_dir.mkdir(parents=True, exist_ok=True)
        if not use_existing:
            if self.memo_dir.is_dir():
                shutil.copytree(self.memo_dir, new_dir / "memos", dirs_exist_ok=True)
            atomic_write_text(new_dir / LIBRARY_FILE,
                              json.dumps(songs_to_payload(self.all()), indent=1, ensure_ascii=False))
        self.data_dir = new_dir
        self.path = new_dir / LIBRARY_FILE
        self.load(create_demo=False)
