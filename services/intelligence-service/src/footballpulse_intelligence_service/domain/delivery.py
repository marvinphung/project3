from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


def _aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value


def _required_text(value: str, field: str, *, max_length: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > max_length:
        raise ValueError(f"{field} must contain 1 to {max_length} characters")
    return normalized


@dataclass(frozen=True, slots=True)
class ProcessedEvent:
    id: UUID
    consumer_name: str
    event_id: UUID
    event_type: str
    processed_at: datetime

    @classmethod
    def create(
        cls,
        *,
        record_id: UUID,
        consumer_name: str,
        event_id: UUID,
        event_type: str,
        processed_at: datetime,
    ) -> ProcessedEvent:
        return cls(
            record_id,
            _required_text(consumer_name, "consumer_name", max_length=100),
            event_id,
            _required_text(event_type, "event_type", max_length=100),
            _aware(processed_at, "processed_at"),
        )


class OutboxStatus(StrEnum):
    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class OutboxEvent:
    id: UUID
    aggregate_type: str
    aggregate_id: UUID
    event_type: str
    deduplication_key: str
    payload: dict[str, object]
    status: OutboxStatus
    attempt_count: int
    available_at: datetime
    published_at: datetime | None
    last_error: str | None
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        event_id: UUID,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        deduplication_key: str,
        payload: dict[str, object],
        now: datetime,
    ) -> OutboxEvent:
        normalized_payload = dict(payload)
        try:
            encoded = json.dumps(normalized_payload, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as error:
            raise ValueError("outbox payload must be JSON serializable") from error
        if len(encoded.encode("utf-8")) > 64 * 1024:
            raise ValueError("outbox payload exceeds 64 KiB")
        timestamp = _aware(now, "outbox timestamp")
        return cls(
            event_id,
            _required_text(aggregate_type, "aggregate_type", max_length=64),
            aggregate_id,
            _required_text(event_type, "event_type", max_length=100),
            _required_text(deduplication_key, "deduplication_key", max_length=200),
            normalized_payload,
            OutboxStatus.PENDING,
            0,
            timestamp,
            None,
            None,
            timestamp,
        )
