"""The plugin contract every processing block follows.

A block is one class in one file. It declares its `params` (the GUI builds
the controls from that list -- no UI code per block), designs itself in
`configure(fs)` and processes mono float64 chunks in `process(x)`.

The one rule that matters: `process` is called once per audio chunk, so
anything with memory (filter delay lines, envelopes, adaptive weights) MUST
live on `self` and carry over from one call to the next. A block that
restarts its state every chunk clicks at every chunk boundary. `SosFilter`
and `FrameBlock` below take care of that for the two common cases.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import signal


@dataclass
class Param:
    """One user-adjustable value. `kind` picks the control: "float"/"int" get
    a slider + number box, "choice" a dropdown, "bool" a tick box."""

    key: str
    label: str
    lo: float = 0.0
    hi: float = 1.0
    default: object = 0.0
    unit: str = ""
    scale: str = "lin"  # "lin" | "log" -- slider law only
    kind: str = "float"  # "float" | "int" | "choice" | "bool"
    choices: tuple = ()
    decimals: int = 1

    def coerce(self, value):
        """Clamp/convert a value (from the GUI or a preset file) to something
        this parameter accepts."""
        if self.kind == "bool":
            return bool(value)
        if self.kind == "choice":
            return value if value in self.choices else self.default
        try:
            v = min(max(float(value), self.lo), self.hi)
        except (TypeError, ValueError):
            return self.default
        return int(round(v)) if self.kind == "int" else v


class Block:
    """Base class. Subclasses set `name`, `category`, `params` and override
    `configure` / `process` (and `reset` if they hold state)."""

    name = "Block"
    category = "Other"
    description = ""
    params: list[Param] = []

    def __init__(self):
        self.enabled = True
        self.fs = 48000.0
        self.latency = 0  # samples of delay this block adds
        self.error = ""  # set by the chain if process() raises
        for p in self.params:
            setattr(self, p.key, p.default)

    def prepare(self, fs: float) -> None:
        """Called when the engine (re)starts at sample rate `fs`."""
        self.fs = float(fs)
        self.configure(self.fs)
        self.reset()

    def configure(self, fs: float) -> None:
        """(Re)design from the current parameter values. Runs on start and on
        every parameter change, so keep running state intact where possible
        -- wiping it here makes the audio click while a slider is dragged."""

    def reset(self) -> None:
        """Clear running state (delay lines, envelopes, learned weights)."""

    def process(self, x: np.ndarray) -> np.ndarray:
        """One chunk in, one chunk of the same length out."""
        return x


class SosFilter:
    """An IIR filter (second-order sections) that remembers its delay line
    between chunks. Swapping coefficients keeps the delay line unless the
    number of sections changed."""

    def __init__(self):
        self.sos = None
        self.zi = None

    def set_sos(self, sos) -> None:
        sos = np.atleast_2d(np.asarray(sos, dtype=float))
        if self.zi is None or self.zi.shape[0] != sos.shape[0]:
            self.zi = np.zeros((sos.shape[0], 2))
        self.sos = sos

    def reset(self) -> None:
        if self.zi is not None:
            self.zi[:] = 0.0

    def __call__(self, x: np.ndarray) -> np.ndarray:
        if self.sos is None:
            return x
        y, self.zi = signal.sosfilt(self.sos, x, zi=self.zi)
        return y


class FrameBlock(Block):
    """Base for FFT-domain blocks. Buffers arbitrary-size chunks into
    fixed, 50%-overlapped, windowed frames, hands each frame's spectrum to
    `process_frame`, and overlap-adds the results back into a continuous
    stream. Adds exactly one frame of latency.

    Subclasses implement `process_frame(spec) -> spec` and, if they keep
    per-bin state, `reset_frames()`.
    """

    frame_ms = 20.0

    def prepare(self, fs: float) -> None:
        n = 1 << int(round(np.log2(self.frame_ms * 1e-3 * fs)))
        self.n = max(64, n)
        self.hop = self.n // 2
        # sqrt-Hann on analysis and synthesis: the product is a Hann, which
        # sums to exactly 1 at 50% overlap.
        self.win = np.sqrt(signal.get_window("hann", self.n))
        self.latency = self.n
        super().prepare(fs)

    def reset(self) -> None:
        self._in = np.zeros(0)
        self._out = np.zeros(self.n)  # the one frame of latency
        self._ola = np.zeros(self.n)
        self.reset_frames()

    def reset_frames(self) -> None:
        pass

    def process_frame(self, spec: np.ndarray) -> np.ndarray:
        return spec

    def process(self, x: np.ndarray) -> np.ndarray:
        n, hop = self.n, self.hop
        self._in = np.concatenate([self._in, x])
        outs = [self._out]
        while len(self._in) >= n:
            spec = np.fft.rfft(self._in[:n] * self.win)
            self._ola += np.fft.irfft(self.process_frame(spec), n) * self.win
            outs.append(self._ola[:hop].copy())
            self._ola = np.concatenate([self._ola[hop:], np.zeros(hop)])
            self._in = self._in[hop:]
        out = np.concatenate(outs)
        self._out = out[len(x):]
        return out[: len(x)]
