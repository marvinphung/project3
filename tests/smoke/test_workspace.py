from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_workspace_targets_python_312() -> None:
    assert sys.version_info >= (3, 12)

    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)

    assert pyproject["project"]["requires-python"] == ">=3.12,<3.13"


def test_workspace_declares_quality_tools() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)

    assert {"pytest", "pytest-asyncio", "ruff", "mypy"} <= set(
        pyproject["dependency-groups"]["dev"]
    )
    assert pyproject["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]
    assert pyproject["tool"]["mypy"]["python_version"] == "3.12"
