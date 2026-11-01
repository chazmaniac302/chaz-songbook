"""Stage the Windows build, write SHA256SUMS.txt, zip it and write the .sha256 sidecar.

usage: python tools/package_win.py <pyinstaller dist dir> <out dir>
"""
import hashlib
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chaz_songbook import __version__  # noqa: E402


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(dist: Path, out: Path) -> Path:
    stage = out / "stage"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    shutil.copytree(dist / "Chaz SongBook", stage / "Chaz SongBook")
    shutil.copy2(dist / "ChazSongBook-Portable.exe", stage / "ChazSongBook-Portable.exe")
    for name in ("Install-ChazSongBook.ps1", "README.md", "LICENSE"):
        shutil.copy2(ROOT / name, stage / name)
    files = sorted(p for p in stage.rglob("*") if p.is_file()
                   and (p.name == "ChazSongBook-Portable.exe" or "Chaz SongBook" in p.relative_to(stage).parts[:1]))
    lines = [f"{sha256(p)} *{p.relative_to(stage).as_posix()}" for p in files]
    (stage / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    zpath = out / f"ChazSongBook-v{__version__}-win64.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(stage.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(stage).as_posix())
    digest = sha256(zpath)
    Path(str(zpath) + ".sha256").write_text(f"{digest}  {zpath.name}\n", encoding="utf-8")
    print(f"{zpath.name}  {zpath.stat().st_size / 1e6:.1f} MB  sha256 {digest}")
    return zpath


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
