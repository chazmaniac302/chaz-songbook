"""Draws the app icon (black disc, gold notebook/C, crimson ring) -> assets/icon.png + icon.ico"""
import sys
from pathlib import Path
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter, QPen, QPainterPath

app = QGuiApplication(sys.argv)
S = 512
img = QImage(S, S, QImage.Format.Format_ARGB32)
img.fill(Qt.GlobalColor.transparent)
p = QPainter(img)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
r = QRectF(16, 16, S - 32, S - 32)
path = QPainterPath(); path.addRoundedRect(r, 110, 110)
g = QLinearGradient(0, 0, 0, S); g.setColorAt(0, QColor("#1A1A1F")); g.setColorAt(1, QColor("#050506"))
p.fillPath(path, g)
p.setPen(QPen(QColor("#B3122E"), 14)); p.drawPath(path)
# notebook page
page = QRectF(132, 104, 248, 304)
pg = QLinearGradient(0, 104, 0, 408); pg.setColorAt(0, QColor("#F2D36B")); pg.setColorAt(1, QColor("#B8901F"))
pp = QPainterPath(); pp.addRoundedRect(page, 26, 26)
p.fillPath(pp, pg)
# spiral rings
p.setPen(QPen(QColor("#E0294A"), 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
for y in range(140, 400, 52):
    p.drawLine(112, y, 160, y)
# lines on page
p.setPen(QPen(QColor(10, 10, 12, 150), 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
for i, y in enumerate(range(230, 380, 40)):
    p.drawLine(190, y, 340 - (i % 2) * 50, y)
# big note glyph
f = QFont("Oswald"); f.setPixelSize(120); f.setBold(True)
p.setFont(f); p.setPen(QColor("#0B0B0D"))
p.drawText(QRectF(176, 100, 180, 130), Qt.AlignmentFlag.AlignCenter, "♪")
p.end()
out = Path(__file__).resolve().parents[1] / "chaz_songbook" / "assets"
img.save(str(out / "icon.png"))
from PIL import Image
im = Image.open(out / "icon.png")
im.save(out / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icon written")
