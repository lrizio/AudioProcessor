"""Template for your own block.

Copy this file to a name WITHOUT the leading underscore (e.g. `tremolo.py`),
edit it and restart the app -- it appears under "+ Add block" in the
category you give it. Files starting with an underscore are ignored.

This example is a tremolo (the volume wobbles at a set rate), chosen because
it shows the one thing every block must get right: `self.phase` carries on
from one chunk to the next instead of restarting at zero each time.
"""
import numpy as np

from audioproc.block import Block, Param


class Tremolo(Block):
    name = "Tremolo"
    category = "Effects"
    description = "Wobbles the volume."
    params = [
        Param("rate", "Rate", 0.5, 20, default=5, unit="Hz"),
        Param("depth", "Depth", 0, 100, default=50, unit="%", decimals=0),
    ]

    def reset(self):
        # running state lives on self
        self.phase = 0.0

    def configure(self, fs):
        # runs on start and whenever a slider moves; fs is the sample rate
        self.step = 2 * np.pi * self.rate / fs

    def process(self, x):
        # x is one chunk of mono samples (-1..1); return the same length
        ph = self.phase + self.step * np.arange(len(x))
        self.phase = (self.phase + self.step * len(x)) % (2 * np.pi)
        d = self.depth / 100.0
        return x * (1.0 - d * 0.5 * (1.0 + np.sin(ph)))
