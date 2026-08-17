"""Build the self-contained Kaggle notebook from the production runner."""

from __future__ import annotations

import json
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "kaggle" / "ai-enrichment" / "runner.py"
NOTEBOOK_PATH = (
    ROOT / "kaggle" / "ai-enrichment" / "footballpulse-ai-enrichment.ipynb"
)
MAIN_GUARD = '\n\nif __name__ == "__main__":\n    main()\n'
LOGGER = logging.getLogger("footballpulse.notebook_builder")


def source_lines(value: str) -> list[str]:
    """Return nbformat-compatible source lines."""

    return value.splitlines(keepends=True)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    LOGGER.info("notebook_build_started source=%s", RUNNER_PATH)
    runner = RUNNER_PATH.read_text(encoding="utf-8")
    if not runner.endswith(MAIN_GUARD):
        raise RuntimeError("runner.py does not end with the expected main guard")
    definitions = runner[: -len(MAIN_GUARD)] + "\n"
    notebook = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": source_lines(
                    "# FootballPulse AI enrichment\n\n"
                    "Notebook production để enrich các bài bóng đá tiếng Anh bằng Qwen3. "
                    "Notebook chỉ đọc input đã attach và ghi kết quả vào "
                    "`/kaggle/working`.\n\n"
                    "## Input bắt buộc\n\n"
                    "1. Dataset private: `pmv259/footballpulse-ai-batches`.\n"
                    "2. Kaggle Model: Qwen3-0.6B, framework Transformers, variation 0.6b "
                    "(attach từ model chính thức `qwen-lm/qwen-3`).\n"
                    "3. Accelerator: GPU. Internet có thể tắt vì model được mount làm input.\n\n"
                    "Chạy cell định nghĩa trước, sau đó chạy cell preflight. Khi preflight "
                    "hiện đúng manifest, articles và model path thì mới chạy cell cuối.\n"
                ),
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": source_lines(definitions),
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": source_lines(
                    "configure_runner_logging()\n"
                    "manifest_path, articles_path = find_batch_files(INPUT_ROOT)\n"
                    "model_path = find_model_path(INPUT_ROOT)\n"
                    "print(f'Manifest: {manifest_path}')\n"
                    "print(f'Articles: {articles_path}')\n"
                    "print(f'Model: {model_path}')\n"
                ),
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": source_lines(
                    "main()\n"
                    "print(f'Results: {OUTPUT_ROOT / \"results.jsonl\"}')\n"
                    "print(f'Report: {OUTPUT_ROOT / \"job-report.json\"}')\n"
                ),
            },
        ],
        "metadata": {
            "kaggle": {"accelerator": "gpu", "dataSources": [], "dockerImageVersionId": None},
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    NOTEBOOK_PATH.write_text(
        json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    LOGGER.info(
        "notebook_build_completed target=%s cell_count=%s bytes=%s",
        NOTEBOOK_PATH,
        len(notebook["cells"]),
        NOTEBOOK_PATH.stat().st_size,
    )


if __name__ == "__main__":
    main()
