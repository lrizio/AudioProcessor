"""Audio I/O and the processing thread.

    input source 1 --> FIFO --x gain--+
    input source 2 --> FIFO --x gain--+--> mix --+
    ...                               |          +--> worker: chain.process --> FIFO --callback--> output device
    recorded clip (looped) --------------------- +

Any number of input sources (capture devices and "PC playback" loopback
captures) can be on at once; each has its own fader and they are summed
into one mono signal -- the mixer. The recorder taps that mix, i.e. it
captures the RAW input before any processing, so a clip can be replayed
through the chain as often as needed while the blocks are adjusted.

The worker is paced by the output device: it makes one chunk whenever the
output FIFO has room. Every source runs on its own clock, so each sits
behind its own small FIFO that pads or drops a few milliseconds when its
clock drifts from the output's.

All streams are opened at the engine's own sample rate and Windows does any
rate conversion to/from the device (WASAPI is opened with auto_convert for
that). The DSP therefore never resamples chunk-by-chunk.
"""
from __future__ import annotations

import logging
import threading
import time
from fractions import Fraction

import numpy as np
import sounddevice as sd
from scipy import signal

from .chain import Chain

log = logging.getLogger("audioproc.engine")

BLOCK = 512  # samples per processing chunk
TAP_N = 8192  # samples kept for the spectrum display


def host_apis() -> list[tuple[int, str]]:
    return [(i, a["name"]) for i, a in enumerate(sd.query_hostapis())]


def devices(hostapi: int, kind: str) -> list[tuple[int, str]]:
    key = "max_input_channels" if kind == "input" else "max_output_channels"
    return [
        (i, d["name"]) for i, d in enumerate(sd.query_devices())
        if d["hostapi"] == hostapi and d[key] > 0
    ]


def loopback_sources() -> list[tuple[tuple[str, str], str]]:
    """Output devices whose playback can be captured, as
    ((\"loopback\", id), name). Empty if the `soundcard` library is missing."""
    try:
        import soundcard as sc
        return [(("loopback", s.id), s.name) for s in sc.all_speakers()]
    except Exception:
        log.exception("loopback sources unavailable")
        return []


def is_loopback(dev) -> bool:
    return isinstance(dev, (tuple, list)) and len(dev) == 2 and dev[0] == "loopback"


def rescan() -> None:
    """Restart PortAudio so devices plugged in since it started are listed.
    No stream may be open."""
    sd._terminate()
    sd._initialize()


def default_device(hostapi: int, kind: str) -> int:
    api = sd.query_hostapis(hostapi)
    return api["default_input_device" if kind == "input" else "default_output_device"]


def _extra_settings(device: int):
    api = sd.query_hostapis(sd.query_devices(device)["hostapi"])["name"]
    return sd.WasapiSettings(auto_convert=True) if "WASAPI" in api else None


def resample(x: np.ndarray, fs_from: float, fs_to: float) -> np.ndarray:
    """Whole-clip rate conversion (never used chunk-by-chunk)."""
    if round(fs_from) == round(fs_to) or len(x) == 0:
        return np.asarray(x, dtype=np.float32)
    frac = Fraction(round(fs_to), round(fs_from)).limit_denominator(2000)
    return signal.resample_poly(x, frac.numerator, frac.denominator).astype(np.float32)


