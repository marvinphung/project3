import pytest
from footballpulse_runtime_config import RuntimeSettings, diagnostic_environment


def test_runtime_settings_have_safe_local_defaults() -> None:
    settings = RuntimeSettings.from_environment({})

    assert settings.environment == "local"
    assert settings.log_level == "INFO"
    assert settings.timezone == "Asia/Ho_Chi_Minh"


def test_runtime_settings_parse_namespaced_environment() -> None:
    settings = RuntimeSettings.from_environment(
        {
            "FOOTBALLPULSE_ENV": "test",
            "FOOTBALLPULSE_LOG_LEVEL": "debug",
            "FOOTBALLPULSE_TIMEZONE": "UTC",
        }
    )

    assert settings.environment == "test"
    assert settings.log_level == "DEBUG"
    assert settings.timezone == "UTC"


def test_runtime_settings_reject_an_unknown_log_level() -> None:
    with pytest.raises(ValueError, match="FOOTBALLPULSE_LOG_LEVEL"):
        RuntimeSettings.from_environment({"FOOTBALLPULSE_LOG_LEVEL": "verbose"})


def test_diagnostics_only_include_namespaced_values_and_mask_secrets() -> None:
    diagnostics = diagnostic_environment(
        {
            "FOOTBALLPULSE_ENV": "local",
            "FOOTBALLPULSE_API_TOKEN": "do-not-print-this",
            "FOOTBALLPULSE_SIGNING_KEY": "also-secret",
            "HOME": "/not/part/of/diagnostics",
        }
    )

    assert diagnostics == {
        "FOOTBALLPULSE_API_TOKEN": "***",
        "FOOTBALLPULSE_ENV": "local",
        "FOOTBALLPULSE_SIGNING_KEY": "***",
    }
