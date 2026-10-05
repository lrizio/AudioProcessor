"""Input-vs-output spectrum: the same stretch of audio before and after
the chain, so the effect of a block is visible as well as audible."""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg

NFFT = 4096


class SpectrumWidget(pg.PlotWidget):
    def __init__(self):
        super().__init__(background="#0b0e11")
        self._win = np.hanning(NFFT)
        self._scale = 20 * np.log10(np.sum(self._win) / 2)  # full-scale sine -> 0 dB
        self._avg_in = None
        self._avg_out = None
        self._fs = 0

        self.setLabel("bottom", "Frequency", units="Hz")
        self.setLabel("left", "Level", units="dB")
        # No showGrid(): pyqtgraph's grid costs ~25 ms per repaint with the
        # interpreter held, which starves the audio thread into dropouts
        # (measured). A handful of fixed lines is nearly free.
        self._grid: list[pg.InfiniteLine] = []
        grid_pen = pg.mkPen("#262c33", width=1)
        for level in range(-100, 0, 20):
            self.addItem(pg.InfiniteLine(level, angle=0, pen=grid_pen))
        self._grid_pen = grid_pen
        self.setYRange(-120, 0, padding=0)
        self.setMouseEnabled(x=True, y=False)
        self.addLegend(offset=(-10, 10))
        self._in = self.plot(pen=pg.mkPen("#7f8890", width=1), name="Input")
        self._out = self.plot(pen=pg.mkPen("#4fb0e0", width=1), name="Output")
        for curve in (self._in, self._out):
            curve.setClipToView(True)

    def set_fs(self, fs: int) -> None:
        if fs != self._fs:
            self._fs = fs
            self._avg_in = self._avg_out = None
            for line in self._grid:
                self.removeItem(line)
            self._grid = [pg.InfiniteLine(f, angle=90, pen=self._grid_pen)
                          for f in range(1000, fs // 2, 1000)]
            for line in self._grid:
                self.addItem(line)
            self.setLimits(xMin=0, xMax=fs / 2)
            self.setXRange(0, min(6000, fs / 2), padding=0)

    def _db(self, x: np.ndarray) -> np.ndarray:
        mag = np.abs(np.fft.rfft(x[-NFFT:] * self._win))
        return 20 * np.log10(mag + 1e-9) - self._scale

    def update_taps(self, tap_in: np.ndarray, tap_out: np.ndarray) -> None:
        a, b = self._db(tap_in), self._db(tap_out)
        if self._avg_in is None:
            self._avg_in, self._avg_out = a, b
        else:
            self._avg_in += 0.3 * (a - self._avg_in)
            self._avg_out += 0.3 * (b - self._avg_out)
        f = np.fft.rfftfreq(NFFT, 1 / self._fs)
        self._in.setData(f, self._avg_in)
        self._out.setData(f, self._avg_out)
