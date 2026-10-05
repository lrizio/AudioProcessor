from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QInputDialog,
    QLabel, QMainWindow, QMenu, QMessageBox, QPushButton,
    QScrollArea, QSlider, QToolButton, QVBoxLayout, QWidget,
)
from scipy.io import wavfile

from .. import APP_DIR, __version__
from .. import engine as eng
from ..chain import Chain, render_offline
from ..registry import by_category, discover
from .block_panel import BlockPanel
from .mixer import UNITY, MixerStrip
from .spectrum import SpectrumWidget
from .widgets import Bar, Meter

log = logging.getLogger("audioproc.ui")

PRESET_DIR = APP_DIR / "presets"
RECORD_DIR = APP_DIR / "recordings"
SETTINGS = APP_DIR / "settings.json"
RATES = [8000, 12000, 16000, 24000, 48000]
LOOPBACK_PREFIX = "PC playback: "

LIT = {
    "green": "background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #4fbf6a, stop:1 #257a3a); color: white; font-weight: bold;",
    "blue": "background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #4fa9e0, stop:1 #2a6f96); color: white; font-weight: bold;",
    "red": "background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #e0564f, stop:1 #962a2a); color: white; font-weight: bold;",
}


def read_wav(path: str) -> tuple[np.ndarray, int]:
    """Any PCM/float WAV -> mono float32 in -1..1."""
    fs, data = wavfile.read(path)
    if data.dtype == np.uint8:
        x = (data.astype(np.float32) - 128.0) / 128.0
    elif np.issubdtype(data.dtype, np.integer):
        x = data.astype(np.float32) / float(np.iinfo(data.dtype).max + 1)
    else:
        x = data.astype(np.float32)
    if x.ndim > 1:
        x = x.mean(axis=1)
    return x, int(fs)


