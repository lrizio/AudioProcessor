from __future__ import annotations

import numpy as np

from ..block import Block, Param
from ._dynamics import GainRider


class NoiseGate(Block):
    name = "Noise Gate"
    category = "Dynamics"
    description = "Turns the audio down whenever it drops below the threshold (a squelch)."
    params = [
        Param("threshold", "Threshold", -80, 0, default=-40, unit="dB"),
        Param("depth", "Reduction", 6, 80, default=40, unit="dB", decimals=0),
        Param("attack", "Open time", 0.5, 50, default=2, unit="ms", scale="log"),
        Param("hold", "Hold", 0, 1000, default=150, unit="ms", decimals=0),
        Param("release", "Close time", 10, 2000, default=200, unit="ms", scale="log", decimals=0),
    ]

    def __init__(self):
        super().__init__()
        self.rider = GainRider()

    def reset(self):
        self.rider.reset()

    def process(self, x):
        curve = lambda level: np.where(level >= self.threshold, 0.0, -self.depth)
        return self.rider.run(x, self.fs, curve, self.release, self.attack, self.hold)
