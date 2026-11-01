import pytest

from chaz_songbook import music


@pytest.mark.parametrize("pc,scale,code", [
    (9, "Minor", "8A"), (0, "Major", "8B"), (8, "Minor", "1A"), (11, "Major", "1B"),
    (4, "Minor", "9A"), (7, "Major", "9B"), (1, "Minor", "12A"), (4, "Major", "12B"),
    (6, "Minor", "11A"), (3, "Major", "5B"), (5, "Minor", "4A"), (10, "Major", "6B"),
    (0, "Minor", "5A"), (2, "Minor", "7A"), (7, "Minor", "6A"), (11, "Minor", "10A"),
])
def test_camelot_major_minor(pc, scale, code):
    assert music.camelot(pc, scale) == code


def test_full_camelot_wheel_is_bijective():
    codes = {music.camelot(pc, sc) for pc in range(12) for sc in ("Major", "Minor")}
    assert len(codes) == 24
    assert codes == {f"{n}{r}" for n in range(1, 13) for r in "AB"}


def test_relative_keys_share_camelot_number():
    for pc in range(12):
        rel_pc, rel_scale = music.relative_key(pc, "Major")
        assert rel_scale == "Minor"
        assert music.camelot(pc, "Major")[:-1] == music.camelot(rel_pc, "Minor")[:-1]


def test_relative_labels():
    assert music.relative_label(0, "Major") == "Relative: A minor"
    assert music.relative_label(9, "Minor") == "Relative: C major"
    assert music.relative_label(1, "Minor") == "Relative: E major"
    assert music.relative_label(2, "Dorian") == "Parent: C major"
    assert music.relative_label(None, "Minor") == ""


def test_modes_map_to_parent_key():
    assert music.camelot(2, "Dorian") == "8B"      # D dorian = C major
    assert music.camelot(7, "Mixolydian") == "8B"  # G mixolydian = C major
    assert music.camelot(4, "Phrygian") == "8B"
    assert music.camelot(5, "Lydian") == "8B"
    assert music.camelot(9, "Harmonic Minor") == "8A"
    assert music.camelot(None, "Minor") == ""


def test_scale_notes():
    assert music.scale_notes(0, "Major") == ["C", "D", "E", "F", "G", "A", "B"]
    assert music.scale_notes(9, "Minor") == ["A", "B", "C", "D", "E", "F", "G"]
    assert music.scale_notes(5, "Major") == ["F", "G", "A", "Bb", "C", "D", "E"]
    assert music.scale_notes(None, "Major") == []


def test_key_names():
    assert music.key_name(1, "Minor") == "C# minor"
    assert music.key_name(10, "Major") == "Bb major"
    assert music.short_key(9, "Minor") == "Am"
    assert music.key_name(None, "Minor") == "—"


def test_compatible():
    assert music.compatible_camelot("8A") == ["8A", "9A", "7A", "8B"]
    assert music.compatible_camelot("12B") == ["12B", "1B", "11B", "12A"]
    assert music.compatible_camelot("1A") == ["1A", "2A", "12A", "1B"]


@pytest.mark.parametrize("bpm,ts,bars,secs", [
    (120, "4/4", 1, 2.0), (120, "4/4", 16, 32.0), (140, "4/4", 64, 64 * 240 / 140),
    (90, "3/4", 4, 4 * 3 * 60 / 90), (120, "6/8", 2, 2 * 1.5), (60, "4/4", 0, 0.0),
])
def test_bars_to_seconds(bpm, ts, bars, secs):
    assert music.bars_to_seconds(bars, bpm, ts) == pytest.approx(secs)


def test_zero_bpm_is_safe():
    assert music.seconds_per_bar(0) == 0
    assert music.ms_per_beat(0) == 0


def test_time_signature_parsing():
    assert music.parse_time_signature("7/8") == (7, 8)
    assert music.parse_time_signature("garbage") == (4, 4)
    assert music.parse_time_signature("4/3") == (4, 4)


def test_format_duration():
    assert music.format_duration(0) == "0:00"
    assert music.format_duration(95.4) == "1:35"
    assert music.format_duration(3725) == "1:02:05"


def test_tap_tempo():
    t = music.TapTempo()
    assert t.tap(0.0) is None
    for i in range(1, 6):
        bpm = t.tap(i * 0.5)
    assert bpm == 120.0
    # long pause resets
    assert t.tap(100.0) is None
    t.tap(100.4285714)
    assert t.bpm() == pytest.approx(140.0, abs=0.1)


def test_half_double():
    assert music.halftime(140) == 70
    assert music.doubletime(70) == 140
