"""The signal path: an ordered list of blocks, run in sequence."""
from __future__ import annotations

import logging
import threading

import numpy as np

from .block import Block

log = logging.getLogger("audioproc.chain")


class Chain:
    """One lock guards the block list and every block's parameters/state.
    The audio worker holds it for the few hundred microseconds a chunk takes
    to process; the GUI holds it while it changes something. That keeps a
    parameter change from landing halfway through a chunk (new coefficients
    against an old-shaped delay line)."""

    def __init__(self):
        self.blocks: list[Block] = []
        self.fs = 48000.0
        self.lock = threading.Lock()

    # -- audio thread -------------------------------------------------
    def process(self, x: np.ndarray) -> np.ndarray:
        with self.lock:
            for b in self.blocks:
                if not b.enabled:
                    continue
                try:
                    x = b.process(x)
                except Exception as exc:  # a broken plugin must not kill the audio
                    log.exception("block %s failed, bypassing it", b.name)
                    b.error = f"{type(exc).__name__}: {exc}"
                    b.enabled = False
        return x

    # -- GUI thread ---------------------------------------------------
    def set_fs(self, fs: float) -> None:
        with self.lock:
            self.fs = float(fs)
            for b in self.blocks:
                self._prepare(b)

    def _prepare(self, b: Block) -> None:
        try:
            b.prepare(self.fs)
        except Exception as exc:
            log.exception("block %s failed to prepare", b.name)
            b.error = f"{type(exc).__name__}: {exc}"
            b.enabled = False

    def add(self, block: Block, index: int | None = None) -> None:
        with self.lock:
            self._prepare(block)
            self.blocks.insert(len(self.blocks) if index is None else index, block)

    def remove(self, block: Block) -> None:
        with self.lock:
            self.blocks.remove(block)

    def move(self, block: Block, delta: int) -> None:
        with self.lock:
            i = self.blocks.index(block)
            j = min(max(i + delta, 0), len(self.blocks) - 1)
            self.blocks.insert(j, self.blocks.pop(i))

    def clear(self) -> None:
        with self.lock:
            self.blocks.clear()

    def set_param(self, block: Block, key: str, value) -> None:
        with self.lock:
            setattr(block, key, value)
            try:
                block.configure(self.fs)
            except Exception as exc:
                log.exception("block %s failed to configure", block.name)
                block.error = f"{type(exc).__name__}: {exc}"
                block.enabled = False

    def set_enabled(self, block: Block, on: bool) -> None:
        with self.lock:
            if on and not block.enabled:
                block.error = ""
                block.reset()  # don't replay stale state from before the bypass
            block.enabled = on

    @property
    def latency(self) -> int:
        return sum(b.latency for b in self.blocks if b.enabled)

    # -- presets ------------------------------------------------------
    def to_dict(self) -> dict:
        out = []
        for b in self.blocks:
            params = {}
            for p in b.params:
                v = getattr(b, p.key)
                params[p.key] = v.item() if isinstance(v, np.generic) else v
            out.append({"type": type(b).__name__, "enabled": b.enabled, "params": params})
        return {"blocks": out}

    def load_dict(self, data: dict, registry: dict) -> list[str]:
        """Replace the chain with the one described by `data`. Returns the
        names of any block types that are no longer available."""
        blocks, missing = build_blocks(data, registry)
        with self.lock:
            self.blocks = blocks
            for b in self.blocks:
                enabled = b.enabled
                self._prepare(b)
                b.enabled = enabled and not b.error
        return missing


def build_blocks(data: dict, registry: dict) -> tuple[list[Block], list[str]]:
    blocks, missing = [], []
    for item in data.get("blocks", []):
        cls = registry.get(item.get("type"))
        if cls is None:
            missing.append(str(item.get("type")))
            continue
        b = cls()
        for p in b.params:
            if p.key in item.get("params", {}):
                setattr(b, p.key, p.coerce(item["params"][p.key]))
        b.enabled = bool(item.get("enabled", True))
        blocks.append(b)
    return blocks, missing


def render_offline(data: dict, registry: dict, x: np.ndarray, fs: float, chunk: int = 512) -> np.ndarray:
    """Run a whole clip through a fresh copy of a chain (for "save
    processed"), in the same chunk size the live engine uses."""
    chain = Chain()
    chain.load_dict(data, registry)
    chain.set_fs(fs)
    lat = chain.latency
    x = np.concatenate([np.asarray(x, dtype=float), np.zeros(lat)])
    out = [chain.process(x[i:i + chunk]) for i in range(0, len(x), chunk)]
    y = np.concatenate(out) if out else np.zeros(0)
    return np.clip(np.nan_to_num(y[lat:]), -1.0, 1.0)
