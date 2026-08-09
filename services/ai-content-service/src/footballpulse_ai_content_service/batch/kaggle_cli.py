from __future__ import annotations

import os
import re
import subprocess
from enum import StrEnum
from pathlib import Path
from typing import Protocol


class KaggleCliError(RuntimeError):
    """A bounded, credential-redacted Kaggle CLI failure."""

    def __init__(self, message: str, *, kind: KaggleFailureKind | None = None) -> None:
        super().__init__(message)
        self.kind = kind or KaggleFailureKind.UNKNOWN


class KaggleFailureKind(StrEnum):
    NETWORK_UNAVAILABLE = "KAGGLE_NETWORK_UNAVAILABLE"
    SERVICE_UNAVAILABLE = "KAGGLE_SERVICE_UNAVAILABLE"
    QUOTA_EXHAUSTED = "KAGGLE_QUOTA_EXHAUSTED"
    GPU_UNAVAILABLE = "KAGGLE_GPU_UNAVAILABLE"
    CREDENTIAL_INVALID = "KAGGLE_CREDENTIAL_INVALID"
    UNKNOWN = "KAGGLE_FAILURE_UNKNOWN"


class KaggleKernelState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class CommandRunner(Protocol):
    def run(
        self,
        command: list[str],
        *,
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]: ...


class SubprocessCommandRunner:
    def run(
        self,
        command: list[str],
        *,
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )


class KaggleCli:
    _SLUG = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")
    _ACCELERATOR = re.compile(r"^[a-zA-Z0-9]+$")

    def __init__(
        self,
        *,
        runner: CommandRunner | None = None,
        command_timeout_seconds: int = 120,
        kernel_timeout_seconds: int = 5_400,
    ) -> None:
        if command_timeout_seconds <= 0 or kernel_timeout_seconds <= 0:
            raise ValueError("timeouts must be positive")
        self._runner = runner or SubprocessCommandRunner()
        self._command_timeout_seconds = command_timeout_seconds
        self._kernel_timeout_seconds = kernel_timeout_seconds

    def upload_dataset(self, dataset_path: Path, *, batch_id: str) -> None:
        self._execute(
            [
                "kaggle",
                "datasets",
                "version",
                "-p",
                str(dataset_path),
                "-m",
                f"FootballPulse batch {batch_id}",
                "--dir-mode",
                "zip",
                "--quiet",
                "--ignore-patterns",
                "results.jsonl",
                "--ignore-patterns",
                "job-report.json",
            ]
        )

    def submit_kernel(self, kernel_path: Path, *, accelerator: str) -> None:
        if self._ACCELERATOR.fullmatch(accelerator) is None:
            raise ValueError("invalid Kaggle accelerator")
        self._execute(
            [
                "kaggle",
                "kernels",
                "push",
                "-p",
                str(kernel_path),
                "--accelerator",
                accelerator,
                "--timeout",
                str(self._kernel_timeout_seconds),
            ]
        )

    def kernel_status(self, kernel_slug: str) -> KaggleKernelState:
        self._validate_slug(kernel_slug)
        result = self._execute(["kaggle", "kernels", "status", kernel_slug])
        output = result.stdout.casefold()
        if "complete" in output:
            return KaggleKernelState.COMPLETE
        if "error" in output or "failed" in output or "cancel" in output:
            return KaggleKernelState.ERROR
        if "running" in output:
            return KaggleKernelState.RUNNING
        if "queued" in output or "pending" in output:
            return KaggleKernelState.PENDING
        return KaggleKernelState.UNKNOWN

    def download_output(self, kernel_slug: str, output_path: Path) -> None:
        self._validate_slug(kernel_slug)
        output_path.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._execute(
            [
                "kaggle",
                "kernels",
                "output",
                kernel_slug,
                "-p",
                str(output_path),
                "--force",
                "--quiet",
                "--file-pattern",
                r"^(results\.jsonl|job-report\.json)$",
            ]
        )

    def _execute(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            result = self._runner.run(command, timeout_seconds=self._command_timeout_seconds)
        except FileNotFoundError as error:
            raise KaggleCliError(
                self._redact(f"Kaggle CLI unavailable: {error}"),
                kind=KaggleFailureKind.UNKNOWN,
            ) from error
        except subprocess.TimeoutExpired as error:
            raise KaggleCliError(
                self._redact(f"Kaggle CLI timed out: {error}"),
                kind=KaggleFailureKind.SERVICE_UNAVAILABLE,
            ) from error
        except OSError as error:
            raise KaggleCliError(
                self._redact(f"Kaggle CLI unavailable: {error}"),
                kind=KaggleFailureKind.NETWORK_UNAVAILABLE,
            ) from error
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
            raise KaggleCliError(
                self._redact(f"Kaggle CLI failed: {detail}"),
                kind=self._classify_failure(detail),
            )
        return result

    @classmethod
    def _validate_slug(cls, slug: str) -> None:
        if cls._SLUG.fullmatch(slug) is None:
            raise ValueError("invalid Kaggle owner/resource slug")

    @staticmethod
    def _redact(message: str) -> str:
        bounded = message[:1_024]
        for variable in ("KAGGLE_USERNAME", "KAGGLE_API_TOKEN", "KAGGLE_KEY"):
            secret = os.environ.get(variable)
            if secret:
                bounded = bounded.replace(secret, "[REDACTED]")
        return bounded

    @staticmethod
    def _classify_failure(detail: str) -> KaggleFailureKind:
        normalized = detail.casefold()
        if any(
            marker in normalized for marker in ("unauthorized", "forbidden", "credential", "auth")
        ):
            return KaggleFailureKind.CREDENTIAL_INVALID
        if any(marker in normalized for marker in ("quota", "limit exceeded")):
            return KaggleFailureKind.QUOTA_EXHAUSTED
        if any(marker in normalized for marker in ("gpu unavailable", "accelerator unavailable")):
            return KaggleFailureKind.GPU_UNAVAILABLE
        if any(
            marker in normalized for marker in ("network", "connection", "timed out", "timeout")
        ):
            return KaggleFailureKind.NETWORK_UNAVAILABLE
        if any(marker in normalized for marker in ("service unavailable", "internal server error")):
            return KaggleFailureKind.SERVICE_UNAVAILABLE
        return KaggleFailureKind.UNKNOWN
