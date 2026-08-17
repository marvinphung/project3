from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from pymongo import ASCENDING, IndexModel
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from footballpulse_ai_content_service.batch.coordinator import (
    EnrichmentPersistenceConflict,
    EnrichmentPersistenceUnavailable,
    GroundedEnrichment,
)
from footballpulse_ai_content_service.batch.domain import AiBatchJob, AiBatchStatus

MongoDocument = dict[str, object]


class ConcurrentBatchUpdate(RuntimeError):
    pass


class MongoBatchJobRepository:
    _LEASE_ID = "kaggle-single-flight"

    def __init__(self, database: Database[MongoDocument]) -> None:
        self._jobs = database.get_collection("ai_batch_jobs")
        self._leases = database.get_collection("ai_batch_locks")

    def ensure_indexes(self) -> None:
        self._jobs.create_indexes(
            [
                IndexModel([("status", ASCENDING), ("updated_at", ASCENDING)]),
                IndexModel([("created_at", ASCENDING)]),
            ]
        )
        self._leases.create_index("expires_at", expireAfterSeconds=0)

    def create(self, job: AiBatchJob) -> None:
        document = job.model_dump(mode="python")
        document["_id"] = str(job.batch_id)
        document["batch_id"] = str(job.batch_id)
        document["status"] = job.status.value
        self._jobs.insert_one(document)

    def get_status(self, batch_id: UUID) -> AiBatchStatus:
        try:
            document = self._jobs.find_one({"_id": str(batch_id)}, {"status": 1})
        except PyMongoError as error:
            raise EnrichmentPersistenceUnavailable("MongoDB batch read failed") from error
        if document is None:
            raise EnrichmentPersistenceUnavailable(f"AI batch {batch_id} was not found")
        try:
            return AiBatchStatus(str(document["status"]))
        except (KeyError, ValueError) as error:
            raise EnrichmentPersistenceConflict("AI batch has an invalid durable status") from error

    def acquire_lease(self, *, owner: str, now: datetime, lease_seconds: int) -> bool:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        try:
            result = self._leases.update_one(
                {
                    "_id": self._LEASE_ID,
                    "$or": [{"expires_at": {"$lte": now}}, {"owner": owner}],
                },
                {
                    "$set": {
                        "owner": owner,
                        "acquired_at": now,
                        "expires_at": now + timedelta(seconds=lease_seconds),
                    }
                },
                upsert=True,
            )
        except DuplicateKeyError:
            return False
        return result.matched_count == 1 or result.upserted_id is not None

    def transition(
        self,
        batch_id: UUID,
        *,
        expected: AiBatchStatus,
        target: AiBatchStatus,
        now: datetime,
        success_count: int | None = None,
        error_count: int | None = None,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> None:
        values: MongoDocument = {
            "status": target.value,
            "updated_at": now,
            "error_code": error_code,
            "error_detail": error_detail,
        }
        if success_count is not None:
            values["success_count"] = success_count
        if error_count is not None:
            values["error_count"] = error_count
        update: MongoDocument = {"$set": values}
        if target is AiBatchStatus.FAILED_RETRYABLE:
            update["$inc"] = {"retry_count": 1}
        result = self._jobs.update_one(
            {"_id": str(batch_id), "status": expected.value},
            update,
        )
        if result.modified_count != 1:
            raise ConcurrentBatchUpdate(
                f"batch {batch_id} did not transition from {expected} to {target}"
            )

    def release_lease(self, *, owner: str) -> None:
        self._leases.delete_one({"_id": self._LEASE_ID, "owner": owner})


class MongoEnrichmentResultSink:
    def __init__(self, database: Database[MongoDocument]) -> None:
        self._collection = database.get_collection("article_enrichments")

    def ensure_indexes(self) -> None:
        indexes = self._collection.index_information()
        desired_keys = [
            ("article_version_id", ASCENDING),
            ("input_hash", ASCENDING),
            ("model_version", ASCENDING),
            ("prompt_version", ASCENDING),
        ]
        for old_name in ("article_version_id_1_input_hash_1", "uq_article_enrichments_run"):
            existing = indexes.get(old_name)
            if existing is not None and list(existing["key"]) != desired_keys:
                self._collection.drop_index(old_name)
        self._collection.create_index(
            desired_keys,
            unique=True,
            name="uq_article_enrichments_run",
        )

    def persist(self, outputs: tuple[GroundedEnrichment, ...]) -> None:
        for grounded in outputs:
            output = grounded.output
            identity = (
                f"{output.article_version_id}:{output.input_hash}:"
                f"{output.model_version}:{output.prompt_version}"
            )
            validation = grounded.validation
            payload: MongoDocument = {
                **output.model_dump(mode="json"),
                "validation_status": validation.status.value,
                "valid_claims": [
                    claim.model_dump(mode="json") for claim in validation.valid_claims
                ],
                "rejected_claims": [
                    {
                        "index": rejected.index,
                        "claim": rejected.claim.model_dump(mode="json"),
                        "codes": [code.value for code in rejected.codes],
                    }
                    for rejected in validation.rejected_claims
                ],
                "validated_summary_en": validation.summary_en,
                "top_level_errors": list(validation.top_level_errors),
                "validated_at": grounded.validated_at.isoformat(),
            }
            document: MongoDocument = {"_id": identity, **payload}
            try:
                self._collection.insert_one(document)
            except DuplicateKeyError:
                existing = self._find_existing(identity)
                existing.pop("validated_at", None)
                comparable_payload = dict(payload)
                comparable_payload.pop("validated_at", None)
                if existing != comparable_payload:
                    raise EnrichmentPersistenceConflict(
                        "different enrichment output already exists for article input"
                    ) from None
            except PyMongoError as error:
                raise EnrichmentPersistenceUnavailable("MongoDB enrichment write failed") from error

    def _find_existing(self, identity: str) -> MongoDocument:
        try:
            existing = self._collection.find_one({"_id": identity})
        except PyMongoError as error:
            raise EnrichmentPersistenceUnavailable("MongoDB enrichment read failed") from error
        if existing is None:
            raise EnrichmentPersistenceUnavailable(
                "enrichment identity disappeared after duplicate write"
            )
        existing.pop("_id", None)
        return existing
