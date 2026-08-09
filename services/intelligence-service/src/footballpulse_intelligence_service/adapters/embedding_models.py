from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib import import_module
from threading import Lock
from typing import Protocol, cast

from footballpulse_intelligence_service.domain.embedding import (
    EMBEDDING_DIMENSIONS,
    EmbeddingVector,
)

DEFAULT_BGE_MODEL = "BAAI/bge-small-en-v1.5"
MAX_BGE_TOKENS = 512


class Tokenizer(Protocol):
    def __call__(
        self,
        texts: list[str],
        *,
        padding: bool,
        truncation: bool,
        add_special_tokens: bool,
    ) -> Mapping[str, object]: ...


class ArrayLike(Protocol):
    def tolist(self) -> object: ...


class SentenceModel(Protocol):
    tokenizer: Tokenizer
    max_seq_length: int

    def get_embedding_dimension(self) -> int | None: ...

    def encode(
        self,
        texts: list[str],
        *,
        batch_size: int,
        show_progress_bar: bool,
        convert_to_numpy: bool,
        normalize_embeddings: bool,
    ) -> ArrayLike: ...


def _load_sentence_model(model_id: str) -> SentenceModel:
    try:
        sentence_transformer = import_module("sentence_transformers").SentenceTransformer
    except (ImportError, AttributeError) as error:
        raise RuntimeError(
            "BGE runtime is unavailable; install the intelligence-service model extra"
        ) from error
    return cast(SentenceModel, sentence_transformer(model_id, device="cpu"))


@dataclass(frozen=True, slots=True)
class EncodedEmbedding:
    vector: EmbeddingVector
    token_count: int
    embedded_token_count: int
    truncated: bool


def _as_rows(value: object, *, field: str) -> list[list[object]]:
    if hasattr(value, "tolist"):
        value = cast(ArrayLike, value).tolist()
    if not isinstance(value, list) or not all(isinstance(row, list) for row in value):
        raise ValueError(f"invalid BGE {field}: expected rows")
    return cast(list[list[object]], value)


class BgeEmbeddingAdapter:
    model_name = "sentence-transformers"

    def __init__(
        self,
        *,
        model_id: str = DEFAULT_BGE_MODEL,
        model_loader: Callable[[str], SentenceModel] = _load_sentence_model,
    ) -> None:
        self.model_version = model_id
        self._model_id = model_id
        self._model_loader = model_loader
        self._model: SentenceModel | None = None
        self._load_lock = Lock()

    def _get_model(self) -> SentenceModel:
        if self._model is None:
            with self._load_lock:
                if self._model is None:
                    self._model = self._model_loader(self._model_id)
        return self._model

    def encode(
        self,
        texts: list[str],
        *,
        batch_size: int,
        max_tokens: int,
    ) -> list[EncodedEmbedding]:
        if not texts or any(not text for text in texts):
            raise ValueError("BGE input batch must contain non-empty text")
        if batch_size < 1 or not 1 <= max_tokens <= MAX_BGE_TOKENS:
            raise ValueError("BGE batch or token limit is outside the model contract")
        model = self._get_model()
        if model.get_embedding_dimension() != EMBEDDING_DIMENSIONS:
            raise ValueError("BGE model output dimension does not match contract")
        model.max_seq_length = max_tokens
        tokenized = model.tokenizer(
            texts,
            padding=False,
            truncation=False,
            add_special_tokens=True,
        )
        token_rows = _as_rows(tokenized.get("input_ids"), field="tokenizer output")
        if len(token_rows) != len(texts):
            raise ValueError("invalid BGE tokenizer output: batch size mismatch")
        raw_vectors = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        vector_rows = _as_rows(raw_vectors, field="model output")
        if len(vector_rows) != len(texts):
            raise ValueError("invalid BGE model output: batch size mismatch")

        results: list[EncodedEmbedding] = []
        for token_row, vector_row in zip(token_rows, vector_rows, strict=True):
            token_count = len(token_row)
            embedded_count = min(token_count, max_tokens)
            numeric_row: list[float] = []
            for value in vector_row:
                if not isinstance(value, int | float) or isinstance(value, bool):
                    raise ValueError("invalid BGE model output: vector values must be numeric")
                numeric_row.append(float(value))
            vector = EmbeddingVector.create(numeric_row)
            results.append(
                EncodedEmbedding(
                    vector,
                    token_count,
                    embedded_count,
                    embedded_count < token_count,
                )
            )
        return results


class MockEmbeddingAdapter:
    model_name = "mock-bge"
    model_version = "fixture-v1"

    def encode(
        self,
        texts: list[str],
        *,
        batch_size: int,
        max_tokens: int,
    ) -> list[EncodedEmbedding]:
        if batch_size < 1 or not 1 <= max_tokens <= MAX_BGE_TOKENS:
            raise ValueError("mock embedding limits are outside the model contract")
        results: list[EncodedEmbedding] = []
        for text in texts:
            if not text:
                raise ValueError("mock embedding input must not be empty")
            digest = hashlib.shake_256(text.encode("utf-8")).digest(EMBEDDING_DIMENSIONS * 2)
            raw = [
                int.from_bytes(digest[index : index + 2], "big") / 32767.5 - 1.0
                for index in range(0, len(digest), 2)
            ]
            norm = math.sqrt(math.fsum(value * value for value in raw))
            vector = EmbeddingVector.create([value / norm for value in raw])
            token_count = len(text.split()) + 2
            embedded_count = min(token_count, max_tokens)
            results.append(
                EncodedEmbedding(
                    vector,
                    token_count,
                    embedded_count,
                    embedded_count < token_count,
                )
            )
        return results
