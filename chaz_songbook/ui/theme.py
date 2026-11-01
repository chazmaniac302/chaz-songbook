"""Black / gold / crimson theme shared by all Chaz tools."""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette

from ..paths import resource_path

BG = "#0B0B0D"
PANEL = "#131316"
PANEL2 = "#1A1A1F"
PANEL3 = "#23232A"
BORDER = "#2C2C34"
TEXT = "#EEE7D7"
MUTED = "#8F897C"
GOLD = "#D4AF37"
GOLD_DIM = "#9C7F25"
CRIMSON = "#B3122E"
CRIMSON_HI = "#E0294A"

STATUS_COLORS = {
    "Idea": "#8F897C",
    "Writing": "#D4AF37",
    "Recording": "#E0294A",
    "Mixing": "#5BA3D9",
    "Done": "#3FBF7F",
}

UI_FONT = "Inter"
HEAD_FONT = "Oswald"


def load_fonts() -> None:
    global UI_FONT, HEAD_FONT
    for name in ("Inter.ttf", "Oswald.ttf"):
        fid = QFontDatabase.addApplicationFont(resource_path(f"assets/fonts/{name}"))
        fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
        if fams and name.startswith("Inter"):
            UI_FONT = fams[0]
        elif fams and name.startswith("Oswald"):
            HEAD_FONT = fams[0]


def head_font(size: int, weight=QFont.Weight.DemiBold) -> QFont:
    f = QFont(HEAD_FONT)
    f.setPixelSize(size)
    f.setWeight(weight)
    f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 104)
    return f


def apply(app) -> None:
    load_fonts()
    f = QFont(UI_FONT)
    f.setPixelSize(13)
    app.setFont(f)
    app.setStyle("Fusion")
    pal = QPalette()
    for role, col in [
        (QPalette.ColorRole.Window, BG), (QPalette.ColorRole.WindowText, TEXT),
        (QPalette.ColorRole.Base, PANEL2), (QPalette.ColorRole.AlternateBase, PANEL),
        (QPalette.ColorRole.Text, TEXT), (QPalette.ColorRole.Button, PANEL2),
        (QPalette.ColorRole.ButtonText, TEXT), (QPalette.ColorRole.Highlight, CRIMSON),
        (QPalette.ColorRole.HighlightedText, "#FFFFFF"), (QPalette.ColorRole.ToolTipBase, PANEL3),
        (QPalette.ColorRole.ToolTipText, TEXT), (QPalette.ColorRole.PlaceholderText, "#5E5A52"),
        (QPalette.ColorRole.Link, GOLD), (QPalette.ColorRole.BrightText, GOLD),
    ]:
        pal.setColor(role, QColor(col))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#55524B"))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#55524B"))
    app.setPalette(pal)
    app.setStyleSheet(STYLESHEET)


