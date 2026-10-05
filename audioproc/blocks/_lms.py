"""Shared core for the two LMS blocks: an adaptive line enhancer.

A FIR filter tries to predict the current sample from samples that are
`delay` old. Anything still predictable after that delay (steady tones, and
to a lesser extent voiced speech) ends up in the prediction `y`; whatever
isn't (noise) is left in the error `e = x - y`.

    Auto Notch keeps e  -> tones removed
    LMS NR     keeps y  -> noise reduced

The weights are updated once per small sub-block (normalised block LMS)
rather than once per sample, which keeps the maths in numpy; a per-sample
Python loop can't keep up with real time at 48 kHz.
"""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

SUB = 16  # samples per weight update


class DelayedLms:
    def __init__(self):
        self.taps = 0
        self.delay = 0
        self.w = np.zeros(0)
        self.hist = np.zeros(0)

    def setup(self, taps: int, delay: int) -> None:
        """Resize for a new filter length/delay; keeps what it has learned
        when neither changed."""
        taps, delay = max(4, int(taps)), max(1, int(delay))
        if (taps, delay) != (self.taps, self.delay):
            self.taps, self.delay = taps, delay
            self.reset()

    def reset(self) -> None:
        self.w = np.zeros(self.taps)
        self.hist = np.zeros(self.delay + self.taps - 1)

    def run(self, x: np.ndarray, mu: float, leak: float) -> tuple[np.ndarray, np.ndarray]:
        """Returns (prediction y, error e), each the length of x."""
        buf = np.concatenate([self.hist, x])
        # win[n] = the `taps` samples ending `delay` before x[n]
        win = sliding_window_view(buf, self.taps)
        y = np.empty(len(x))
        w = self.w
        keep = 1.0 - leak
        eps = 1e-9 * self.taps
        for i in range(0, len(x), SUB):
            X = win[i:i + SUB]
            yb = X @ w
            eb = x[i:i + SUB] - yb
            norm = np.einsum("ij,ij->i", X, X) + eps
            w = keep * w + mu * (X.T @ (eb / norm))
            y[i:i + SUB] = yb
        self.w = w
        self.hist = buf[len(x):]
        return y, x - y
