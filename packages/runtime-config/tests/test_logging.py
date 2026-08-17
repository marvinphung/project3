from __future__ import annotations

import json
import logging
from io import StringIO

import pytest
from footballpulse_runtime_config.asgi import RequestLoggingMiddleware
from footballpulse_runtime_config.logging import (
    bind_log_context,
    configure_logging,
    log_event,
)


def test_structured_log_contains_stable_event_and_bound_context() -> None:
    output = StringIO()
    configure_logging(service="crawler-service", level="INFO", stream=output, force=True)

    with bind_log_context(correlation_id="request-1", batch_id="batch-1"):
        log_event(logging.getLogger("test"), "crawl_batch_started", source_count=3)

    record = json.loads(output.getvalue())
    assert record["level"] == "INFO"
    assert record["service"] == "crawler-service"
    assert record["event"] == "crawl_batch_started"
    assert record["correlation_id"] == "request-1"
    assert record["batch_id"] == "batch-1"
    assert record["source_count"] == 3
    assert record["timestamp"].endswith("Z")


def test_structured_log_redacts_nested_secrets() -> None:
    output = StringIO()
    configure_logging(service="ai-content-service", level="INFO", stream=output, force=True)

    log_event(
        logging.getLogger("test"),
        "provider_configured",
        api_token="never-print",
        settings={"password": "never-print", "model": "qwen3"},
    )

    record = json.loads(output.getvalue())
    assert record["api_token"] == "***"
    assert record["settings"] == {"password": "***", "model": "qwen3"}
    assert "never-print" not in output.getvalue()


def test_exception_log_includes_type_without_exposing_secret_message() -> None:
    output = StringIO()
    configure_logging(service="article-service", level="INFO", stream=output, force=True)

    try:
        raise RuntimeError("token=secret-value")
    except RuntimeError as error:
        log_event(logging.getLogger("test"), "article_failed", level=logging.ERROR, error=error)

    record = json.loads(output.getvalue())
    assert record["error_type"] == "RuntimeError"
    assert "secret-value" not in output.getvalue()
    assert "token=" not in output.getvalue()


def test_context_is_restored_after_binding_scope() -> None:
    output = StringIO()
    configure_logging(service="test-service", level="INFO", stream=output, force=True)

    with bind_log_context(correlation_id="temporary"):
        log_event(logging.getLogger("test"), "inside")
    log_event(logging.getLogger("test"), "outside")

    records = [json.loads(line) for line in output.getvalue().splitlines()]
    assert records[0]["correlation_id"] == "temporary"
    assert records[1]["correlation_id"] == "-"


@pytest.mark.anyio
async def test_asgi_middleware_logs_without_task_boundary_and_adds_request_id() -> None:
    output = StringIO()
    configure_logging(service="crawler-api", level="INFO", stream=output, force=True)
    sent: list[dict[str, object]] = []

    async def app(scope, receive, send):  # type: ignore[no-untyped-def]
        del scope, receive
        await send({"type": "http.response.start", "status": 201, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    middleware = RequestLoggingMiddleware(app, logger=logging.getLogger("test.http"))
    await middleware(
        {
            "type": "http",
            "method": "POST",
            "path": "/admin/v1/sources",
            "headers": [(b"x-request-id", b"request-123")],
        },
        receive,
        send,
    )

    records = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [record["event"] for record in records] == [
        "http_request_started",
        "http_request_completed",
    ]
    assert records[1]["status_code"] == 201
    assert records[1]["correlation_id"] == "request-123"
    assert sent[0]["headers"] == [(b"x-request-id", b"request-123")]
