from __future__ import annotations

import numpy as np

from ..block import Block, Param
from ._dynamics import GainRider


class Agc(Block):
    name = "AGC"
    category = "Dynamics"
    description = "Automatic gain control: holds the output near a target level."
    params = [
        Param("target", "Target level", -40, 0, default=-12, unit="dB"),
        Param("max_gain", "Max gain", 0, 60, default=30, unit="dB", decimals=0),
        Param("attack", "Attack", 0.5, 100, default=5, unit="ms", scale="log"),
        Param("release", "Decay", 20, 5000, default=500, unit="ms", scale="log", decimals=0),
    ]

    def __init__(self):
        super().__init__()
        self.rider = GainRider()

    def reset(self):
        self.rider.reset()

    def process(self, x):
        curve = lambda level: np.clip(self.target - level, -80.0, self.max_gain)
        return self.rider.run(x, self.fs, curve, self.attack, self.release)
