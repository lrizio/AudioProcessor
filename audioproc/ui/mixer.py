"""One strip per available input source: ON switch, fader and level meter.
Everything that is ON is added together to make the input of the chain."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout

from .widgets import Meter

UNITY = 100  # fader position for 0 dB
FADER_MAX = 130  # +12 dB
DB_PER_STEP = 0.4

ON_STYLE = ("background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #4fbf6a, stop:1 #257a3a);"
            " color: white; font-weight: bold; padding: 2px 0;")
OFF_STYLE = "padding: 2px 0;"


def fader_gain(value: int) -> float:
    """Fader position -> linear gain. 0 is fully off, UNITY is 0 dB."""
    return 0.0 if value <= 0 else 10.0 ** ((value - UNITY) * DB_PER_STEP / 20.0)


class MixerStrip(QFrame):
    toggled = Signal(object, bool)  # strip, on
    level_changed = Signal(object)  # strip

    def __init__(self, key, name: str, label: str):
        super().__init__()
        self.key = key  # engine source key
        self.name = name  # the device's own name
        self.label = label  # what is shown, and what settings are saved under
        self.blocked = ""  # reason this source can't be used right now
        self.setObjectName("mixerStrip")
        self.setStyleSheet("#mixerStrip { background: #1a1d21; border: 1px solid #0a0b0c;"
                           " border-top: 1px solid #33373c; border-radius: 6px; }")
        self.setFixedWidth(176)  # seven strips across the default window

        v = QVBoxLayout(self)
        v.setContentsMargins(8, 5, 8, 6)
        v.setSpacing(3)

        # Two lines for the name: the part that tells two radios apart
        # ("11-" / "12- USB Audio CODEC") sits in the middle of it.
        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.title.setFixedHeight(2 * self.title.fontMetrics().lineSpacing() + 2)
        v.addWidget(self.title)

        mid = QHBoxLayout()
        mid.setSpacing(5)
        self.on_btn = QPushButton("ON")
        self.on_btn.setCheckable(True)
        self.on_btn.setFixedWidth(34)
        self.on_btn.setStyleSheet(OFF_STYLE)
        self.on_btn.toggled.connect(self._on_toggled)
        mid.addWidget(self.on_btn)
        self.fader = QSlider(Qt.Horizontal)
        self.fader.setRange(0, FADER_MAX)
        self.fader.setValue(UNITY)
        self.fader.valueChanged.connect(self._on_fader)
        mid.addWidget(self.fader, 1)
        self.db = QLabel()
        self.db.setFixedWidth(42)
        self.db.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.db.setStyleSheet("color: #bbb;")
        mid.addWidget(self.db)
        v.addLayout(mid)

        self.meter = Meter(width=None, height=8)
        v.addWidget(self.meter)
        self._on_fader(self.fader.value())
        self._refresh_title()

    # -- state --------------------------------------------------------
    @property
    def on(self) -> bool:
        return self.on_btn.isChecked()

    @property
    def gain(self) -> float:
        return fader_gain(self.fader.value())

    def set_state(self, on: bool, level: int) -> None:
        """Restore saved state without telling the engine (the caller does)."""
        for w in (self.on_btn, self.fader):
            w.blockSignals(True)
        self.on_btn.setChecked(on and not self.blocked)
        self.fader.setValue(level)
        for w in (self.on_btn, self.fader):
            w.blockSignals(False)
        self.on_btn.setStyleSheet(ON_STYLE if self.on else OFF_STYLE)
        self._on_fader(self.fader.value(), tell=False)

    def set_blocked(self, reason: str) -> None:
        """A source that can't be used (it is the output device) is greyed
        out and switched off."""
        self.blocked = reason
        self.on_btn.setEnabled(not reason)
        self.fader.setEnabled(not reason)
        self._refresh_title()

    def set_error(self, text: str) -> None:
        self._refresh_title(text)

    def _refresh_title(self, error: str = "") -> None:
        # room for two wrapped lines; anything longer is cut with "…" (the
        # tooltip has the whole name)
        self.title.setText(self.title.fontMetrics().elidedText(self.label, Qt.ElideRight, 2 * 150))
        if error:
            self.title.setStyleSheet("color: #e06a5a;")
            self.setToolTip(f"{self.label}\n\nCould not be opened: {error}")
        elif self.blocked:
            self.title.setStyleSheet("color: #666;")
            self.setToolTip(f"{self.label}\n\n{self.blocked}")
        else:
            self.title.setStyleSheet("color: #9fd4f0;")
            self.setToolTip(self.label)

    # -- user actions -------------------------------------------------
    def _on_toggled(self, on: bool) -> None:
        self.on_btn.setStyleSheet(ON_STYLE if on else OFF_STYLE)
        self.toggled.emit(self, on)

    def _on_fader(self, value: int, tell: bool = True) -> None:
        self.db.setText("off" if value <= 0 else f"{(value - UNITY) * DB_PER_STEP:+.0f} dB")
        if tell:
            self.level_changed.emit(self)
