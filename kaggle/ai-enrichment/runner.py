"""FootballPulse Kaggle Qwen batch runner.

The script intentionally has no FootballPulse package dependency: Kaggle executes
it with an attached private batch dataset and a pinned model input.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

INPUT_ROOT = Path("/kaggle/input")
OUTPUT_ROOT = Path("/kaggle/working")
PROMPT_VERSION = "article-enrichment-v1"
MAX_NEW_TOKENS = 2_500
MAX_INPUT_TOKENS = 24_576
MAX_CHUNK_WORDS = 1_200
CHUNK_OVERLAP_WORDS = 150
REQUIRED_RESULT_FIELDS = frozenset({"event_type", "summary_en", "claims"})
LOGGER = logging.getLogger("footballpulse.kaggle.runner")


def configure_runner_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
        force=True,
    )


def log_progress(event: str, **fields: object) -> None:
    detail = " ".join(f"{name}={value}" for name, value in fields.items())
    LOGGER.info("%s%s", event, f" {detail}" if detail else "")


def utc_now() -> datetime:
    return datetime.now(UTC)


def find_batch_files(root: Path) -> tuple[Path, Path]:
    log_progress("input_batch_search_started", root=root)
    candidates = [
        (manifest, manifest.with_name("articles.jsonl"))
        for manifest in root.rglob("manifest.json")
        if manifest.with_name("articles.jsonl").is_file()
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"expected exactly one batch dataset, found {len(candidates)}")
    log_progress(
        "input_batch_found",
        manifest=candidates[0][0],
        articles=candidates[0][1],
    )
    return candidates[0]


def find_model_path(root: Path) -> Path:
    log_progress("model_search_started", root=root)
    candidates: list[Path] = []
    for config_path in root.glob("**/config.json"):
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(config.get("model_type", "")).casefold().startswith("qwen3"):
            candidates.append(config_path.parent)
    unique = sorted(set(candidates))
    if len(unique) != 1:
        raise RuntimeError(f"expected exactly one Qwen3 model input, found {len(unique)}")
    log_progress("model_found", path=unique[0])
    return unique[0]


def parse_model_json(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^\s*```(?:json)?|```\s*$", "", text.strip(), flags=re.IGNORECASE)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("model did not return a JSON object") from None
        value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict) or not value.keys() >= REQUIRED_RESULT_FIELDS:
        raise ValueError("model JSON is missing required result fields")
    if not isinstance(value["summary_en"], str) or not value["summary_en"].strip():
        raise ValueError("model summary_en must be non-empty")
    if not isinstance(value["claims"], list):
        raise ValueError("model claims must be a list")
    return value


def content_chunks(
    content: str,
    *,
    max_words: int = MAX_CHUNK_WORDS,
    overlap_words: int = CHUNK_OVERLAP_WORDS,
) -> list[tuple[int, str]]:
    if max_words < 1 or overlap_words < 0 or overlap_words >= max_words:
        raise ValueError("invalid chunk limits")
    words = list(re.finditer(r"\S+", content))
    chunks: list[tuple[int, str]] = []
    first = 0
    while first < len(words):
        last = min(first + max_words, len(words))
        start = words[first].start()
        end = words[last - 1].end()
        chunks.append((start, content[start:end]))
        if len(chunks) > 64:
            raise ValueError("article requires more than 64 model chunks")
        if last == len(words):
            break
        first = last - overlap_words
    return chunks


def prompt_for(article: dict[str, Any], *, repair_text: str | None = None) -> str:
    contract = {
        "event_type": "TRANSFER|CONTRACT|INJURY|MATCH|MANAGERIAL|DISCIPLINARY|OTHER",
        "summary_en": "grounded English summary",
        "claims": [
            {
                "subject_entity_id": "UUID from canonical_entities",
                "predicate": "one allowed article-enrichment.v1 predicate",
                "object_entity_id": "UUID or null",
                "object_text": "text or null; exactly one object form",
                "qualifiers": {
                    "amount": None,
                    "currency": None,
                    "date": None,
                    "injury": None,
                    "score": None,
                },
                "certainty": "RUMOR|REPORTED|CONFIRMED|DENIED",
                "evidence_quote": "exact substring of cleaned_content",
                "evidence_start": 0,
                "evidence_end": 1,
            }
        ],
    }
    repair = (
        "\nYour previous output was invalid. Return one corrected JSON object only:\n"
        + repair_text[:4_000]
        if repair_text
        else ""
    )
    return (
        "Extract only facts supported by the English article. Never invent entities, numbers, "
        "dates, scores, or certainty. Evidence offsets use Python character indexes into "
        "cleaned_content. Return JSON only.\nSchema:\n"
        + json.dumps(contract, ensure_ascii=False)
        + "\nInput:\n"
        + json.dumps(article, ensure_ascii=False)
        + repair
    )


def load_model(model_path: Path) -> tuple[Any, Any]:
    from transformers import AutoModelForCausalLM, AutoTokenizer

    started = time.monotonic()
    log_progress("tokenizer_loading", model_path=model_path)
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    log_progress("model_loading", model_path=model_path)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        device_map="auto",
        torch_dtype="auto",
        local_files_only=True,
    )
    model.eval()
    log_progress("model_ready", duration_seconds=round(time.monotonic() - started, 2))
    return tokenizer, model


def generate(tokenizer: Any, model: Any, prompt: str) -> str:
    messages = [
        {"role": "system", "content": "You are a strict football fact extraction engine."},
        {"role": "user", "content": prompt},
    ]
    rendered = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    inputs = tokenizer(
        rendered,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_INPUT_TOKENS,
    ).to(model.device)
    generated = model.generate(
        **inputs,
        max_new_tokens=MAX_NEW_TOKENS,
        do_sample=False,
    )
    prompt_tokens = inputs["input_ids"].shape[1]
    return tokenizer.decode(generated[0][prompt_tokens:], skip_special_tokens=True)


def extract_chunk(tokenizer: Any, model: Any, article: dict[str, Any]) -> dict[str, Any]:
    raw = generate(tokenizer, model, prompt_for(article))
    try:
        return parse_model_json(raw)
    except (ValueError, json.JSONDecodeError):
        repaired = generate(tokenizer, model, prompt_for(article, repair_text=raw))
        return parse_model_json(repaired)


def process_article(
    tokenizer: Any,
    model: Any,
    article: dict[str, Any],
    *,
    model_version: str,
    prompt_version: str,
) -> dict[str, Any]:
    extracted_chunks: list[dict[str, Any]] = []
    global_claims: list[dict[str, Any]] = []
    chunks = content_chunks(article["cleaned_content"])
    log_progress(
        "article_chunking_completed",
        article_version_id=article["article_version_id"],
        chunk_count=len(chunks),
    )
    for chunk_number, (start, chunk_text) in enumerate(chunks, start=1):
        chunk_started = time.monotonic()
        log_progress(
            "article_chunk_started",
            article_version_id=article["article_version_id"],
            chunk_number=chunk_number,
            chunk_total=len(chunks),
        )
        end = start + len(chunk_text)
        chunk_mentions = [
            {
                **mention,
                "start": mention["start"] - start,
                "end": mention["end"] - start,
            }
            for mention in article.get("unresolved_mentions", [])
            if mention["start"] >= start and mention["end"] <= end
        ]
        chunk_article = {
            **article,
            "cleaned_content": chunk_text,
            "unresolved_mentions": chunk_mentions,
        }
        extracted = extract_chunk(tokenizer, model, chunk_article)
        log_progress(
            "article_chunk_completed",
            article_version_id=article["article_version_id"],
            chunk_number=chunk_number,
            claims=len(extracted["claims"]),
            duration_seconds=round(time.monotonic() - chunk_started, 2),
        )
        extracted_chunks.append(extracted)
        for claim_value in extracted["claims"]:
            if not isinstance(claim_value, dict):
                raise ValueError("model claim must be an object")
            claim = dict(claim_value)
            local_start = claim.get("evidence_start")
            local_end = claim.get("evidence_end")
            quote = claim.get("evidence_quote")
            if not isinstance(local_start, int) or not isinstance(local_end, int):
                raise ValueError("claim evidence offsets must be integers")
            if not isinstance(quote, str) or chunk_text[local_start:local_end] != quote:
                raise ValueError("claim evidence does not match chunk offsets")
            claim["evidence_start"] = start + local_start
            claim["evidence_end"] = start + local_end
            global_claims.append(claim)

    if not extracted_chunks:
        raise ValueError("article content has no words")
    event_counts = Counter(str(item["event_type"]) for item in extracted_chunks)
    event_type = max(event_counts, key=lambda value: event_counts[value])
    summaries = list(dict.fromkeys(str(item["summary_en"]).strip() for item in extracted_chunks))
    summary = " ".join(summaries)
    if len(summary) > 4_000 or len(global_claims) > 500:
        raise ValueError("combined model output exceeds contract bounds")

    result = {
        "contract_version": "article-enrichment.v1",
        "article_version_id": article["article_version_id"],
        "input_hash": article["input_hash"],
        "event_type": event_type,
        "summary_en": summary,
        "claims": global_claims,
        "model_version": model_version,
        "prompt_version": prompt_version,
    }
    return {
        "article_version_id": article["article_version_id"],
        "status": "SUCCESS",
        "result": result,
    }


def error_record(article: dict[str, Any], error: Exception) -> dict[str, Any]:
    return {
        "article_version_id": article.get("article_version_id"),
        "input_hash": article.get("input_hash"),
        "status": "ERROR",
        "error_code": type(error).__name__.upper()[:80],
        "error": " ".join(str(error).split())[:500] or "unknown model error",
    }


def main() -> None:
    configure_runner_logging()
    started_at = utc_now()
    run_started = time.monotonic()
    log_progress("enrichment_run_started", input_root=INPUT_ROOT, output_root=OUTPUT_ROOT)
    manifest_path, articles_path = find_batch_files(INPUT_ROOT)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    articles_sha256 = hashlib.sha256(articles_path.read_bytes()).hexdigest()
    if articles_sha256 != manifest["articles_sha256"]:
        raise RuntimeError("articles.jsonl checksum does not match manifest")
    model_path = find_model_path(INPUT_ROOT)
    tokenizer, model = load_model(model_path)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    success_count = 0
    error_count = 0
    with (
        articles_path.open(encoding="utf-8") as source,
        (OUTPUT_ROOT / "results.jsonl").open("w", encoding="utf-8") as destination,
    ):
        for article_number, line in enumerate(source, start=1):
            article = json.loads(line)
            article_started = time.monotonic()
            log_progress(
                "article_started",
                article_number=article_number,
                article_total=manifest["article_count"],
                article_version_id=article.get("article_version_id"),
            )
            try:
                record = process_article(
                    tokenizer,
                    model,
                    article,
                    model_version=manifest["model_version"],
                    prompt_version=manifest["prompt_version"],
                )
                success_count += 1
                log_progress(
                    "article_completed",
                    article_number=article_number,
                    article_total=manifest["article_count"],
                    article_version_id=article.get("article_version_id"),
                    claim_count=len(record["result"]["claims"]),
                    duration_seconds=round(time.monotonic() - article_started, 2),
                )
            except Exception as error:  # noqa: BLE001 - one bad article must not abort the batch
                record = error_record(article, error)
                error_count += 1
                LOGGER.exception(
                    "article_failed article_number=%s article_total=%s article_version_id=%s "
                    "error_type=%s duration_seconds=%s",
                    article_number,
                    manifest["article_count"],
                    article.get("article_version_id"),
                    type(error).__name__,
                    round(time.monotonic() - article_started, 2),
                )
            destination.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            destination.flush()

    report = {
        "contract_version": "ai-job-report.v1",
        "batch_id": manifest["batch_id"],
        "articles_sha256": articles_sha256,
        "model_version": manifest["model_version"],
        "prompt_version": manifest["prompt_version"],
        "success_count": success_count,
        "error_count": error_count,
        "started_at": started_at.isoformat(),
        "finished_at": utc_now().isoformat(),
    }
    (OUTPUT_ROOT / "job-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    log_progress(
        "enrichment_run_completed",
        article_count=manifest["article_count"],
        success_count=success_count,
        error_count=error_count,
        duration_seconds=round(time.monotonic() - run_started, 2),
        results_path=OUTPUT_ROOT / "results.jsonl",
        report_path=OUTPUT_ROOT / "job-report.json",
    )


if __name__ == "__main__":
    main()