STYLESHEET = f"""
QWidget {{ color: {TEXT}; }}
QMainWindow, QDialog {{ background: {BG}; }}
QToolTip {{ background: {PANEL3}; color: {TEXT}; border: 1px solid {GOLD_DIM}; padding: 4px 6px; }}
QFrame#Sidebar {{ background: {PANEL}; border-right: 1px solid {BORDER}; }}
QFrame#Header {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #17090C, stop:0.55 {PANEL}, stop:1 #15120A);
                 border-bottom: 1px solid {BORDER}; }}
QFrame#Card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}
QLabel#Brand {{ color: {GOLD}; }}
QLabel#Muted, QLabel[muted="true"] {{ color: {MUTED}; }}
QLabel#SectionTitle {{ color: {GOLD}; font-weight: 600; letter-spacing: 1px; }}
QLabel#Stat {{ color: {TEXT}; font-weight: 600; }}
QLabel#Pill {{ border-radius: 9px; padding: 2px 9px; font-weight: 600; }}

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {PANEL2}; border: 1px solid {BORDER}; border-radius: 7px; padding: 6px 8px;
    selection-background-color: {CRIMSON}; selection-color: white; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {GOLD_DIM}; }}
QLineEdit#TitleEdit {{ background: transparent; border: 1px solid transparent; font-size: 26px; padding: 2px 4px; }}
QLineEdit#TitleEdit:hover {{ border: 1px solid {BORDER}; }}
QLineEdit#TitleEdit:focus {{ border: 1px solid {GOLD_DIM}; background: {PANEL2}; }}
QPlainTextEdit#LyricEditor {{ font-size: 17px; padding: 14px 16px; background: #111114; border-radius: 10px;
                              line-height: 150%; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: none; border-left: 5px solid transparent; border-right: 5px solid transparent;
                         border-top: 6px solid {GOLD}; margin-right: 8px; }}
QComboBox QAbstractItemView {{ background: {PANEL2}; border: 1px solid {BORDER}; selection-background-color: {CRIMSON}; outline: 0; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0; border: none; }}

QPushButton, QToolButton {{ background: {PANEL3}; border: 1px solid {BORDER}; border-radius: 7px; padding: 6px 12px; }}
QPushButton:hover, QToolButton:hover {{ border-color: {GOLD_DIM}; background: #2A2A32; }}
QPushButton:pressed, QToolButton:pressed {{ background: #18181C; }}
QPushButton:disabled {{ color: #55524B; }}
QPushButton#Primary {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #E6C24A, stop:1 {GOLD_DIM});
                       color: #120E02; border: 1px solid #E8C65A; font-weight: 700; }}
QPushButton#Primary:hover {{ background: #E6C24A; }}
QPushButton#Danger {{ background: #2A0E14; border-color: #5A1422; color: #FF8EA0; }}
QPushButton#Danger:hover {{ background: {CRIMSON}; color: white; }}
QPushButton#Tap {{ background: #2A0E14; border: 1px solid {CRIMSON}; color: #FFD9DF; font-weight: 700; min-width: 54px; }}
QPushButton#Tap:pressed {{ background: {CRIMSON}; }}
QPushButton:checked, QToolButton:checked {{ background: #3A2E0A; border-color: {GOLD}; color: {GOLD}; }}
QToolButton#Star {{ background: transparent; border: none; font-size: 22px; color: #5E5A52; padding: 0 4px; }}
QToolButton#Star:checked {{ color: {GOLD}; background: transparent; }}
QToolButton#Chip {{ border-radius: 11px; padding: 3px 10px; background: #221A06; border-color: #4D3D10; color: {GOLD}; }}

QTabWidget::pane {{ border: none; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 10px 18px; border: none;
                border-bottom: 2px solid transparent; font-weight: 600; font-size: 13px; }}
QTabBar::tab:selected {{ color: {GOLD}; border-bottom: 2px solid {GOLD}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}

QListWidget, QListView, QTreeView, QTableWidget {{ background: transparent; border: none; outline: 0; }}
QListWidget::item {{ border-radius: 7px; padding: 6px; margin: 1px 0; }}
QListWidget::item:selected {{ background: #2A0E14; border: 1px solid {CRIMSON}; color: white; }}
QListWidget::item:hover:!selected {{ background: {PANEL2}; }}
QHeaderView::section {{ background: {PANEL}; color: {MUTED}; border: none; padding: 6px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #34343C; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {GOLD_DIM}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #34343C; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QSplitter::handle {{ background: {BORDER}; }}
QStatusBar {{ background: {PANEL}; color: {MUTED}; border-top: 1px solid {BORDER}; }}
QStatusBar QLabel {{ color: {MUTED}; padding: 0 6px; }}
QMenu {{ background: {PANEL2}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 6px 22px; border-radius: 5px; }}
QMenu::item:selected {{ background: {CRIMSON}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {BORDER}; background: {PANEL2}; }}
QCheckBox::indicator:checked {{ background: {GOLD}; border-color: {GOLD}; }}
QMessageBox {{ background: {PANEL}; }}
"""
