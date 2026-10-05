"""Entry point: `python run.py`."""
from __future__ import annotations

import json
import logging
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from audioproc import APP_DIR, RESOURCE_DIR, seed_app_dir
from audioproc.ui.main_window import MainWindow
from audioproc.ui.theme import STYLESHEET


def selftest(path: str) -> int:
    """`--selftest <file>`: write what this build can see (blocks, presets,
    audio devices) and push a chunk through every block. The windowed .exe
    has no console, so this is how a fresh build gets checked."""
    import numpy as np
    import sounddevice as sd

    from audioproc.engine import loopback_sources
    from audioproc.registry import discover

    registry, errors = discover([APP_DIR / "blocks"])
    ran = {}
    for name, cls in registry.items():
        try:
            b = cls()
            b.prepare(48000)
            ran[name] = len(b.process(np.zeros(512))) == 512
        except Exception as exc:
            ran[name] = f"{type(exc).__name__}: {exc}"
    report = {
        "frozen": bool(getattr(sys, "frozen", False)),
        "app_dir": str(APP_DIR),
        "blocks": ran,
        "load_errors": errors,
        "presets": sorted(p.name for p in (APP_DIR / "presets").glob("*.json")),
        "template": (APP_DIR / "blocks" / "_template.py").exists(),
        "icon": (RESOURCE_DIR / "icon.ico").exists(),
        "audio_devices": len(sd.query_devices()),
        "loopback_sources": [name for _, name in loopback_sources()],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return 0


def livetest(path: str) -> int:
    """`--livetest <file>`: run the real window on a COPY of the current
    settings with the output muted, put a narrow Band Filter in the chain and
    measure whether the chain's output actually differs from its input.
    Answers "do the filters do anything in this build, on this PC?"."""
    import shutil
    import tempfile
    from pathlib import Path

    import numpy as np
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QMessageBox

    from audioproc.ui import main_window as mw

    tmp = Path(tempfile.mkdtemp())
    if mw.SETTINGS.exists():
        shutil.copy(mw.SETTINGS, tmp / "settings.json")
    mw.SETTINGS = tmp / "settings.json"  # the real settings are never written
    mw.RECORD_DIR = tmp
    report = {"frozen": bool(getattr(sys, "frozen", False)), "messages": [], "steps": {}}
    QMessageBox.warning = lambda *a, **k: report["messages"].append(list(map(str, a[1:3])))
    QMessageBox.critical = QMessageBox.warning

    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    w.mute.setChecked(True)
    e = w.engine
    taps = []
    grab = QTimer()
    grab.timeout.connect(lambda: taps.append((e.tap_in.copy(), e.tap_out.copy())))

    def measure(tag):
        def band(x, lo, hi):
            s = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
            f = np.fft.rfftfreq(len(x), 1 / e.fs)
            return 10 * np.log10(s[(f >= lo) & (f < hi)].mean() + 1e-20)
        report["steps"][tag] = {
            "chain": [[b.name, b.enabled, b.error] for b in w.chain.blocks],
            "source": e.source, "bypass": e.bypass, "running": e.running,
            "inputs_on": {s.name: [s.ok, s.error] for s in e.sources.values()},
            "input_level_db": round(float(np.mean([band(i, 30, 12000) for i, _ in taps])), 1) if taps else None,
            "out_minus_in_db": {name: round(float(np.mean([band(o, lo, hi) - band(i, lo, hi) for i, o in taps])), 1)
                                for name, lo, hi in (("below 200 Hz", 30, 200), ("500-2000 Hz", 500, 2000),
                                                     ("above 5 kHz", 5000, 12000))} if taps else None,
        }
        taps.clear()

    def with_filter():
        measure("chain as saved")
        w._clear_chain()
        w._add_block(w.registry["BandFilter"])  # what "+ Add block" does

    def bypassed():
        measure("band filter 300-2700 Hz added")
        w.bypass_btn.click()

    def done():
        measure("same, BYPASS on")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        w.close()
        app.quit()

    QTimer.singleShot(500, lambda: (w.live_btn.click(), grab.start(250)))
    QTimer.singleShot(4000, with_filter)
    QTimer.singleShot(7500, bypassed)
    QTimer.singleShot(10500, done)
    app.exec()
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # Let the audio thread take the interpreter back from the GUI thread
    # after 1 ms rather than the default 5 ms -- a chunk is only ~10 ms.
    sys.setswitchinterval(0.001)
    seed_app_dir()
    if len(sys.argv) == 3 and sys.argv[1] == "--selftest":
        return selftest(sys.argv[2])
    if len(sys.argv) == 3 and sys.argv[1] == "--livetest":
        return livetest(sys.argv[2])
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    icon = RESOURCE_DIR / "icon.ico"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
