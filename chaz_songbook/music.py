"""Music theory helpers: keys, scales, relative keys, Camelot codes, tempo math."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

NOTE_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
NOTE_LABELS = ["C", "C♯ / D♭", "D", "D♯ / E♭", "E", "F", "F♯ / G♭", "G", "G♯ / A♭", "A", "A♯ / B♭", "B"]
# Names used in Camelot / DJ-style display (minor keys conventionally use these spellings)
MINOR_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "Bb", "B"]
MAJOR_NAMES = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

SCALES: dict[str, list[int]] = {
    "Major": [0, 2, 4, 5, 7, 9, 11],
    "Minor": [0, 2, 3, 5, 7, 8, 10],
    "Harmonic Minor": [0, 2, 3, 5, 7, 8, 11],
    "Dorian": [0, 2, 3, 5, 7, 9, 10],
    "Phrygian": [0, 1, 3, 5, 7, 8, 10],
    "Lydian": [0, 2, 4, 6, 7, 9, 11],
    "Mixolydian": [0, 2, 4, 5, 7, 9, 10],
}
SCALE_NAMES = list(SCALES)
MINOR_LIKE = {"Minor", "Harmonic Minor", "Dorian", "Phrygian"}
# semitone offset from mode tonic to its parent major key (same key signature)
PARENT_MAJOR_OFFSET = {
    "Major": 0, "Minor": 3, "Harmonic Minor": 3, "Dorian": -2,
    "Phrygian": -4, "Lydian": -5, "Mixolydian": -7,
}

TIME_SIGNATURES = ["4/4", "3/4", "6/8", "12/8", "5/4", "7/8", "2/4"]


def note_name(pc: int, scale: str = "Major") -> str:
    pc %= 12
    return (MINOR_NAMES if scale in MINOR_LIKE else MAJOR_NAMES)[pc]


def key_name(pc: int | None, scale: str) -> str:
    if pc is None:
        return "—"
    if scale == "Major":
        return f"{note_name(pc, scale)} major"
    if scale == "Minor":
        return f"{note_name(pc, scale)} minor"
    return f"{note_name(pc, scale)} {scale.lower()}"


def short_key(pc: int | None, scale: str) -> str:
    """Compact form like 'Am', 'F#', 'D dor'."""
    if pc is None:
        return ""
    n = note_name(pc, scale)
    return {"Major": n, "Minor": n + "m", "Harmonic Minor": n + "m(h)"}.get(scale, f"{n} {scale[:3].lower()}")


def camelot_number_for_major(pc: int) -> int:
    return (7 * (pc % 12) + 7) % 12 + 1


def camelot(pc: int | None, scale: str) -> str:
    """Camelot wheel code. Modes map to the code of their parent key signature
    (B for major-like parent; minor/harmonic minor use the A ring)."""
    if pc is None or scale not in SCALES:
        return ""
    if scale in ("Minor", "Harmonic Minor"):
        return f"{camelot_number_for_major(pc + 3)}A"
    if scale == "Major":
        return f"{camelot_number_for_major(pc)}B"
    parent = (pc + PARENT_MAJOR_OFFSET[scale]) % 12
    return f"{camelot_number_for_major(parent)}B"


def relative_key(pc: int | None, scale: str) -> tuple[int, str] | None:
    """Relative major/minor. For modes, returns the parent major key."""
    if pc is None:
        return None
    if scale == "Major":
        return ((pc + 9) % 12, "Minor")
    if scale in ("Minor", "Harmonic Minor"):
        return ((pc + 3) % 12, "Major")
    return ((pc + PARENT_MAJOR_OFFSET[scale]) % 12, "Major")


def relative_label(pc: int | None, scale: str) -> str:
    rel = relative_key(pc, scale)
    if rel is None:
        return ""
    prefix = "Relative" if scale in ("Major", "Minor", "Harmonic Minor") else "Parent"
    return f"{prefix}: {key_name(*rel)}"


def scale_notes(pc: int | None, scale: str) -> list[str]:
    if pc is None or scale not in SCALES:
        return []
    names = MINOR_NAMES if scale in MINOR_LIKE else MAJOR_NAMES
    if scale == "Major" and pc in (5, 10, 3, 8, 1):  # flat keys: use flats
        names = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
    return [names[(pc + i) % 12] for i in SCALES[scale]]


def compatible_camelot(code: str) -> list[str]:
    """Harmonically compatible Camelot codes (same, +/-1, relative)."""
    if not code:
        return []
    n, ring = int(code[:-1]), code[-1]
    other = "B" if ring == "A" else "A"
    up = n % 12 + 1
    down = (n - 2) % 12 + 1
    return [code, f"{up}{ring}", f"{down}{ring}", f"{n}{other}"]


def parse_time_signature(ts: str) -> tuple[int, int]:
    try:
        a, b = ts.split("/")
        num, den = int(a), int(b)
        if num <= 0 or den not in (1, 2, 4, 8, 16):
            raise ValueError
        return num, den
    except Exception:
        return 4, 4


def seconds_per_bar(bpm: float, time_signature: str = "4/4") -> float:
    """BPM counts quarter notes (FL Studio / Maschine convention)."""
    if not bpm or bpm <= 0:
        return 0.0
    num, den = parse_time_signature(time_signature)
    quarters = num * 4.0 / den
    return quarters * 60.0 / bpm


def bars_to_seconds(bars: float, bpm: float, time_signature: str = "4/4") -> float:
    return max(0.0, bars) * seconds_per_bar(bpm, time_signature)


def format_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def halftime(bpm: float) -> float:
    return round(bpm / 2.0, 2)


def doubletime(bpm: float) -> float:
    return round(bpm * 2.0, 2)


def ms_per_beat(bpm: float) -> float:
    return 60000.0 / bpm if bpm > 0 else 0.0


@dataclass
class TapTempo:
    """Tap-tempo estimator. Resets after `timeout` seconds without a tap."""
    timeout: float = 2.0
    max_taps: int = 8
    taps: list[float] = field(default_factory=list)

    def tap(self, t: float | None = None) -> float | None:
        t = time.monotonic() if t is None else t
        if self.taps and t - self.taps[-1] > self.timeout:
            self.taps.clear()
        self.taps.append(t)
        self.taps = self.taps[-self.max_taps:]
        return self.bpm()

    def bpm(self) -> float | None:
        if len(self.taps) < 2:
            return None
        intervals = [b - a for a, b in zip(self.taps, self.taps[1:])]
        avg = sum(intervals) / len(intervals)
        if avg <= 0:
            return None
        return round(60.0 / avg, 1)

    def reset(self) -> None:
        self.taps.clear()
