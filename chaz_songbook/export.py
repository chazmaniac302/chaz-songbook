"""Song sheet export: Markdown, plain text, HTML and PDF."""
from __future__ import annotations

import html
from pathlib import Path

from . import music
from .lyrics import stats
from .model import Song


def _meta_rows(song: Song) -> list[tuple[str, str]]:
    rows = [("Artist", song.artist), ("Features", song.features), ("Status", song.status)]
    if song.bpm:
        rows.append(("BPM", f"{song.bpm:g}"))
    if song.key_tonic is not None:
        k = song.key_display
        extra = [x for x in (song.camelot, music.relative_label(song.key_tonic, song.key_scale)) if x]
        rows.append(("Key", f"{k} ({', '.join(extra)})" if extra else k))
        rows.append(("Scale notes", " ".join(music.scale_notes(song.key_tonic, song.key_scale))))
    rows.append(("Time signature", song.time_signature))
    if song.arrangement:
        rows.append(("Length", f"{song.total_bars} bars · {music.format_duration(song.total_seconds)}"))
    if song.tags:
        rows.append(("Tags", ", ".join(song.tags)))
    return [(k, v) for k, v in rows if v]


def _arrangement_rows(song: Song):
    starts = song.block_start_seconds()
    bar = 1
    for b, t in zip(song.arrangement, starts):
        yield b, bar, music.format_duration(t)
        bar += b.bars


def to_markdown(song: Song) -> str:
    out = [f"# {song.title}", ""]
    for k, v in _meta_rows(song):
        out.append(f"- **{k}:** {v}")
    out.append("")
    if song.references:
        out += ["## References", ""]
        out += [f"- {r.title or r.url}" + (f" — <{r.url}>" if r.url and r.title else "") for r in song.references]
        out.append("")
    if song.beat_files:
        out += ["## Beat files", ""] + [f"- `{p}`" for p in song.beat_files] + [""]
    if song.arrangement:
        out += ["## Arrangement", "", "| # | Section | Bars | Starts (bar / time) | Notes |", "|---|---|---|---|---|"]
        for i, (b, bar, t) in enumerate(_arrangement_rows(song), 1):
            notes = b.notes.replace("|", "\\|").replace("\n", " ")
            out.append(f"| {i} | {b.label or b.type} | {b.bars} | {bar} / {t} | {notes} |")
        out += ["", f"**Total:** {song.total_bars} bars · {music.format_duration(song.total_seconds)}", ""]
    if song.lyrics:
        out += ["## Lyrics", ""]
        for sec in song.lyrics:
            st = stats(sec.text)
            out.append(f"### {sec.label or sec.type}  _( {st['bars']} bars · {st['words']} words )_")
            out.append("")
            out += [(line + "  ") if line.strip() else "" for line in sec.text.splitlines()]
            out.append("")
    if song.notes.strip():
        out += ["## Notes", "", song.notes.strip(), ""]
    return "\n".join(out).rstrip() + "\n"


def to_text(song: Song) -> str:
    title = song.title.upper()
    out = [title, "=" * len(title), ""]
    for k, v in _meta_rows(song):
        out.append(f"{k}: {v}")
    out.append("")
    if song.references:
        out += ["REFERENCES"] + [f"  - {r.title} {r.url}".rstrip() for r in song.references] + [""]
    if song.beat_files:
        out += ["BEAT FILES"] + [f"  - {p}" for p in song.beat_files] + [""]
    if song.arrangement:
        out.append("ARRANGEMENT")
        for i, (b, bar, t) in enumerate(_arrangement_rows(song), 1):
            line = f"  {i:>2}. {(b.label or b.type):<14} {b.bars:>3} bars  @ bar {bar:<4} {t}"
            out.append(line + (f"  — {b.notes}" if b.notes else ""))
        out += [f"  Total: {song.total_bars} bars · {music.format_duration(song.total_seconds)}", ""]
    if song.lyrics:
        out.append("LYRICS")
        for sec in song.lyrics:
            out += ["", f"[{sec.label or sec.type}]"] + sec.text.splitlines()
        out.append("")
    if song.notes.strip():
        out += ["NOTES", song.notes.strip(), ""]
    return "\n".join(out).rstrip() + "\n"


