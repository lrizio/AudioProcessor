"""App-wide QSS: a skeuomorphic "3D" pass over the default Fusion look --
raised gradient buttons with a top-highlight/bottom-shade, sunken-groove
sliders, and beveled group boxes. Applied once at the QApplication level
(see run.py) so every plain QPushButton/QComboBox/QSlider/QGroupBox/
QCheckBox picks it up automatically; widgets that set their own
`setStyleSheet()` directly (the lit START/LIVE/REC buttons) take
precedence over this for the properties they specify, same as CSS
specificity -- this is just the shared baseline underneath them, not a
replacement. Copied from HackRF SDR TRX, plus the few widgets this app
adds (spin boxes, horizontal scrollbar, menus, tooltips).
"""
from __future__ import annotations

from pathlib import Path

STYLESHEET = """
QWidget {
    background: #14181c;
    color: #ddd;
}

QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1c2126, stop:1 #101316);
}

QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #4a4f56, stop:0.5 #383c42, stop:1 #2a2d31);
    border: 1px solid #15171a;
    border-top: 1px solid #64696f;
    border-radius: 4px;
    padding: 5px 9px;
    color: #e2e2e2;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #565b62, stop:0.5 #40444a, stop:1 #303337);
}
QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #24262a, stop:1 #34373c);
    border-top: 1px solid #15171a;
    padding-top: 6px;
}
QPushButton:disabled {
    background: #262a2e;
    border: 1px solid #1a1c1f;
    color: #666;
}

QComboBox, QLineEdit {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1c1f22, stop:1 #26292d);
    border: 1px solid #0c0d0f;
    border-top: 1px solid #3a3d41;
    border-radius: 3px;
    padding: 3px 6px;
    color: #ddd;
}
QComboBox::drop-down {
    border-left: 1px solid #0c0d0f;
    width: 20px;
}
QComboBox::down-arrow {
    image: url("ARROW_PNG");
    width: 11px;
    height: 7px;
}
QComboBox:disabled {
    color: #666;
}
QComboBox QAbstractItemView {
    background: #22262a;
    border: 1px solid #0c0d0f;
    selection-background-color: #3a5f7d;
}

QGroupBox {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1a1d21, stop:1 #15171a);
    border: 1px solid #0a0b0c;
    border-top: 1px solid #33373c;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 6px;
    font-weight: bold;
    color: #9ab;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    top: 1px;
    padding: 0 4px;
}

QCheckBox {
    color: #ccc;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid #0a0b0c;
    border-top: 1px solid #3a3d41;
    border-radius: 3px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1c1f22, stop:1 #282b2f);
}
QCheckBox::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #4fb0e0, stop:1 #2a6f96);
    border-top: 1px solid #7ecbf0;
}

QSlider::groove:horizontal {
    height: 6px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #0c0d0f, stop:1 #2a2d31);
    border: 1px solid #060708;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 15px;
    height: 15px;
    margin: -5px 0;
    border-radius: 7px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #d8dadd, stop:0.5 #9a9ea3, stop:1 #6b6e72);
    border: 1px solid #333;
}
QSlider::handle:horizontal:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #eef0f2, stop:0.5 #b0b4b9, stop:1 #7d8085);
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2f7db8, stop:1 #1c4d70);
    border: 1px solid #0c2a3d;
    border-radius: 3px;
}

QProgressBar {
    background: #0c0d0f;
    border: 1px solid #060708;
    border-radius: 3px;
    text-align: center;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #4fa9e0, stop:1 #2a6f96);
    border-radius: 3px;
}

QScrollArea, QScrollArea > QWidget > QWidget {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background: #101316;
    width: 12px;
    border-radius: 6px;
}
QScrollBar::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4a4d51, stop:1 #34373b);
    border-radius: 6px;
    min-height: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QLabel {
    background: transparent;
}

QDoubleSpinBox {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1c1f22, stop:1 #26292d);
    border: 1px solid #0c0d0f;
    border-top: 1px solid #3a3d41;
    border-radius: 3px;
    padding: 1px 3px;
    color: #9fd4f0;
}
QScrollBar:horizontal {
    background: #101316;
    height: 12px;
    border-radius: 6px;
}
QScrollBar::handle:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #4a4d51, stop:1 #34373b);
    border-radius: 6px;
    min-width: 24px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QMenu {
    background: #22262a;
    border: 1px solid #0c0d0f;
}
QMenu::item {
    padding: 5px 22px;
}
QMenu::item:selected {
    background: #3a5f7d;
}
QToolTip {
    background: #22262a;
    color: #ddd;
    border: 1px solid #0c0d0f;
}
""".replace("ARROW_PNG", (Path(__file__).resolve().parent / "arrow.png").as_posix())
