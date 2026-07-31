import sys

import footballpulse_event_contracts


def test_workspace_uses_python_312() -> None:
    assert sys.version_info[:2] == (3, 12)


def test_event_contracts_package_is_installed() -> None:
    assert footballpulse_event_contracts.__version__ == "0.1.0"
