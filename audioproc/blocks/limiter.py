from __future__ import annotations

import numpy as np

from ..block import Block, Param
from ._dynamics import GainRider


class Limiter(Block):
    name = "Limiter"
    category = "Dynamics"
    description = "Stops peaks going above the ceiling. Put it last."
    params = [
        Param("ceiling", "Ceiling", -30, 0, default=-3, unit="dB"),
        Param("release", "Release", 10, 1000, default=80, unit="ms", scale="log", decimals=0),
    ]

    def __init__(self):
        super().__init__()
        self.rider = GainRider()

    def reset(self):
        self.rider.reset()

    def process(self, x):
        curve = lambda level: np.minimum(self.ceiling - level, 0.0)
        y = self.rider.run(x, self.fs, curve, 0.3, self.release)
        # The gain reacts within ~1 ms, not instantly; clip the leading edge
        # of a sudden peak so the ceiling is a hard guarantee.
        top = 10.0 ** (self.ceiling / 20.0)
        return np.clip(y, -top, top)
