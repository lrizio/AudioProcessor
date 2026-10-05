from __future__ import annotations

from ..block import Block, Param
from ._lms import DelayedLms


class AutoNotch(Block):
    name = "Auto Notch"
    category = "Adaptive"
    description = "Finds and removes steady tones (carriers, heterodynes) by itself. Not for CW - it will notch the signal."
    params = [
        Param("length", "Filter length", 1, 10, default=4, unit="ms"),
        Param("delay", "Delay", 0.5, 20, default=4, unit="ms"),
        Param("speed", "Adapt speed", 0.001, 0.2, default=0.02, scale="log", decimals=3),
    ]

    def __init__(self):
        super().__init__()
        self.lms = DelayedLms()

    def configure(self, fs):
        self.lms.setup(self.length * 1e-3 * fs, self.delay * 1e-3 * fs)

    def reset(self):
        self.lms.reset()

    def process(self, x):
        _, e = self.lms.run(x, self.speed, leak=1e-4)
        return e
