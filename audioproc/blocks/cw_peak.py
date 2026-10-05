from __future__ import annotations

from scipy import signal

from ..block import Block, Param, SosFilter


class CwPeak(Block):
    name = "CW Peak Filter"
    category = "Filters"
    description = "Narrow band-pass centred on the CW pitch."
    params = [
        Param("center", "Pitch", 300, 1500, default=700, unit="Hz", decimals=0),
        Param("width", "Width", 30, 1000, default=150, unit="Hz", scale="log", decimals=0),
    ]

    def __init__(self):
        super().__init__()
        self.filt = SosFilter()

    def configure(self, fs):
        lo = max(self.center - self.width / 2, 20.0)
        hi = min(self.center + self.width / 2, fs * 0.45)
        self.filt.set_sos(signal.butter(2, [lo, hi], "band", fs=fs, output="sos"))

    def reset(self):
        self.filt.reset()

    def process(self, x):
        return self.filt(x)