def to_html(song: Song) -> str:
    e = html.escape
    gold, crimson = "#B8901F", "#A3122A"
    parts = [f"""<html><head><meta charset="utf-8"><style>
body {{ font-family: 'Inter','Segoe UI',Arial,sans-serif; color:#111; font-size:10.5pt; }}
h1 {{ font-family: 'Oswald','Bahnschrift',sans-serif; color:{crimson}; font-size:24pt; margin-bottom:2pt; }}
h2 {{ font-family: 'Oswald','Bahnschrift',sans-serif; color:{gold}; font-size:14pt; border-bottom:1px solid {gold}; margin-top:14pt; }}
h3 {{ color:{crimson}; font-size:11.5pt; margin-bottom:2pt; margin-top:10pt; }}
td, th {{ padding:3pt 6pt; vertical-align:top; }}
th {{ text-align:left; background:#f3ead0; }}
.meta td:first-child {{ font-weight:bold; color:#555; }}
.lyr {{ white-space:pre-wrap; line-height:140%; }}
.small {{ color:#777; font-size:9pt; }}
</style></head><body>""", f"<h1>{e(song.title)}</h1>", '<table class="meta">']
    for k, v in _meta_rows(song):
        parts.append(f"<tr><td>{e(k)}</td><td>{e(v)}</td></tr>")
    parts.append("</table>")
    if song.arrangement:
        parts.append('<h2>Arrangement</h2><table width="100%" cellspacing="0" border="0">'
                     "<tr><th>#</th><th>Section</th><th>Bars</th><th>Start</th><th>Notes</th></tr>")
        for i, (b, bar, t) in enumerate(_arrangement_rows(song), 1):
            parts.append(f'<tr><td>{i}</td><td><span style="color:{b.color}">■</span> {e(b.label or b.type)}</td>'
                         f"<td>{b.bars}</td><td>bar {bar} · {t}</td><td>{e(b.notes)}</td></tr>")
        parts.append(f"</table><p><b>Total:</b> {song.total_bars} bars · {music.format_duration(song.total_seconds)}</p>")
    if song.lyrics:
        parts.append("<h2>Lyrics</h2>")
        for sec in song.lyrics:
            st = stats(sec.text)
            parts.append(f'<h3>{e(sec.label or sec.type)} <span class="small">{st["bars"]} bars · {st["words"]} words</span></h3>')
            parts.append('<div class="lyr">' + "<br>".join(e(l) for l in sec.text.splitlines()) + "</div>")
    if song.references:
        parts.append("<h2>References</h2><ul>" + "".join(
            f"<li>{e(r.title)} <span class='small'>{e(r.url)}</span></li>" for r in song.references) + "</ul>")
    if song.beat_files:
        parts.append("<h2>Beat files</h2><ul>" + "".join(f"<li>{e(p)}</li>" for p in song.beat_files) + "</ul>")
    if song.notes.strip():
        parts.append("<h2>Notes</h2><div class='lyr'>" + "<br>".join(e(l) for l in song.notes.splitlines()) + "</div>")
    parts.append("<p class='small'><br>Exported from Chaz SongBook</p></body></html>")
    return "".join(parts)


def export_pdf(song: Song, dest: str | Path) -> None:
    """Render the song sheet to PDF with Qt (needs a QGuiApplication)."""
    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

    writer = QPdfWriter(str(dest))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.Letter))
    writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
    writer.setResolution(300)
    writer.setTitle(song.title)
    writer.setCreator("Chaz SongBook")
    doc = QTextDocument()
    doc.setHtml(to_html(song))
    doc.setPageSize(QSizeF(writer.width(), writer.height()))
    # QTextDocument.print_ handles pagination into the writer
    doc.print_(writer)


def export_song(song: Song, dest: str | Path) -> Path:
    dest = Path(dest)
    ext = dest.suffix.lower()
    if ext == ".pdf":
        export_pdf(song, dest)
    elif ext in (".md", ".markdown"):
        dest.write_text(to_markdown(song), encoding="utf-8")
    elif ext in (".html", ".htm"):
        dest.write_text(to_html(song), encoding="utf-8")
    else:
        dest.write_text(to_text(song), encoding="utf-8")
    return dest


def safe_filename(name: str) -> str:
    bad = '<>:"/\\|?*'
    cleaned = "".join("_" if c in bad or ord(c) < 32 else c for c in name).strip(" .")
    return cleaned or "song"