def write_wav(path: str | Path, x: np.ndarray, fs: int) -> None:
    wavfile.write(str(path), int(fs), (np.clip(x, -1.0, 1.0) * 32767.0).astype(np.int16))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Audio Processor {__version__}")
        self.resize(1320, 900)

        PRESET_DIR.mkdir(exist_ok=True)
        RECORD_DIR.mkdir(exist_ok=True)
        self.registry, self.load_errors = discover([APP_DIR / "blocks"])
        self.chain = Chain()
        self.engine = eng.AudioEngine(self.chain)
        self._rec_t0 = 0.0
        self._panels: list[BlockPanel] = []
        self._strips: list[MixerStrip] = []

        root = QWidget()
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(8)
        lay.addWidget(self._build_io())
        row = QHBoxLayout()
        row.addWidget(self._build_source(), 1)
        row.addWidget(self._build_monitor(), 1)
        lay.addLayout(row)
        self.spectrum = SpectrumWidget()
        self.spectrum.setMinimumHeight(140)
        lay.addWidget(self.spectrum, 1)
        lay.addWidget(self._build_chain())
        lay.addWidget(self._build_mixer())

        self._load_settings()
        self._refresh_presets()
        self._update_buttons()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(50)

        if self.load_errors:
            QTimer.singleShot(300, lambda: QMessageBox.warning(
                self, "Block load errors",
                "These block files could not be loaded:\n\n" + "\n".join(self.load_errors)))

    # ================= UI construction =================
    def _build_io(self) -> QGroupBox:
        box = QGroupBox("Audio devices")
        h = QHBoxLayout(box)
        self.api_combo = QComboBox()
        for idx, name in eng.host_apis():
            self.api_combo.addItem(name.replace("Windows ", ""), idx)
        self.out_combo = QComboBox()
        self.rate_combo = QComboBox()
        for r in RATES:
            self.rate_combo.addItem(f"{r} Hz", r)
        self.rate_combo.setCurrentIndex(len(RATES) - 1)
        for label, w, stretch in (("Driver", self.api_combo, 0), ("Output", self.out_combo, 1),
                                  ("Rate", self.rate_combo, 0)):
            h.addWidget(QLabel(label))
            h.addWidget(w, stretch)
        # `activated` fires only for a choice the user made, not for the
        # programmatic refills -- a change while running restarts the audio
        # on the new device straight away.
        self.api_combo.activated.connect(lambda _: self._driver_changed())
        for combo in (self.out_combo, self.rate_combo):
            combo.activated.connect(lambda _: self._devices_changed())
        rescan = QPushButton("Rescan")
        rescan.setToolTip("Look again for audio devices (after plugging in a radio or sound card)")
        rescan.clicked.connect(self._rescan_devices)
        h.addWidget(rescan)
        self.start_btn = QPushButton("START")
        self.start_btn.setFixedWidth(110)
        self.start_btn.clicked.connect(self._toggle_engine)
        h.addWidget(self.start_btn)
        wasapi = self.api_combo.findText("WASAPI")
        self.api_combo.setCurrentIndex(max(wasapi, 0))
        return box

    def _build_source(self) -> QGroupBox:
        box = QGroupBox("Source and recording")
        h = QHBoxLayout(box)
        self.live_btn = QPushButton("LIVE")
        self.live_btn.setToolTip("Process the input mix (everything switched ON in the Input mixer)")
        self.live_btn.clicked.connect(lambda: self._set_source("live"))
        self.clip_btn = QPushButton("PLAY CLIP")
        self.clip_btn.setToolTip("Loop the recorded/opened clip through the chain")
        self.clip_btn.clicked.connect(lambda: self._set_source("clip"))
        self.rec_btn = QPushButton("● REC")
        self.rec_btn.setToolTip("Record the input mix (before processing). Stopping loads it as the clip.")
        self.rec_btn.clicked.connect(self._toggle_record)
        for b in (self.live_btn, self.clip_btn, self.rec_btn):
            b.setFixedWidth(96)
            h.addWidget(b)

        v = QVBoxLayout()
        self.clip_label = QLabel("No clip - record one or open a WAV")
        self.clip_label.setStyleSheet("color: #bbb;")
        self.clip_bar = Bar(height=8)
        v.addWidget(self.clip_label)
        v.addWidget(self.clip_bar)
        h.addLayout(v, 1)

        open_btn = QPushButton("Open WAV…")
        open_btn.clicked.connect(self._open_wav)
        self.save_btn = QPushButton("Save processed…")
        self.save_btn.setToolTip("Run the whole clip through the current chain and save the result")
        self.save_btn.clicked.connect(self._save_processed)
        h.addWidget(open_btn)
        h.addWidget(self.save_btn)
        return box

    def _build_monitor(self) -> QGroupBox:
        box = QGroupBox("Monitor")
        h = QHBoxLayout(box)
        v = QVBoxLayout()
        self.in_meter, self.out_meter = Meter(), Meter()
        for name, meter in (("IN", self.in_meter), ("OUT", self.out_meter)):
            r = QHBoxLayout()
            lab = QLabel(name)
            lab.setFixedWidth(30)
            r.addWidget(lab)
            r.addWidget(meter)
            v.addLayout(r)
        h.addLayout(v)
        h.addWidget(QLabel("Volume"))
        self.vol = QSlider(Qt.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(70)
        self.vol.setMinimumWidth(120)
        self.vol.valueChanged.connect(self._on_volume)
        h.addWidget(self.vol, 1)
        self.mute = QCheckBox("Mute")
        self.mute.toggled.connect(lambda on: setattr(self.engine, "muted", on))
        h.addWidget(self.mute)
        self.status = QLabel("Stopped")
        self.status.setStyleSheet("color: #9ab;")
        self.status.setMinimumWidth(170)
        h.addWidget(self.status)
        self._on_volume(self.vol.value())
        return box

    def _build_chain(self) -> QGroupBox:
        box = QGroupBox("Processing chain  (input → left to right → output)")
        v = QVBoxLayout(box)
        bar = QHBoxLayout()
        add = QToolButton()
        add.setText("+ Add block")
        add.setPopupMode(QToolButton.InstantPopup)
        add.setStyleSheet("QToolButton { padding: 5px 14px; }")
        menu = QMenu(add)
        for cat, classes in by_category(self.registry):
            sub = menu.addMenu(cat)
            for cls in classes:
                act = sub.addAction(cls.name)
                act.setToolTip(cls.description)
                act.triggered.connect(lambda _=False, c=cls: self._add_block(c))
            sub.setToolTipsVisible(True)
        add.setMenu(menu)
        bar.addWidget(add)
        bar.addSpacing(20)
        bar.addWidget(QLabel("Preset"))
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(220)
        self.preset_combo.activated.connect(self._load_preset)
        bar.addWidget(self.preset_combo)
        for text, slot in (("Save as…", self._save_preset), ("Delete", self._delete_preset),
                           ("Clear chain", self._clear_chain)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            bar.addWidget(b)
        bar.addSpacing(20)
        self.bypass_btn = QPushButton("BYPASS")
        self.bypass_btn.setCheckable(True)
        self.bypass_btn.setFixedWidth(96)
        self.bypass_btn.setToolTip("Skip the whole chain, to compare the sound with and without it")
        self.bypass_btn.toggled.connect(self._on_bypass)
        bar.addWidget(self.bypass_btn)
        bar.addStretch(1)
        self.latency_label = QLabel("")
        self.latency_label.setStyleSheet("color: #9ab;")
        bar.addWidget(self.latency_label)
        v.addLayout(bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFixedHeight(312)
        self.panel_host = QWidget()
        self.panel_row = QHBoxLayout(self.panel_host)
        self.panel_row.setContentsMargins(0, 0, 0, 0)
        self.panel_row.setSpacing(8)
        self.scroll.setWidget(self.panel_host)
        v.addWidget(self.scroll)
        return box

    def _build_mixer(self) -> QGroupBox:
        box = QGroupBox("Input mixer  (every source switched ON is added together and fed to the chain)")
        v = QVBoxLayout(box)
        v.setContentsMargins(8, 10, 8, 6)
        self.mixer_scroll = QScrollArea()
        self.mixer_scroll.setWidgetResizable(True)
        self.mixer_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.mixer_scroll.setFixedHeight(100)
        host = QWidget()
        self.mixer_row = QHBoxLayout(host)
        self.mixer_row.setContentsMargins(0, 0, 0, 0)
        self.mixer_row.setSpacing(8)
        self.mixer_scroll.setWidget(host)
        v.addWidget(self.mixer_scroll)
        return box

    # ================= devices / engine =================
    def _fill_devices(self, want_out: str = "") -> None:
        api = self.api_combo.currentData()
        self.out_combo.clear()
        for idx, name in eng.devices(api, "output"):
            self.out_combo.addItem(name, idx)
        pick = self.out_combo.findText(want_out) if want_out else -1
        if pick < 0 and want_out:
            # same device under another driver: MME cuts names to 31 characters
            pick = next((i for i in range(self.out_combo.count())
                         if want_out.startswith(self.out_combo.itemText(i))
                         or self.out_combo.itemText(i).startswith(want_out)), -1)
        if pick < 0:
            pick = self.out_combo.findData(eng.default_device(api, "output"))
        self.out_combo.setCurrentIndex(max(pick, 0))

    # -- mixer --------------------------------------------------------
    def _mixer_state(self) -> dict:
        return {st.label: {"on": st.on, "level": st.fader.value()} for st in self._strips}

    def _rebuild_mixer(self, state: dict | None = None) -> None:
        """One strip per capture device of the current driver, plus one per
        output device whose playback can be captured. `state` (from the
        settings file or the strips being replaced) is matched by name; a
        device index is only valid until the next driver change or rescan,
        so the engine's sources are rebuilt along with the strips."""
        state = self._mixer_state() if state is None else state
        self.engine.clear_sources()
        while self.mixer_row.count():
            item = self.mixer_row.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self._strips = []
        api = self.api_combo.currentData()
        found = [(idx, name, name) for idx, name in eng.devices(api, "input")]
        found += [(key, name, LOOPBACK_PREFIX + name) for key, name in eng.loopback_sources()]
        for key, name, label in found:
            st = MixerStrip(key, name, label)
            saved = state.get(label, {})
            st.set_state(bool(saved.get("on", False)), int(saved.get("level", UNITY)))
            st.toggled.connect(self._strip_toggled)
            st.level_changed.connect(self._strip_level)
            self.mixer_row.addWidget(st)
            self._strips.append(st)
        if not self._strips:
            hint = QLabel("No input sources found. Plug one in and press Rescan.")
            hint.setStyleSheet("color: #778; font-weight: normal;")
            self.mixer_row.addWidget(hint)
        self.mixer_row.addStretch(1)
        self._apply_output_block()
        for st in self._strips:
            if st.on:
                self.engine.add_source(st.key, st.label, st.gain)
        self._show_source_errors()

    def _apply_output_block(self) -> None:
        """Capturing the device we also play to would re-capture our own
        output: an endless echo. That one "PC playback" strip is greyed out
        and switched off. (MME cuts device names to 31 characters, hence the
        prefix comparison.)"""
        out_name = self.out_combo.currentText()
        for st in self._strips:
            same = eng.is_loopback(st.key) and bool(out_name) and (
                st.name.startswith(out_name) or out_name.startswith(st.name))
            st.set_blocked("This is the Output device. Capturing it would echo endlessly, so it "
                           "can't be used as an input. Choose a different Output to use it." if same else "")
            if same and st.on:
                st.set_state(False, st.fader.value())
                self.engine.remove_source(st.key)

    def _strip_toggled(self, strip: MixerStrip, on: bool) -> None:
        if on:
            self.engine.add_source(strip.key, strip.label, strip.gain)
        else:
            self.engine.remove_source(strip.key)
        self._show_source_errors()

    def _strip_level(self, strip: MixerStrip) -> None:
        src = self.engine.sources.get(strip.key)
        if src is not None:
            src.gain = strip.gain

    def _show_source_errors(self) -> None:
        for st in self._strips:
            src = self.engine.sources.get(st.key)
            st.set_error(src.error if src is not None else "")

    # -- engine -------------------------------------------------------
    def _driver_changed(self) -> None:
        """A different driver has different devices (and device numbers)."""
        was_running = self.engine.running
        self._stop_record(save=True)
        self.engine.stop()
        self._fill_devices(self.out_combo.currentText())
        self._rebuild_mixer()
        if was_running:
            self._start_engine()
        self._update_buttons()

    def _devices_changed(self) -> None:
        was_running = self.engine.running
        if was_running:
            self._stop_record(save=True)
            self.engine.stop()
        self._apply_output_block()
        if was_running:
            self._start_engine()
        self._update_buttons()

    def _rescan_devices(self) -> None:
        """PortAudio lists devices once, when it starts; anything plugged in
        later only shows up after it is restarted."""
        was_running = self.engine.running
        self._stop_record(save=True)
        self.engine.stop()
        state = self._mixer_state()
        self.engine.clear_sources()  # no stream may be open during a rescan
        eng.rescan()
        self._fill_devices(self.out_combo.currentText())
        self._rebuild_mixer(state)
        if was_running:
            self._start_engine()
        self._update_buttons()

    def _toggle_engine(self) -> None:
        if self.engine.running:
            self._stop_record(save=True)
            self.engine.stop()
        else:
            self._start_engine()
        self._update_buttons()

    def _start_engine(self) -> bool:
        out_dev = self.out_combo.currentData()
        if out_dev is None:
            QMessageBox.warning(self, "No output", "No output device is available for this driver.")
            return False
        try:
            self.engine.start(out_dev, self.rate_combo.currentData())
        except Exception as exc:
            log.exception("engine start failed")
            self.engine.stop()
            QMessageBox.critical(self, "Could not start audio", str(exc))
            return False
        self.spectrum.set_fs(self.engine.fs)
        self._show_source_errors()
        failed = [f"{s.name}:\n    {s.error}" for s in self.engine.sources.values() if s.error]
        if failed:
            QMessageBox.warning(self, "Input source failed",
                                "These input sources could not be opened and are not in the mix:\n\n"
                                + "\n\n".join(failed))
        return True

    def _set_source(self, source: str) -> None:
        if source == "clip" and self.engine.clip is None and self.engine._clip_src is None:
            return
        self.engine.set_source(source)
        if not self.engine.running:
            self._start_engine()
        self._update_buttons()

    def _on_bypass(self, on: bool) -> None:
        self.engine.bypass = on
        self.bypass_btn.setStyleSheet(LIT["red"] if on else "")
        self.bypass_btn.setText("BYPASSED" if on else "BYPASS")

    def _on_volume(self, v: int) -> None:
        # slider is in dB-ish steps: 100 -> 0 dB, 0 -> silence
        self.engine.volume = 0.0 if v == 0 else 10 ** ((v - 100) * 0.5 / 20)

    # ================= record / clip =================
    def _toggle_record(self) -> None:
        if self.engine.recording:
            self._stop_record(save=True)
        else:
            if not self.engine.running and not self._start_engine():
                return
            if not self.engine.has_input:
                QMessageBox.warning(self, "Cannot record",
                                    "Nothing is switched ON in the Input mixer, so there is "
                                    "nothing to record.")
                self._update_buttons()
                return
            self.engine.set_source("live")
            self.engine.start_record()
            self._rec_t0 = time.monotonic()
        self._update_buttons()

    def _stop_record(self, save: bool) -> None:
        if not self.engine.recording:
            return
        data = self.engine.stop_record()
        if not save or len(data) < self.engine.fs // 10:
            return
        path = RECORD_DIR / time.strftime("rec_%Y%m%d_%H%M%S.wav")
        try:
            write_wav(path, data, self.engine.fs)
        except OSError as exc:
            QMessageBox.warning(self, "Recording not saved", str(exc))
        self._use_clip(data, self.engine.fs, path.name)
        # straight into looped playback, ready to be processed
        self.engine.set_source("clip")

    def _use_clip(self, data: np.ndarray, fs: int, name: str) -> None:
        self.engine.set_clip(data, fs, name)
        self.clip_label.setText(f"{name}   {len(data) / fs:.1f} s   {fs} Hz")
        self._update_buttons()

    def _open_wav(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open WAV", str(RECORD_DIR), "WAV files (*.wav)")
        if not path:
            return
        try:
            data, fs = read_wav(path)
        except Exception as exc:
            QMessageBox.warning(self, "Could not open file", str(exc))
            return
        if len(data) == 0:
            QMessageBox.warning(self, "Could not open file", "The file contains no audio.")
            return
        self._use_clip(data, fs, Path(path).name)

    def _save_processed(self) -> None:
        if self.engine._clip_src is None:
            return
        data, fs = self.engine._clip_src
        stem = Path(self.engine.clip_name).stem
        path, _ = QFileDialog.getSaveFileName(self, "Save processed clip",
                                              str(RECORD_DIR / f"{stem}_processed.wav"), "WAV files (*.wav)")
        if not path:
            return
        try:
            # at the engine's rate, so it sounds exactly like the playback
            rate = self.rate_combo.currentData()
            y = render_offline(self.chain.to_dict(), self.registry, eng.resample(data, fs, rate), rate)
            write_wav(path, y, rate)
        except Exception as exc:
            log.exception("save processed failed")
            QMessageBox.warning(self, "Could not save", str(exc))

    # ================= chain / presets =================
    def _add_block(self, cls) -> None:
        self.chain.add(cls())
        self._rebuild_panels()
        QTimer.singleShot(0, lambda: self.scroll.horizontalScrollBar().setValue(
            self.scroll.horizontalScrollBar().maximum()))

    def _rebuild_panels(self) -> None:
        while self.panel_row.count():
            item = self.panel_row.takeAt(0)
            if item.widget():
                item.widget().hide()  # deleteLater alone leaves it drawn until the loop spins
                item.widget().deleteLater()
        self._panels = []
        for b in self.chain.blocks:
            p = BlockPanel(b, self.chain)
            p.move_requested.connect(self._move_block)
            p.remove_requested.connect(self._remove_block)
            p.refresh_status()
            self.panel_row.addWidget(p)
            self._panels.append(p)
        if not self._panels:
            hint = QLabel("The chain is empty - audio passes straight through. Use “+ Add block”.")
            hint.setStyleSheet("color: #778; font-weight: normal;")
            self.panel_row.addWidget(hint)
        self.panel_row.addStretch(1)

    def _move_block(self, block, delta: int) -> None:
        self.chain.move(block, delta)
        self._rebuild_panels()

    def _remove_block(self, block) -> None:
        self.chain.remove(block)
        self._rebuild_panels()

    def _clear_chain(self) -> None:
        self.chain.clear()
        self._rebuild_panels()

    def _refresh_presets(self, select: str = "") -> None:
        self.preset_combo.clear()
        self.preset_combo.addItem("Load a preset…", None)
        for path in sorted(PRESET_DIR.glob("*.json")):
            self.preset_combo.addItem(path.stem, str(path))
        if select:
            self.preset_combo.setCurrentIndex(max(self.preset_combo.findText(select), 0))

    def _load_preset(self, index: int) -> None:
        path = self.preset_combo.itemData(index)
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not load preset", str(exc))
            return
        self._apply_chain(data)

    def _apply_chain(self, data: dict) -> None:
        missing = self.chain.load_dict(data, self.registry)
        self._rebuild_panels()
        if missing:
            QMessageBox.warning(self, "Missing blocks",
                                "These blocks are not installed and were skipped:\n\n" + "\n".join(missing))

    def _save_preset(self) -> None:
        current = self.preset_combo.currentText() if self.preset_combo.currentData() else ""
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:", text=current)
        name = "".join(c for c in name if c not in '\\/:*?"<>|').strip()
        if not ok or not name:
            return
        try:
            (PRESET_DIR / f"{name}.json").write_text(json.dumps(self.chain.to_dict(), indent=2), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Could not save preset", str(exc))
            return
        self._refresh_presets(select=name)

    def _delete_preset(self) -> None:
        path = self.preset_combo.currentData()
        if not path:
            return
        name = self.preset_combo.currentText()
        if QMessageBox.question(self, "Delete preset", f"Delete the preset “{name}”?") != QMessageBox.Yes:
            return
        try:
            Path(path).unlink()
        except OSError as exc:
            QMessageBox.warning(self, "Could not delete preset", str(exc))
        self._refresh_presets()

    # ================= periodic refresh =================
    def _update_buttons(self) -> None:
        e = self.engine
        running = e.running
        self.start_btn.setText("STOP" if running else "START")
        self.start_btn.setStyleSheet(LIT["green"] if running else "")
        has_clip = e._clip_src is not None
        self.clip_btn.setEnabled(has_clip)
        self.save_btn.setEnabled(has_clip)
        self.live_btn.setStyleSheet(LIT["blue"] if running and e.source == "live" else "")
        self.clip_btn.setStyleSheet(LIT["blue"] if running and e.source == "clip" else "")
        self.rec_btn.setStyleSheet(LIT["red"] if e.recording else "")
        if not e.recording:
            self.rec_btn.setText("● REC")

    def _tick(self) -> None:
        e = self.engine
        self.in_meter.feed(e.in_peak)
        self.out_meter.feed(e.out_peak)
        e.in_peak = e.out_peak = 0.0
        for st in self._strips:
            src = e.sources.get(st.key)
            st.meter.feed(src.peak if src is not None and e.running else 0.0)
            if src is not None:
                src.peak = 0.0

        chain_ms = self.chain.latency / self.chain.fs * 1000
        self.latency_label.setText(f"Chain delay {chain_ms:.0f} ms")
        for p in self._panels:
            if p.block.error or p.enable.isChecked() != p.block.enabled:
                p.refresh_status()

        if not e.running:
            self.status.setText("Stopped")
            return
        self.spectrum.update_taps(e.tap_in, e.tap_out)
        # a dropout is the output running dry, or a live source doing so
        dropouts = e.underruns + sum(s.gaps for s in e.sources.values())
        self.status.setText(f"DSP load {e.cpu * 100:.0f}%   dropouts {dropouts}")
        if e.recording:
            self.rec_btn.setText(f"■ {time.monotonic() - self._rec_t0:4.1f} s")
        if e.source == "clip" and e.clip is not None and len(e.clip):
            self.clip_bar.set(e.clip_pos / len(e.clip))
        else:
            self.clip_bar.set(0.0)

    # ================= settings =================
    def _load_settings(self) -> None:
        try:
            s = json.loads(SETTINGS.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            s = {}
        api = self.api_combo.findText(s.get("driver", ""))
        if api >= 0:
            self.api_combo.setCurrentIndex(api)
        self._fill_devices(s.get("output", ""))
        mixer = s.get("mixer")
        if mixer is None:
            # first run, or settings from before the mixer: one source on --
            # the input that was selected then, else Windows' default input
            name = s.get("input") or next(
                (n for i, n in eng.devices(self.api_combo.currentData(), "input")
                 if i == eng.default_device(self.api_combo.currentData(), "input")), "")
            mixer = {name: {"on": True, "level": UNITY}} if name else {}
        self._rebuild_mixer(mixer)
        rate = self.rate_combo.findData(s.get("rate"))
        if rate >= 0:
            self.rate_combo.setCurrentIndex(rate)
        self.vol.setValue(int(s.get("volume", 70)))
        self.chain.set_fs(self.rate_combo.currentData())
        self.spectrum.set_fs(self.rate_combo.currentData())
        self._apply_chain(s.get("chain", {}))

    def _save_settings(self) -> None:
        s = {
            "driver": self.api_combo.currentText(),
            "mixer": self._mixer_state(),
            "output": self.out_combo.currentText(),
            "rate": self.rate_combo.currentData(),
            "volume": self.vol.value(),
            "chain": self.chain.to_dict(),
        }
        try:
            SETTINGS.write_text(json.dumps(s, indent=2), encoding="utf-8")
        except OSError:
            log.exception("could not save settings")

    def closeEvent(self, event) -> None:
        self.timer.stop()
        self._stop_record(save=True)
        self.engine.stop()
        self._save_settings()
        super().closeEvent(event)
