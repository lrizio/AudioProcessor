"""Audio Processor: a chain of pluggable DSP blocks between an input source
(live device or a recorded clip) and an output device."""
from __future__ import annotations

import sys
from pathlib import Path

__version__ = "1.2"

# Folder holding presets/, recordings/, settings.json and the user blocks/
# folder -- beside the .exe when frozen, the project root otherwise.
APP_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent.parent
)

# Where the files shipped with the app live: PyInstaller's per-run
# extraction folder when frozen, the project root otherwise.
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def seed_app_dir() -> None:
    """First run of the .exe in a fresh folder: put the shipped presets and
    the block template beside it, so they can be found and edited. Never
    overwrites, and a folder the user emptied on purpose stays empty."""
    import shutil

    if RESOURCE_DIR == APP_DIR:
        return
    for name in ("presets", "blocks"):
        src, dst = RESOURCE_DIR / name, APP_DIR / name
        if src.is_dir() and not dst.exists():
            try:
                shutil.copytree(src, dst)
            except OSError:
                pass  # read-only location: the app still runs, just without them
