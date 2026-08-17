from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def _load_runner() -> ModuleType:
    path = ROOT / "scripts" / "run-real-crawl.py"
    spec = importlib.util.spec_from_file_location("footballpulse_real_crawl", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_reuters_is_opt_in_but_remains_explicitly_selectable() -> None:
    runner = _load_runner()

    default_names = {source.name for source in runner.select_sources(None)}
    explicit_names = {source.name for source in runner.select_sources(["Reuters Soccer"])}

    assert "Reuters Soccer" not in default_names
    assert explicit_names == {"Reuters Soccer"}
