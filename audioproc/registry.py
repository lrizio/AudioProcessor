"""Finds the available block classes: the built-in ones in
`audioproc/blocks/` plus any .py file dropped into the user `blocks/` folder
beside the app. Files whose name starts with an underscore are helpers, not
blocks, and are skipped."""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
import pkgutil
from pathlib import Path

from .block import Block, FrameBlock

log = logging.getLogger("audioproc.registry")

CATEGORY_ORDER = ["Filters", "Adaptive", "Spectral", "Dynamics", "Tone"]


def _blocks_in(module) -> list[type]:
    return [
        cls for _, cls in inspect.getmembers(module, inspect.isclass)
        if issubclass(cls, Block) and cls not in (Block, FrameBlock)
        and cls.__module__ == module.__name__
    ]


def discover(user_dirs: list[Path] | None = None) -> tuple[dict[str, type], list[str]]:
    """Returns ({class name: class}, [load error messages])."""
    found: dict[str, type] = {}
    errors: list[str] = []

    from . import blocks as builtin
    for info in pkgutil.iter_modules(builtin.__path__):
        if info.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"{builtin.__name__}.{info.name}")
            for cls in _blocks_in(mod):
                found[cls.__name__] = cls
        except Exception as exc:
            log.exception("built-in block %s failed to load", info.name)
            errors.append(f"{info.name}.py: {type(exc).__name__}: {exc}")

    for folder in user_dirs or []:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.py")):
            if path.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(f"userblocks_{path.stem}", path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                for cls in _blocks_in(mod):
                    found[cls.__name__] = cls
            except Exception as exc:
                log.exception("user block %s failed to load", path.name)
                errors.append(f"{path.name}: {type(exc).__name__}: {exc}")
    return found, errors


def by_category(registry: dict[str, type]) -> list[tuple[str, list[type]]]:
    cats: dict[str, list[type]] = {}
    for cls in registry.values():
        cats.setdefault(cls.category, []).append(cls)
    order = CATEGORY_ORDER + sorted(c for c in cats if c not in CATEGORY_ORDER)
    return [(c, sorted(cats[c], key=lambda k: k.name)) for c in order if c in cats]