class SampleFifo:
    """Fixed-size ring of samples between two threads. Writing into a full
    FIFO drops the oldest audio, which is what keeps latency bounded when
    two devices' clocks drift."""

    def __init__(self, capacity: int):
        self._buf = np.zeros(capacity, dtype=np.float32)
        self._cap = capacity
        self._r = 0
        self._n = 0
        self._lock = threading.Lock()

    @property
    def fill(self) -> int:
        return self._n

    def clear(self) -> None:
        with self._lock:
            self._r = self._n = 0

    def write(self, x: np.ndarray) -> None:
        with self._lock:
            x = x[-self._cap:]
            over = self._n + len(x) - self._cap
            if over > 0:
                self._r = (self._r + over) % self._cap
                self._n -= over
            w = (self._r + self._n) % self._cap
            first = min(len(x), self._cap - w)
            self._buf[w:w + first] = x[:first]
            self._buf[:len(x) - first] = x[first:]
            self._n += len(x)

    def read(self, n: int) -> tuple[np.ndarray, int]:
        """Returns (n samples, zero-padded if short; how many were real)."""
        out = np.zeros(n, dtype=np.float32)
        with self._lock:
            got = min(n, self._n)
            first = min(got, self._cap - self._r)
            out[:first] = self._buf[self._r:self._r + first]
            out[first:got] = self._buf[:got - first]
            self._r = (self._r + got) % self._cap
            self._n -= got
        return out, got

    def drop(self, n: int) -> None:
        with self._lock:
            n = min(n, self._n)
            self._r = (self._r + n) % self._cap
            self._n -= n


class InputSource:
    """One mixer channel: a capture device (key = its PortAudio index) or a
    loopback capture of an output device (key = ("loopback", id))."""

    CUSHION = 2 * BLOCK  # audio held back so a late chunk doesn't leave a gap
    TOO_FULL = 7 * BLOCK  # source running faster than the output: skip ahead

    def __init__(self, key, name: str, gain: float = 1.0):
        self.key = key
        self.name = name
        self.gain = gain
        self.peak = 0.0  # post-fader, read and zeroed by the GUI
        self.error = ""
        self.ok = False
        self.gaps = 0  # times this source ran dry mid-stream (clock drift or a stall)
        self._fifo = SampleFifo(16 * BLOCK)
        self._starved = True
        self._stream: sd.InputStream | None = None
        self._thread: threading.Thread | None = None
        self._run = False

    # -- lifecycle (GUI thread) ---------------------------------------
    def start(self, fs: int) -> None:
        """Never raises: a source that can't be opened leaves the reason in
        `error` and simply contributes nothing to the mix."""
        self.stop()
        self.error = ""
        self._fifo.clear()
        self._starved = True
        self._run = True
        if is_loopback(self.key):
            ready = threading.Event()
            self._thread = threading.Thread(target=self._loopback_reader, args=(self.key[1], fs, ready),
                                            name="audio-loopback", daemon=True)
            self._thread.start()
            ready.wait(timeout=3.0)  # so an open failure is known before we return
            return
        try:
            ch = min(2, sd.query_devices(self.key)["max_input_channels"])
            self._stream = sd.InputStream(
                device=self.key, channels=ch, samplerate=fs, dtype="float32", blocksize=BLOCK,
                latency="low", callback=self._callback, extra_settings=_extra_settings(self.key),
            )
            self._stream.start()
            self.ok = True
        except Exception as exc:
            log.exception("input %r failed to open", self.name)
            self._stream = None
            self.error = str(exc) or type(exc).__name__

    def stop(self) -> None:
        self._run = False
        self.ok = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                log.exception("closing input %r", self.name)
            self._stream = None

    # -- capture side (device threads) --------------------------------
    def _callback(self, indata, frames, time_info, status):
        self._fifo.write(indata.mean(axis=1) if indata.shape[1] > 1 else indata[:, 0])

    def _loopback_reader(self, speaker_id: str, fs: int, ready: threading.Event) -> None:
        """Captures what is being played on an output device ("what you
        hear"). PortAudio as shipped with sounddevice can't do WASAPI
        loopback, hence the separate `soundcard` library and this thread."""
        import ctypes
        # soundcard only initialises COM on the thread that imported it;
        # without this every call here fails with 0x800401F0.
        ctypes.windll.ole32.CoInitializeEx(None, 0)
        try:
            import soundcard as sc
            mic = sc.get_microphone(speaker_id, include_loopback=True)
            with mic.recorder(samplerate=fs, channels=2, blocksize=BLOCK) as rec:
                self.ok = True
                ready.set()
                while self._run:
                    data = rec.record(numframes=None)  # whatever has arrived
                    if len(data) == 0:
                        time.sleep(0.002)
                        continue
                    self._fifo.write(data.mean(axis=1, dtype=np.float32))
        except Exception as exc:
            log.exception("loopback capture of %r failed", self.name)
            self.error = str(exc) or type(exc).__name__
        finally:
            self.ok = False
            ready.set()
            ctypes.windll.ole32.CoUninitialize()

    # -- mix side (worker thread) -------------------------------------
    def read(self) -> np.ndarray | None:
        """The next chunk, fader applied, or None if this source has nothing
        ready (not open, silent device, or re-building its cushion)."""
        fill = self._fifo.fill
        if self._starved:
            if fill < self.CUSHION + BLOCK:
                return None
            self._starved = False
        elif fill > self.TOO_FULL:
            self._fifo.drop(fill - self.CUSHION - BLOCK)
        data, got = self._fifo.read(BLOCK)
        if got < BLOCK:
            self._starved = True
            self.gaps += 1
        data *= self.gain
        self.peak = max(self.peak, float(np.max(np.abs(data))))
        return data


