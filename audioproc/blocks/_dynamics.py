"""Shared gain-riding core for the dynamics blocks (AGC, compressor,
limiter, gate).

The signal level is measured as the peak of each ~1 ms sub-block; a block's
own `curve` turns that level into the gain it would like (both in dB); that
wanted gain is then smoothed with separate time constants for falling and
rising gain, and applied as a ramp so the gain never steps. Working at the
1 ms rate keeps the only Python loop to a couple of dozen passes per chunk.
"""
from __future__ import annotations

import math

import numpy as np


class GainRider:
    def __init__(self, start_db: float = 0.0):
        self.start_db = start_db
        self.reset()

    def reset(self) -> None:
        self.g = self.start_db  # current gain, dB
        self.hold = 0.0  # ms left before the gain may fall

    def run(self, x, fs, curve, fall_ms, rise_ms, hold_ms=0.0):
        """Returns x with the gain applied. `curve(level_db) -> wanted gain
        in dB` works on arrays."""
        n = len(x)
        if n == 0:
            return x
        sb = max(1, int(fs / 1000))
        idx = np.arange(0, n, sb)
        peaks = np.maximum.reduceat(np.abs(x), idx)
        want = curve(20.0 * np.log10(np.maximum(peaks, 1e-9)))

        dt = sb / fs * 1000.0
        cf = math.exp(-dt / max(fall_ms, 0.05))
        cr = math.exp(-dt / max(rise_ms, 0.05))
        g, hold = self.g, self.hold
        gains = np.empty(len(idx))
        for i, w in enumerate(want.tolist()):
            if w < g:
                if hold > 0.0:
                    hold -= dt
                else:
                    g = cf * g + (1.0 - cf) * w
            else:
                g = cr * g + (1.0 - cr) * w
                hold = hold_ms
            gains[i] = g

        # ramp from the previous gain to each sub-block's gain by its end
        ends = np.minimum(idx + sb, n) - 1
        ramp = np.interp(np.arange(n), np.concatenate([[-1], ends]),
                         np.concatenate([[self.g], gains]))
        self.g, self.hold = g, hold
        return x * 10.0 ** (ramp / 20.0)
