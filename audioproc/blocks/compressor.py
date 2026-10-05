from __future__ import annotations

import numpy as np

from ..block import Block, Param
from ._dynamics import GainRider


class Compressor(Block):
    name = "Compressor"
    category = "Dynamics"
    description = "Turns down whatever exceeds the threshold, by the ratio."
    params = [
        Param("threshold", "Threshold", -60, 0, default=-20, unit="dB"),
        Param("ratio", "Ratio", 1, 20, default=4, scale="log"),
        Param("attack", "Attack", 0.5, 100, default=5, unit="ms", scale="log"),
        Param("release", "Release", 10, 2000, default=150, unit="ms", scale="log", decimals=0),
        Param("makeup", "Make-up gain", 0, 30, default=0, unit="dB"),
    ]

    def __init__(self):
        super().__init__()
        self.rider = GainRider()

    def reset(self):
        self.rider.reset()

    def process(self, x):
        slope = 1.0 - 1.0 / self.ratio
        curve = lambda level: -np.maximum(level - self.threshold, 0.0) * slope
        y = self.rider.run(x, self.fs, curve, self.attack, self.release)
        return y * 10.0 ** (self.makeup / 20.0)
