from chaz_songbook import export as ex
from chaz_songbook.model import demo_song


def test_markdown():
    md = ex.to_markdown(demo_song())
    assert md.startswith("# Gold Teeth Sunrise")
    assert "**BPM:** 142" in md
    assert "C# minor (12A, Relative: E major)" in md
    assert "| 3 | Verse 1 | 16 | 13 / 0:20 |" in md
    assert "**Total:** 56 bars · 1:35" in md
    assert "### Hook" in md


def test_text():
    t = ex.to_text(demo_song())
    assert "ARRANGEMENT" in t and "LYRICS" in t and "[Verse 1]" in t
    assert "Total: 56 bars" in t


def test_html_escapes():
    s = demo_song()
    s.title = "<b>Bad & Boujee</b>"
    h = ex.to_html(s)
    assert "&lt;b&gt;Bad &amp; Boujee&lt;/b&gt;" in h


def test_files(tmp_path, qapp):
    s = demo_song()
    for ext in ("md", "txt", "html", "pdf"):
        p = ex.export_song(s, tmp_path / f"x.{ext}")
        assert p.stat().st_size > 300
    assert (tmp_path / "x.pdf").read_bytes().startswith(b"%PDF")


def test_safe_filename():
    assert ex.safe_filename('a/b:c*?"<>|') == "a_b_c______"
    assert ex.safe_filename("  ...") == "song"
