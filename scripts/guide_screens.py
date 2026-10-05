"""Renders the screenshots used by build_user_guide.py into docs/guide/.

    python scripts/guide_screens.py

Runs the real window for a few seconds with the output MUTED, looping a
synthetic "noisy SSB with a carrier on it" clip through the SSB cleanup
preset, so the spectrum shows a believable before/after. Your own settings
and recordings are not touched.
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "guide"
OUT.mkdir(parents=True, exist_ok=True)

import numpy as np  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402
from scipy import signal  # noqa: E402

from audioproc.ui import main_window as mw  # noqa: E402
from audioproc.ui.theme import STYLESHEET  # noqa: E402

tmp = Path(tempfile.mkdtemp())
mw.SETTINGS = tmp / "settings.json"
mw.RECORD_DIR = tmp
QMessageBox.warning = lambda *a, **k: print("warning box:", a[1:])

FS = 48000


def demo_clip(seconds: float = 6.0) -> np.ndarray:
    """Band noise + speech-like bursts in 300-2700 Hz + a 1.2 kHz carrier."""
    rng = np.random.default_rng(3)
    n = int(seconds * FS)
    t = np.arange(n) / FS
    voice_band = signal.butter(4, [300, 2700], "band", fs=FS, output="sos")
    syllables = np.clip(np.sin(2 * np.pi * 2.3 * t), 0, 1) ** 2
    formants = sum(np.sin(2 * np.pi * f * t * (1 + 0.02 * np.sin(2 * np.pi * 3 * t)))
                   for f in (420, 640, 1050, 1700, 2300))
    speech = 0.05 * syllables * formants
    hiss = signal.sosfilt(signal.butter(2, 5000, "low", fs=FS, output="sos"), rng.standard_normal(n))
    return (signal.sosfilt(voice_band, speech) + 0.02 * hiss
            + 0.08 * np.sin(2 * np.pi * 1200 * t)).astype(np.float32)


app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(STYLESHEET)
w = mw.MainWindow()
w.resize(1320, 900)
w.show()
w.mute.setChecked(True)


def save(widget, name):
    widget.grab().save(str(OUT / name))


def step1():
    save(w, "empty.png")
    w._load_preset(w.preset_combo.findText("SSB cleanup"))
    w._use_clip(demo_clip(), FS, "rec_20261001_101500.wav")
    for st in w._strips:  # a second source on, so the mixer shows a mix (capture only: nothing is played)
        if st.label.startswith("Microphone (") and "CODEC" in st.label and not st.on:
            st.on_btn.click()
            st.fader.setValue(85)
            break
    w.clip_btn.click()  # starts the engine on the clip
    QTimer.singleShot(5000, step2)


def step2():
    save(w, "main.png")
    save(w.centralWidget().layout().itemAt(0).widget(), "devices.png")
    row = w.centralWidget().layout().itemAt(1).layout()
    save(row.itemAt(0).widget(), "source.png")
    save(row.itemAt(1).widget(), "monitor.png")
    save(w.spectrum, "spectrum.png")
    p = w._panels[0]  # just the controls, not the empty space below them
    p.grab().copy(0, 0, p.width(), 172).save(str(OUT / "panel.png"))
    save(w.centralWidget().layout().itemAt(4).widget(), "mixer.png")
    QTimer.singleShot(500, step3)


def step3():
    w._add_block(w.registry["ParametricEq"])
    QTimer.singleShot(600, step4)


def step4():
    save(w.centralWidget().layout().itemAt(3).widget(), "chain.png")
    w.close()
    app.quit()


QTimer.singleShot(800, step1)
app.exec()
print("screens written to", OUT)
