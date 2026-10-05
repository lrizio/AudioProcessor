"""One panel per block in the chain. The controls are generated from the
block's `params` list, so a new block needs no UI code."""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QPushButton, QSlider, QVBoxLayout,
)

from ..block import Block, Param
from ..chain import Chain

STEPS = 1000  # slider resolution for float parameters


class BlockPanel(QGroupBox):
    move_requested = Signal(object, int)  # block, -1 / +1
    remove_requested = Signal(object)

    def __init__(self, block: Block, chain: Chain):
        super().__init__()
        self.block = block
        self.chain = chain
        self.setFixedWidth(290)
        self.setToolTip(block.description)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 10, 8, 8)
        outer.setSpacing(6)

        head = QHBoxLayout()
        self.enable = QCheckBox(block.name)
        self.enable.setChecked(block.enabled)
        self.enable.setStyleSheet("font-weight: bold; color: #9fd4f0;")
        self.enable.toggled.connect(self._on_enabled)
        head.addWidget(self.enable, 1)
        for text, tip, slot in (
            ("◀", "Move earlier in the chain", lambda: self.move_requested.emit(block, -1)),
            ("▶", "Move later in the chain", lambda: self.move_requested.emit(block, +1)),
            ("✕", "Remove", lambda: self.remove_requested.emit(block)),
        ):
            btn = QPushButton(text)
            btn.setFixedSize(26, 24)
            btn.setStyleSheet("padding: 0;")
            btn.setToolTip(tip)
            btn.clicked.connect(slot)
            head.addWidget(btn)
        outer.addLayout(head)

        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)
        for row, p in enumerate(block.params):
            self._add_row(grid, row, p)
        grid.setColumnStretch(1, 1)
        outer.addLayout(grid)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #e06a5a; font-weight: normal;")
        self.status.hide()
        outer.addWidget(self.status)
        outer.addStretch(1)

    # -- one control row per parameter --------------------------------
    def _add_row(self, grid: QGridLayout, row: int, p: Param) -> None:
        label = QLabel(p.label)
        label.setStyleSheet("font-weight: normal; color: #bbb;")
        grid.addWidget(label, row, 0)
        value = getattr(self.block, p.key)

        if p.kind == "bool":
            box = QCheckBox()
            box.setChecked(bool(value))
            box.toggled.connect(lambda on, k=p.key: self.chain.set_param(self.block, k, on))
            grid.addWidget(box, row, 1, 1, 2)
            return
        if p.kind == "choice":
            combo = QComboBox()
            combo.addItems(list(p.choices))
            combo.setCurrentText(str(value))
            combo.currentTextChanged.connect(lambda t, k=p.key: self.chain.set_param(self.block, k, t))
            grid.addWidget(combo, row, 1, 1, 2)
            return

        is_int = p.kind == "int"
        log = p.scale == "log" and p.lo > 0 and not is_int
        slider = QSlider(Qt.Horizontal)
        spin = QDoubleSpinBox()
        spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
        spin.setKeyboardTracking(False)
        spin.setDecimals(0 if is_int else p.decimals)
        spin.setRange(p.lo, p.hi)
        spin.setSuffix(f" {p.unit}" if p.unit else "")
        spin.setFixedWidth(82)
        spin.setAlignment(Qt.AlignRight)
        if is_int:
            slider.setRange(int(p.lo), int(p.hi))
        else:
            slider.setRange(0, STEPS)

        def to_slider(v: float) -> int:
            if is_int:
                return int(round(v))
            if log:
                return int(round(STEPS * math.log(v / p.lo) / math.log(p.hi / p.lo)))
            return int(round(STEPS * (v - p.lo) / (p.hi - p.lo)))

        def from_slider(s: int) -> float:
            if is_int:
                return s
            if log:
                return p.lo * (p.hi / p.lo) ** (s / STEPS)
            return p.lo + (p.hi - p.lo) * s / STEPS

        def apply(v: float) -> None:
            self.chain.set_param(self.block, p.key, p.coerce(v))

        def slider_moved(s: int) -> None:
            v = from_slider(s)
            spin.blockSignals(True)
            spin.setValue(v)
            spin.blockSignals(False)
            apply(v)

        def spin_changed(v: float) -> None:
            slider.blockSignals(True)
            slider.setValue(to_slider(v))
            slider.blockSignals(False)
            apply(v)

        spin.setValue(float(value))
        slider.setValue(to_slider(float(value)))
        slider.valueChanged.connect(slider_moved)
        spin.valueChanged.connect(spin_changed)
        grid.addWidget(slider, row, 1)
        grid.addWidget(spin, row, 2)

    def _on_enabled(self, on: bool) -> None:
        self.chain.set_enabled(self.block, on)
        self.refresh_status()

    def refresh_status(self) -> None:
        """Reflect a block the chain bypassed because it raised."""
        b = self.block
        if self.enable.isChecked() != b.enabled:
            self.enable.blockSignals(True)
            self.enable.setChecked(b.enabled)
            self.enable.blockSignals(False)
        if b.error:
            self.status.setText(f"Bypassed after an error: {b.error}")
        self.status.setVisible(bool(b.error))
