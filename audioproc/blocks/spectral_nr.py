from __future__ import annotations

import numpy as np

from ..block import FrameBlock, Param

RING = 8  # sub-windows in the minimum search
RING_SECONDS = 1.5  # how far back the noise floor search looks
BIAS = 5.0  # the running minimum sits at ~0.3x the average noise power (measured); this lands the estimate ~1.5x above it


class SpectralNr(FrameBlock):
    name = "Spectral Noise Reduction"
    category = "Spectral"
    description = "Learns the noise floor in each frequency bin and turns down the bins that are only noise. Adds about 20 ms of delay."
    params = [
        Param("strength", "Strength", 0.2, 4, default=1.0, decimals=2),
        Param("floor", "Max reduction", 3, 40, default=15, unit="dB", decimals=0),
    ]

    def reset_frames(self):
        bins = self.n // 2 + 1
        self.ps = None  # smoothed power per bin
        self.cur_min = np.full(bins, np.inf)
        self.ring = np.full((RING, bins), np.inf)
        self.ring_i = 0
        self.count = 0
        self.gain = np.ones(bins)
        self.sub_frames = max(1, int(RING_SECONDS / RING * self.fs / self.hop))

    def process_frame(self, spec):
        p = spec.real ** 2 + spec.imag ** 2
        self.ps = p if self.ps is None else 0.7 * self.ps + 0.3 * p

        # Noise floor = the lowest smoothed power seen in each bin over the
        # last RING_SECONDS. Speech and CW leave gaps, so the minimum is the
        # noise; and because the window slides, it follows a changing band.
        self.cur_min = np.minimum(self.cur_min, self.ps)
        self.count += 1
        if self.count >= self.sub_frames:
            self.ring[self.ring_i] = self.cur_min
            self.ring_i = (self.ring_i + 1) % RING
            self.cur_min = self.ps.copy()
            self.count = 0
        noise = np.minimum(self.ring.min(axis=0), self.cur_min) * BIAS

        g = np.sqrt(np.maximum(1.0 - self.strength * noise / np.maximum(self.ps, 1e-20), 0.0))
        g = np.maximum(g, 10.0 ** (-self.floor / 20.0))
        # open instantly, close gradually: cuts the "musical noise" chirps
        self.gain = np.where(g > self.gain, g, 0.6 * self.gain + 0.4 * g)
        return spec * self.gain
