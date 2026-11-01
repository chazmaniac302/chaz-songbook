"""Data model for songs. Plain dataclasses that round-trip to JSON-safe dicts."""
from __future__ import annotations

import copy
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone

from . import music

STATUSES = ["Idea", "Writing", "Recording", "Mixing", "Done"]

SECTION_TYPES = ["Intro", "Hook", "Pre-Hook", "Verse", "Bridge", "Breakdown",
                 "Drop", "Interlude", "Outro", "Skit", "Other"]

SECTION_COLORS = {
    "Intro": "#6B5B95",
    "Hook": "#D4AF37",
    "Pre-Hook": "#C9822B",
    "Verse": "#B3122E",
    "Bridge": "#2E7D6B",
    "Breakdown": "#3D5A80",
    "Drop": "#E0475B",
    "Interlude": "#5C6B73",
    "Outro": "#7A5C3E",
    "Skit": "#8E6C8A",
    "Other": "#4A4A4A",
}

DEFAULT_BARS = {"Intro": 4, "Hook": 8, "Pre-Hook": 4, "Verse": 16, "Bridge": 8,
                "Breakdown": 8, "Drop": 8, "Interlude": 4, "Outro": 4, "Skit": 4, "Other": 8}

SUGGESTED_TAGS = ["trap", "hip-hop", "rnb", "drill", "boom bap", "melodic", "dark", "chill",
                  "love", "hype", "sad", "club", "lofi", "soul", "plugg", "jersey", "afro"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def _from_dict(cls, data: dict):
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in (data or {}).items() if k in names})


@dataclass
class LyricSection:
    type: str = "Verse"
    label: str = "Verse 1"
    text: str = ""
    id: str = field(default_factory=new_id)

    @classmethod
    def from_dict(cls, d: dict) -> "LyricSection":
        return _from_dict(cls, d)


@dataclass
class ArrangementBlock:
    type: str = "Verse"
    label: str = "Verse"
    bars: int = 16
    notes: str = ""
    id: str = field(default_factory=new_id)

    @classmethod
    def from_dict(cls, d: dict) -> "ArrangementBlock":
        b = _from_dict(cls, d)
        try:
            b.bars = max(1, int(b.bars))
        except (TypeError, ValueError):
            b.bars = 1
        return b

    @property
    def color(self) -> str:
        return SECTION_COLORS.get(self.type, SECTION_COLORS["Other"])


@dataclass
class Reference:
    title: str = ""
    url: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Reference":
        return _from_dict(cls, d)


@dataclass
class VoiceMemo:
    name: str = "Memo"
    file: str = ""          # path relative to the data folder
    created: str = field(default_factory=now_iso)
    duration: float = 0.0
    id: str = field(default_factory=new_id)

    @classmethod
    def from_dict(cls, d: dict) -> "VoiceMemo":
        return _from_dict(cls, d)


@dataclass
class Song:
    title: str = "Untitled"
    artist: str = ""
    features: str = ""
    bpm: float = 140.0
    key_tonic: int | None = None
    key_scale: str = "Minor"
    time_signature: str = "4/4"
    status: str = "Idea"
    tags: list[str] = field(default_factory=list)
    favorite: bool = False
    references: list[Reference] = field(default_factory=list)
    beat_files: list[str] = field(default_factory=list)
    notes: str = ""
    lyrics: list[LyricSection] = field(default_factory=list)
    arrangement: list[ArrangementBlock] = field(default_factory=list)
    memos: list[VoiceMemo] = field(default_factory=list)
    created: str = field(default_factory=now_iso)
    updated: str = field(default_factory=now_iso)
    id: str = field(default_factory=new_id)

    # ---- serialisation -------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Song":
        d = dict(d or {})
        s = _from_dict(cls, d)
        s.references = [Reference.from_dict(x) for x in d.get("references", []) or []]
        s.lyrics = [LyricSection.from_dict(x) for x in d.get("lyrics", []) or []]
        s.arrangement = [ArrangementBlock.from_dict(x) for x in d.get("arrangement", []) or []]
        s.memos = [VoiceMemo.from_dict(x) for x in d.get("memos", []) or []]
        s.tags = [str(t) for t in (d.get("tags") or [])]
        s.beat_files = [str(p) for p in (d.get("beat_files") or [])]
        try:
            s.bpm = float(s.bpm) if s.bpm not in (None, "") else 0.0
        except (TypeError, ValueError):
            s.bpm = 0.0
        if s.key_tonic is not None:
            try:
                s.key_tonic = int(s.key_tonic) % 12
            except (TypeError, ValueError):
                s.key_tonic = None
        if s.key_scale not in music.SCALES:
            s.key_scale = "Minor"
        if s.status not in STATUSES:
            s.status = "Idea"
        return s

    # ---- derived values ------------------------------------------------
    def touch(self) -> None:
        self.updated = now_iso()

    @property
    def key_display(self) -> str:
        return music.key_name(self.key_tonic, self.key_scale)

    @property
    def camelot(self) -> str:
        return music.camelot(self.key_tonic, self.key_scale)

    @property
    def total_bars(self) -> int:
        return sum(b.bars for b in self.arrangement)

    @property
    def total_seconds(self) -> float:
        return music.bars_to_seconds(self.total_bars, self.bpm, self.time_signature)

    def block_start_seconds(self) -> list[float]:
        out, acc = [], 0
        for b in self.arrangement:
            out.append(music.bars_to_seconds(acc, self.bpm, self.time_signature))
            acc += b.bars
        return out

    def duplicate(self) -> "Song":
        d = copy.deepcopy(self.to_dict())
        d["id"] = new_id()
        d["title"] = f"{self.title} (copy)"
        d["created"] = d["updated"] = now_iso()
        d["favorite"] = False
        d["memos"] = []  # audio files are not duplicated
        for key in ("lyrics", "arrangement"):
            for item in d[key]:
                item["id"] = new_id()
        return Song.from_dict(d)

    def next_section_label(self, sec_type: str, items=None) -> str:
        items = self.lyrics if items is None else items
        if sec_type in ("Verse",):
            n = sum(1 for s in items if s.type == sec_type) + 1
            return f"{sec_type} {n}"
        return sec_type

    def arrangement_from_lyrics(self) -> list[ArrangementBlock]:
        from .lyrics import count_bars
        blocks = []
        for sec in self.lyrics:
            bars = count_bars(sec.text) or DEFAULT_BARS.get(sec.type, 8)
            blocks.append(ArrangementBlock(type=sec.type, label=sec.label, bars=bars))
        return blocks

    def matches(self, query: str) -> bool:
        q = (query or "").strip().lower()
        if not q:
            return True
        hay = " ".join([
            self.title, self.artist, self.features, self.notes, " ".join(self.tags),
            self.key_display, music.short_key(self.key_tonic, self.key_scale), self.camelot,
            self.status, str(int(self.bpm)) if self.bpm else "",
            " ".join(s.text for s in self.lyrics),
        ]).lower()
        return all(term in hay for term in q.split())


