from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from footballpulse_ai_content_service.batch.kaggle_cli import (
    KaggleCli,
    KaggleCliError,
    KaggleKernelState,
)


class RecordingRunner:
    def __init__(self, outputs: list[subprocess.CompletedProcess[str]] | None = None) -> None:
        self.calls: list[tuple[list[str], int]] = []
        self.outputs = outputs or []

    def run(self, command: list[str], *, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        self.calls.append((command, timeout_seconds))
        if self.outputs:
            return self.outputs.pop(0)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


def completed(
    stdout: str = "", stderr: str = "", returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["kaggle"], returncode, stdout=stdout, stderr=stderr)


def test_cli_uses_argument_arrays_for_dataset_kernel_and_output(tmp_path: Path) -> None:
    runner = RecordingRunner()
    cli = KaggleCli(runner=runner, command_timeout_seconds=120)

    cli.upload_dataset(tmp_path / "input", batch_id="batch-123")
    cli.submit_kernel(tmp_path / "notebook", accelerator="NvidiaTeslaP100")
    cli.download_output("owner/footballpulse-ai", tmp_path / "output")

    assert runner.calls == [
        (
            [
                "kaggle",
                "datasets",
                "version",
                "-p",
                str(tmp_path / "input"),
                "-m",
                "FootballPulse batch batch-123",
                "--dir-mode",
                "zip",
                "--quiet",
                "--ignore-patterns",
                "results.jsonl",
                "--ignore-patterns",
                "job-report.json",
            ],
            120,
        ),
        (
            [
                "kaggle",
                "kernels",
                "push",
                "-p",
                str(tmp_path / "notebook"),
                "--accelerator",
                "NvidiaTeslaP100",
                "--timeout",
                "5400",
            ],
            120,
        ),
        (
            [
                "kaggle",
                "kernels",
                "output",
                "owner/footballpulse-ai",
                "-p",
                str(tmp_path / "output"),
                "--force",
                "--quiet",
                "--file-pattern",
                "^(results\\.jsonl|job-report\\.json)$",
            ],
            120,
        ),
    ]


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("Kernel status: running", KaggleKernelState.RUNNING),
        ("Kernel status: queued", KaggleKernelState.PENDING),
        ("Kernel status: complete", KaggleKernelState.COMPLETE),
        ("Kernel status: error", KaggleKernelState.ERROR),
        ("unexpected response", KaggleKernelState.UNKNOWN),
    ],
)
def test_status_is_normalized(output: str, expected: KaggleKernelState) -> None:
    cli = KaggleCli(runner=RecordingRunner([completed(stdout=output)]))

    assert cli.kernel_status("owner/footballpulse-ai") is expected


def test_cli_failure_is_bounded_and_redacts_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAGGLE_USERNAME", "private-user")
    monkeypatch.setenv("KAGGLE_KEY", "super-secret-key")
    runner = RecordingRunner(
        [completed(stderr="private-user super-secret-key " + "x" * 3_000, returncode=1)]
    )
    cli = KaggleCli(runner=runner)

    with pytest.raises(KaggleCliError) as error:
        cli.kernel_status("owner/footballpulse-ai")

    message = str(error.value)
    assert "private-user" not in message
    assert "super-secret-key" not in message
    assert len(message) < 1_500
