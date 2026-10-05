from __future__ import annotations

from scipy import signal

from ..block import Block, Param, SosFilter


class Notch(Block):
    name = "Notch"
    category = "Filters"
    description = "Manual notch: removes one fixed tone (a carrier, heterodyne or hum)."
    params = [
        Param("freq", "Frequency", 40, 6000, default=1000, unit="Hz", scale="log", decimals=0),
        Param("q", "Sharpness (Q)", 1, 100, default=30, scale="log", decimals=0),
    ]

    def __init__(self):
        super().__init__()
        self.filt = SosFilter()

    def configure(self, fs):
        b, a = signal.iirnotch(min(self.freq, fs * 0.45), self.q, fs=fs)
        self.filt.set_sos(signal.tf2sos(b, a))

    def reset(self):
        self.filt.reset()

    def process(self, x):
        return self.filt(x)