def sort_songs(songs: list[Song], key: str) -> list[Song]:
    key = key or "updated"
    if key == "title":
        return sorted(songs, key=lambda s: s.title.lower())
    if key == "bpm":
        return sorted(songs, key=lambda s: (s.bpm or 0, s.title.lower()))
    if key == "key":
        return sorted(songs, key=lambda s: (s.camelot == "", _camelot_sort(s.camelot), s.title.lower()))
    if key == "status":
        return sorted(songs, key=lambda s: (STATUSES.index(s.status), s.title.lower()))
    if key == "created":
        return sorted(songs, key=lambda s: s.created, reverse=True)
    return sorted(songs, key=lambda s: s.updated, reverse=True)


def _camelot_sort(code: str):
    if not code:
        return (99, "")
    return (int(code[:-1]), code[-1])


def filter_songs(songs, query="", status=None, tag=None, favorites_only=False):
    out = []
    for s in songs:
        if status and s.status != status:
            continue
        if tag and tag.lower() not in (t.lower() for t in s.tags):
            continue
        if favorites_only and not s.favorite:
            continue
        if not s.matches(query):
            continue
        out.append(s)
    return out


def demo_song() -> Song:
    s = Song(
        title="Gold Teeth Sunrise (example)",
        artist="Chazmaniac",
        features="",
        bpm=142.0, key_tonic=1, key_scale="Minor", status="Writing",
        tags=["trap", "melodic", "dark"], favorite=True,
        references=[Reference("Vibe: slow pads + hard 808", "https://www.youtube.com/")],
        notes="Example song so you can see how everything fits. Delete it whenever.\n"
              "• Bells + choir pad, 808 glide on the hook\n• Try halftime switch in the bridge",
    )
    s.lyrics = [
        LyricSection("Intro", "Intro", "Yeah, uh\nSun comin' up and I'm still in the lab"),
        LyricSection("Hook", "Hook", "Gold on my teeth when the sun hit the glass\n"
                     "Ran it up slow but I'm movin' it fast\nNever look back, I don't live in the past\n"
                     "Gold on my teeth, yeah, I'm built for the bag"),
        LyricSection("Verse", "Verse 1", "Started with nothin' but a dream and a pad\n"
                     "Four in the mornin' with the 808 bad\nMama said keep it, the vision I had\n"
                     "Now every beat that I cook is a smash"),
        LyricSection("Bridge", "Bridge", ""),
    ]
    s.arrangement = [
        ArrangementBlock("Intro", "Intro", 4, "Filtered bells, no drums"),
        ArrangementBlock("Hook", "Hook", 8, "Full drums, 808 glide"),
        ArrangementBlock("Verse", "Verse 1", 16, "Drop 808 on bar 1, hat rolls every 4"),
        ArrangementBlock("Hook", "Hook", 8, ""),
        ArrangementBlock("Bridge", "Bridge", 8, "Halftime, reverse cymbal into hook"),
        ArrangementBlock("Hook", "Hook", 8, "Add choir layer"),
        ArrangementBlock("Outro", "Outro", 4, "Strip to pads"),
    ]
    return s
