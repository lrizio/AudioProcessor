from __future__ import annotations

from ..block import Block, Param


class Gain(Block):
    name = "Gain"
    category = "Tone"
    description = "Plain level change."
    params = [
        Param("gain", "Gain", -40, 40, default=0, unit="dB"),
    ]

    def process(self, x):
        return x * 10.0 ** (self.gain / 20.0)
