from __future__ import annotations

from ..block import Block, Param
from ._lms import DelayedLms


class LmsNr(Block):
    name = "LMS Noise Reduction"
    category = "Adaptive"
    description = "Keeps what is predictable (tones, CW, voiced speech) and drops random noise. Best on CW and steady signals."
    params = [
        Param("length", "Filter length", 1, 10, default=4, unit="ms"),
        Param("delay", "Delay", 0.2, 10, default=1, unit="ms"),
        Param("speed", "Adapt speed", 0.001, 0.2, default=0.02, scale="log", decimals=3),
        Param("leak", "Leak", 0, 50, default=5, decimals=0),
        Param("mix", "Amount", 0, 100, default=100, unit="%", decimals=0),
    ]

    def __init__(self):
        super().__init__()
        self.lms = DelayedLms()

    def configure(self, fs):
        self.lms.setup(self.length * 1e-3 * fs, self.delay * 1e-3 * fs)

    def reset(self):
        self.lms.reset()

    def process(self, x):
        # Leak pulls the weights back toward zero so the filter can't slowly
        # learn to pass the noise as well.
        y, _ = self.lms.run(x, self.speed, leak=self.leak * 1e-5)
        m = self.mix / 100.0
        return m * y + (1.0 - m) * x