class AudioEngine:
    def __init__(self, chain: Chain):
        self.chain = chain
        self.fs = 48000
        self.running = False
        self.source = "live"  # "live" (the input mix) | "clip"
        self.volume = 1.0
        self.muted = False
        self.bypass = False  # True: the chain is skipped, for A/B comparison

        # the mixer: every source that is switched on, by key
        self.sources: dict = {}

        # clip (a recording or an opened WAV), kept at its own rate and
        # converted to the engine rate whenever that changes
        self.clip_name = ""
        self._clip_src: tuple[np.ndarray, float] | None = None
        self.clip: np.ndarray | None = None
        self.clip_pos = 0

        self.recording = False
        self._rec_chunks: list[np.ndarray] = []
        self._rec_samples = 0

        # read (and zeroed) by the GUI meter timer
        self.in_peak = 0.0
        self.out_peak = 0.0
        self.cpu = 0.0  # fraction of real time spent in the chain
        self.underruns = 0

        self.tap_in = np.zeros(TAP_N, dtype=np.float32)
        self.tap_out = np.zeros(TAP_N, dtype=np.float32)

        self._fifo = SampleFifo(16 * BLOCK)
        self._starved = True
        self._out_frames = BLOCK
        self._out_stream: sd.OutputStream | None = None
        self._thread: threading.Thread | None = None
        self._run = False

    # -- lifecycle ----------------------------------------------------
    def start(self, out_dev: int, fs: int) -> None:
        """Raises if the output device can't be opened. Input sources that
        fail are not fatal (the others, and clip playback, still work);
        each leaves its reason in its own `error`."""
        self.stop()
        self.fs = int(fs)
        self.chain.set_fs(self.fs)
        self._convert_clip()
        self._fifo.clear()
        self._starved = True
        self.underruns = 0
        self.cpu = 0.0
        self.tap_in[:] = 0
        self.tap_out[:] = 0

        out_ch = min(2, sd.query_devices(out_dev)["max_output_channels"])
        self._out_stream = sd.OutputStream(
            device=out_dev, channels=out_ch, samplerate=self.fs, dtype="float32",
            latency="low", callback=self._out_cb, extra_settings=_extra_settings(out_dev),
        )
        self._out_stream.start()
        self.running = True
        for src in list(self.sources.values()):
            src.start(self.fs)
        self._run = True
        self._thread = threading.Thread(target=self._worker, name="audio-dsp", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._run = False
        self.recording = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        for src in list(self.sources.values()):
            src.stop()
        if self._out_stream is not None:
            try:
                self._out_stream.stop()
                self._out_stream.close()
            except Exception:
                log.exception("closing output stream")
            self._out_stream = None
        self.running = False

    # -- mixer --------------------------------------------------------
    def add_source(self, key, name: str, gain: float = 1.0) -> InputSource:
        """Switch a mixer channel on; opens it straight away if running."""
        if key in self.sources:
            self.sources[key].gain = gain
            return self.sources[key]
        src = InputSource(key, name, gain)
        if self.running:
            src.start(self.fs)
        self.sources = {**self.sources, key: src}  # replaced whole: the worker iterates it
        return src

    def remove_source(self, key) -> None:
        src = self.sources.get(key)
        if src is None:
            return
        self.sources = {k: v for k, v in self.sources.items() if k != key}
        src.stop()

    def clear_sources(self) -> None:
        old, self.sources = self.sources, {}
        for src in old.values():
            src.stop()

    @property
    def has_input(self) -> bool:
        return any(s.ok for s in self.sources.values())

    def _mix(self) -> np.ndarray:
        mix = np.zeros(BLOCK, dtype=np.float32)
        for src in self.sources.values():
            data = src.read()
            if data is not None:
                mix += data
        return mix

    # -- source / clip ------------------------------------------------
    def set_source(self, source: str) -> None:
        if source == "clip":
            self.clip_pos = 0
        self.source = source

    def set_clip(self, data: np.ndarray, fs: float, name: str) -> None:
        self._clip_src = (np.asarray(data, dtype=np.float32), float(fs))
        self.clip_name = name
        self._convert_clip()

    def _convert_clip(self) -> None:
        if self._clip_src is None:
            return
        data, fs = self._clip_src
        self.clip_pos = 0
        self.clip = resample(data, fs, self.fs)

    def _next_clip_block(self) -> np.ndarray:
        clip = self.clip
        pos = self.clip_pos % len(clip)
        x = clip[pos:pos + BLOCK]
        if len(x) < BLOCK:  # wrap: the clip loops
            x = np.concatenate([x, clip[:BLOCK - len(x)]])
        self.clip_pos = (pos + BLOCK) % len(clip)
        return x

    # -- recording ----------------------------------------------------
    def start_record(self) -> None:
        self._rec_chunks = []
        self._rec_samples = 0
        self.recording = True

    def stop_record(self) -> np.ndarray:
        self.recording = False
        chunks, self._rec_chunks = self._rec_chunks, []
        return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)

    @property
    def record_seconds(self) -> float:
        return self._rec_samples / self.fs

    # -- audio callback / worker --------------------------------------
    def _out_cb(self, outdata, frames, time_info, status):
        self._out_frames = frames
        # After running dry, wait for a cushion before resuming so a late
        # chunk doesn't glitch on every callback. Two chunks (~21 ms at
        # 48 kHz) rides out the GUI thread holding the interpreter while it
        # repaints; one chunk measurably did not.
        if self._starved and self._fifo.fill < frames + 2 * BLOCK:
            outdata[:] = 0
            return
        data, got = self._fifo.read(frames)
        if got < frames:
            if not self._starved:
                self.underruns += 1
            self._starved = True
        else:
            self._starved = False
        if self.muted:
            outdata[:] = 0
        else:
            outdata[:] = (data * self.volume)[:, None]

    def _worker(self) -> None:
        block_time = BLOCK / self.fs
        while self._run:
            # paced by the output: keep a couple of callbacks' worth queued
            if self._fifo.fill >= 2 * self._out_frames + 3 * BLOCK:
                time.sleep(0.002)
                continue
            # The mix is made even while a clip plays, so the mixer meters
            # stay live and the source FIFOs keep draining.
            mix = self._mix()
            if self.recording:
                self._rec_chunks.append(mix)
                self._rec_samples += BLOCK
            if self.source == "clip" and self.clip is not None and len(self.clip):
                x = self._next_clip_block()
            else:
                x = mix
            self.in_peak = max(self.in_peak, float(np.max(np.abs(x))))

            t0 = time.perf_counter()
            y = x if self.bypass else self.chain.process(x.astype(np.float64))
            self.cpu += 0.1 * ((time.perf_counter() - t0) / block_time - self.cpu)
            y = np.clip(np.nan_to_num(y), -1.0, 1.0).astype(np.float32)
            self.out_peak = max(self.out_peak, float(np.max(np.abs(y))) if len(y) else 0.0)

            for tap, data in ((self.tap_in, x), (self.tap_out, y)):
                n = len(data)
                tap[:-n] = tap[n:]
                tap[-n:] = data
            self._fifo.write(y)
