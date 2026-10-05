from __future__ import annotations

import math

import numpy as np

from ..block import Block, Param, SosFilter


def _peaking(f, gain_db, q, fs):
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * f / fs
    alpha = math.sin(w0) / (2.0 * q)
    c = math.cos(w0)
    return [1 + alpha * a, -2 * c, 1 - alpha * a, 1 + alpha / a, -2 * c, 1 - alpha / a]


def _shelf(f, gain_db, fs, high):
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * f / fs
    c = math.cos(w0)
    k = 2.0 * math.sqrt(a) * math.sin(w0) / 2.0 * math.sqrt(2.0)
    s = -1.0 if high else 1.0  # the high shelf mirrors the low shelf
    return [
        a * ((a + 1) - s * (a - 1) * c + k),
        s * 2 * a * ((a - 1) - s * (a + 1) * c),
        a * ((a + 1) - s * (a - 1) * c - k),
        (a + 1) + s * (a - 1) * c + k,
        s * -2 * ((a - 1) + s * (a + 1) * c),
        (a + 1) + s * (a - 1) * c - k,
    ]


def _sos_row(coefs):
    b0, b1, b2, a0, a1, a2 = coefs
    return [b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]


class ParametricEq(Block):
    name = "Parametric EQ"
    category = "Tone"
    description = "Low shelf, two sweepable peaking bands and a high shelf."
    params = [
        Param("low_f", "Low shelf", 50, 1000, default=200, unit="Hz", scale="log", decimals=0),
        Param("low_g", "Low gain", -18, 18, default=0, unit="dB"),
        Param("mid1_f", "Mid 1", 100, 6000, default=800, unit="Hz", scale="log", decimals=0),
        Param("mid1_g", "Mid 1 gain", -18, 18, default=0, unit="dB"),
        Param("mid1_q", "Mid 1 Q", 0.3, 10, default=1.0, scale="log"),
        Param("mid2_f", "Mid 2", 100, 6000, default=2000, unit="Hz", scale="log", decimals=0),
        Param("mid2_g", "Mid 2 gain", -18, 18, default=0, unit="dB"),
        Param("mid2_q", "Mid 2 Q", 0.3, 10, default=1.0, scale="log"),
        Param("high_f", "High shelf", 500, 10000, default=3000, unit="Hz", scale="log", decimals=0),
        Param("high_g", "High gain", -18, 18, default=0, unit="dB"),
    ]

    def __init__(self):
        super().__init__()
        self.filt = SosFilter()

    def configure(self, fs):
        top = fs * 0.45
        self.filt.set_sos(np.array([
            _sos_row(_shelf(min(self.low_f, top), self.low_g, fs, high=False)),
            _sos_row(_peaking(min(self.mid1_f, top), self.mid1_g, self.mid1_q, fs)),
            _sos_row(_peaking(min(self.mid2_f, top), self.mid2_g, self.mid2_q, fs)),
            _sos_row(_shelf(min(self.high_f, top), self.high_g, fs, high=True)),
        ]))

    def reset(self):
        self.filt.reset()

    def process(self, x):
        return self.filt(x)
