"""Offline checks of the DSP blocks on synthetic signals -- no audio
hardware needed. Run with `python tests/test_blocks.py` (or pytest)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audioproc.block import FrameBlock  # noqa: E402
from audioproc.chain import Chain, render_offline  # noqa: E402
from audioproc.registry import discover  # noqa: E402

FS = 48000
REG, ERRORS = discover()
RNG = np.random.default_rng(1)


def make(name, **params):
    b = REG[name]()
    for k, v in params.items():
        assert any(p.key == k for p in b.params), f"{name} has no param {k}"
        setattr(b, k, v)
    b.prepare(FS)
    return b


def run(block, x, chunk=512):
    return np.concatenate([block.process(x[i:i + chunk]) for i in range(0, len(x), chunk)])


def tone(f, secs=2.0, amp=0.5):
    return amp * np.sin(2 * np.pi * f * np.arange(int(secs * FS)) / FS)


def noise(secs=2.0, amp=0.1):
    return amp * RNG.standard_normal(int(secs * FS))


def db(x):
    return 10 * np.log10(np.mean(np.square(x)) + 1e-30)


def tone_db(x, f):
    """Power of the component at f (dB), by correlation."""
    t = np.arange(len(x)) / FS
    return 20 * np.log10(abs(np.mean(x * np.exp(-2j * np.pi * f * t))) * 2 + 1e-15)


def test_registry():
    assert not ERRORS, ERRORS
    expected = {"BandFilter", "Notch", "CwPeak", "AutoNotch", "LmsNr", "SpectralNr",
                "Agc", "Compressor", "Limiter", "NoiseGate", "ParametricEq", "Gain"}
    assert expected <= set(REG), expected - set(REG)


def test_chunking_is_seamless():
    """Every block must give the same output whatever the chunk size --
    i.e. it carries its state across chunk boundaries."""
    x = tone(700, 1.0) + noise(1.0)
    for name in REG:
        a = run(make(name), x, chunk=512)
        b = run(make(name), x, chunk=4096)
        if name in ("AutoNotch", "LmsNr"):
            continue  # weights update per 16-sample sub-block; 512 and 4096 both align
        tol = 1e-9
        if name in ("Agc", "Compressor", "Limiter", "NoiseGate"):
            # level sub-blocks restart at chunk edges when the chunk isn't a
            # multiple of 1 ms, so allow a small difference -- but no clicks
            tol = 0.05
        assert np.max(np.abs(a - b)) < tol, (name, np.max(np.abs(a - b)))
    for name in ("AutoNotch", "LmsNr"):
        a = run(make(name), x, chunk=512)
        b = run(make(name), x, chunk=4096)
        assert np.max(np.abs(a - b)) < 1e-9, name


def test_band_filter():
    x = tone(100) + tone(1000) + tone(6000)
    y = run(make("BandFilter", low=300, high=2700), x)[FS:]
    assert tone_db(y, 1000) > tone_db(x, 1000) - 1
    assert tone_db(y, 100) < tone_db(x, 100) - 30
    assert tone_db(y, 6000) < tone_db(x, 6000) - 25
    y = run(make("BandFilter", mode="Low-pass", high=2700), x)[FS:]
    assert tone_db(y, 100) > tone_db(x, 100) - 1 and tone_db(y, 6000) < tone_db(x, 6000) - 25
    y = run(make("BandFilter", mode="High-pass", low=300), x)[FS:]
    assert tone_db(y, 6000) > tone_db(x, 6000) - 1 and tone_db(y, 100) < tone_db(x, 100) - 30


def test_notch():
    x = tone(1000) + tone(1500)
    y = run(make("Notch", freq=1000, q=30), x)[FS:]
    assert tone_db(y, 1000) < tone_db(x, 1000) - 40
    assert tone_db(y, 1500) > tone_db(x, 1500) - 1


def test_cw_peak():
    x = tone(700) + tone(1200)
    y = run(make("CwPeak", center=700, width=150), x)[FS:]
    assert tone_db(y, 700) > tone_db(x, 700) - 1
    assert tone_db(y, 1200) < tone_db(x, 1200) - 25


def test_auto_notch():
    n = noise(4.0)
    x = tone(1200, 4.0) + n
    y = run(make("AutoNotch"), x)
    cut = tone_db(x[-FS:], 1200) - tone_db(y[-FS:], 1200)
    assert cut > 20, cut
    # the broadband part should survive
    assert db(y[-FS:]) > db(n[-FS:]) - 3, (db(y[-FS:]), db(n[-FS:]))
    return cut


def test_lms_nr():
    s = tone(700, 4.0, amp=0.2)
    x = s + noise(4.0, amp=0.2)
    y = run(make("LmsNr"), x)[-FS:]
    snr_in = db(s) - db(x - s)
    sig = tone_db(y, 700)
    resid = y - 10 ** (sig / 20) * np.sin(2 * np.pi * 700 * np.arange(len(y)) / FS + _phase(y, 700))
    snr_out = (sig - 3) - db(resid)
    assert snr_out > snr_in + 6, (snr_in, snr_out)
    return snr_out - snr_in


def _phase(x, f):
    t = np.arange(len(x)) / FS
    return np.angle(np.mean(x * np.exp(-2j * np.pi * f * t))) + np.pi / 2


def test_frame_block_is_transparent():
    b = FrameBlock()
    b.prepare(FS)
    x = noise(1.0)
    y = run(b, x, chunk=500)  # deliberately not a multiple of the hop
    assert b.latency == 1024
    # after the first frame's fade-in the output is the input, one frame late
    assert np.max(np.abs(y[2 * b.n:] - x[b.n:-b.n])) < 1e-9


def test_spectral_nr():
    n = noise(6.0, amp=0.05)
    gate = (np.arange(len(n)) // (FS // 4)) % 2  # tone keyed on/off every 250 ms
    s = tone(800, 6.0, amp=0.3) * gate
    b = make("SpectralNr")
    y = run(b, s + n)
    lat = b.latency
    y = y[lat:]
    s, n = s[:-lat], n[:-lat]
    # last 2 s: noise in the gaps should be well down, the tone kept
    seg = slice(len(y) - 2 * FS, len(y))
    off = gate[:len(y)][seg] == 0
    on = ~off
    cut = db((s + n)[seg][off]) - db(y[seg][off])
    assert cut > 8, cut
    kept = db(y[seg][on]) - db((s + n)[seg][on])
    assert kept > -2, kept
    return cut


def test_agc():
    quiet, loud = tone(700, 2.0, amp=0.01), tone(700, 2.0, amp=0.8)
    b = make("Agc", target=-12, max_gain=40)
    y = run(b, np.concatenate([quiet, loud, quiet]))
    target = 10 ** (-12 / 20)
    for seg in (y[FS + FS // 2:2 * FS], y[3 * FS + FS // 2:4 * FS], y[5 * FS + FS // 2:]):
        assert abs(np.max(np.abs(seg)) / target - 1) < 0.1, np.max(np.abs(seg))


def test_compressor_limiter_gate():
    x = tone(700, 1.0, amp=1.0)
    y = run(make("Compressor", threshold=-20, ratio=4), x)[FS // 2:]
    assert abs(20 * np.log10(np.max(np.abs(y))) - (-15)) < 0.7  # 20 over -> 5 over

    y = run(make("Limiter", ceiling=-6), x)
    assert np.max(np.abs(y)) <= 10 ** (-6 / 20) + 1e-12

    x = np.concatenate([tone(700, 1.0, amp=0.001), tone(700, 1.0, amp=0.3), tone(700, 1.0, amp=0.001)])
    y = run(make("NoiseGate", threshold=-40, depth=40, hold=50, release=50), x)
    assert np.max(np.abs(y[FS // 2:FS])) < 0.001 * 10 ** (-35 / 20)  # closed
    assert np.max(np.abs(y[FS + FS // 2:2 * FS])) > 0.29  # open
    assert np.max(np.abs(y[2 * FS + FS // 2:])) < 0.001 * 10 ** (-35 / 20)  # closed again


def test_eq_and_gain():
    x = tone(100) + tone(1000) + tone(8000)
    y = run(make("ParametricEq"), x)[FS:]
    for f in (100, 1000, 8000):  # all gains at 0 dB -> flat
        assert abs(tone_db(y, f) - tone_db(x, f)) < 0.01
    y = run(make("ParametricEq", low_g=6, mid1_f=1000, mid1_g=-9, high_g=12), x)[FS:]
    assert abs(tone_db(y, 100) - tone_db(x, 100) - 6) < 1.5
    assert abs(tone_db(y, 1000) - tone_db(x, 1000) + 9) < 0.7
    assert abs(tone_db(y, 8000) - tone_db(x, 8000) - 12) < 1.5
    y = run(make("Gain", gain=-6), x)
    assert abs(db(y) - db(x) + 6) < 0.01


def test_presets_roundtrip_and_render():
    chain = Chain()
    for name in ("BandFilter", "AutoNotch", "SpectralNr", "Agc"):
        chain.add(REG[name]())
    chain.set_param(chain.blocks[0], "low", 400.0)
    chain.set_enabled(chain.blocks[1], False)
    data = chain.to_dict()
    other = Chain()
    assert other.load_dict(data, REG) == []
    assert other.to_dict() == data
    assert other.load_dict({"blocks": [{"type": "Gone"}]}, REG) == ["Gone"]
    x = tone(1000, 1.0)
    y = render_offline(data, REG, x, FS)
    assert len(y) == len(x) and np.max(np.abs(y)) > 0.05


def test_broken_block_is_bypassed():
    class Broken(REG["Gain"]):
        def process(self, x):
            raise RuntimeError("boom")
    chain = Chain()
    chain.add(Broken())
    x = tone(1000, 0.1)
    assert np.array_equal(chain.process(x), x)
    assert not chain.blocks[0].enabled and "boom" in chain.blocks[0].error


def test_realtime_budget():
    """Whole starter set in one chain must run far faster than real time."""
    chain = Chain()
    for cls in REG.values():
        chain.add(cls())
    x = noise(5.0)
    t0 = time.perf_counter()
    for i in range(0, len(x), 512):
        chain.process(x[i:i + 512])
    load = (time.perf_counter() - t0) / 5.0
    assert load < 0.5, load
    return load


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                result = fn()
                print(f"PASS {name}" + (f"  ({result:.2f})" if isinstance(result, float) else ""))
            except Exception as exc:
                failed += 1
                print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    sys.exit(1 if failed else 0)
