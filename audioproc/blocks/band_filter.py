from __future__ import annotations

from scipy import signal

from ..block import Block, Param, SosFilter


class BandFilter(Block):
    name = "Band Filter"
    category = "Filters"
    description = "Butterworth low-pass, high-pass or band-pass with adjustable edges."
    params = [
        Param("mode", "Type", kind="choice", default="Band-pass",
              choices=("Band-pass", "Low-pass", "High-pass")),
        Param("low", "Low cut", 30, 5000, default=300, unit="Hz", scale="log", decimals=0),
        Param("high", "High cut", 200, 12000, default=2700, unit="Hz", scale="log", decimals=0),
        Param("order", "Steepness", 1, 8, default=4, kind="int"),
    ]

    def __init__(self):
        super().__init__()
        self.filt = SosFilter()

    def configure(self, fs):
        nyq = fs / 2
        lo = min(self.low, nyq * 0.90)
        hi = min(self.high, nyq * 0.95)
        if self.mode == "Low-pass":
            sos = signal.butter(self.order, hi, "low", fs=fs, output="sos")
        elif self.mode == "High-pass":
            sos = signal.butter(self.order, lo, "high", fs=fs, output="sos")
        else:
            hi = max(hi, lo * 1.05)  # the edges can't cross
            sos = signal.butter(self.order, [lo, hi], "band", fs=fs, output="sos")
        self.filt.set_sos(sos)

    def reset(self):
        self.filt.reset()

    def process(self, x):
        return self.filt(x)
