from __future__ import annotations

from footballpulse_intelligence_service.adapters.embedding_models import (
    BgeEmbeddingAdapter,
    MockEmbeddingAdapter,
)
from footballpulse_intelligence_service.domain.embedding import EMBEDDING_DIMENSIONS


class FakeArray:
    def __init__(self, rows: list[list[float]]) -> None:
        self._rows = rows

    def tolist(self) -> list[list[float]]:
        return self._rows


class FakeTokenizer:
    def __call__(
        self,
        texts: list[str],
        *,
        padding: bool,
        truncation: bool,
        add_special_tokens: bool,
    ) -> dict[str, list[list[int]]]:
        assert padding is False
        assert truncation is False
        assert add_special_tokens is True
        return {"input_ids": [[101, *range(len(text.split())), 102] for text in texts]}


class FakeSentenceModel:
    def __init__(self) -> None:
        self.tokenizer = FakeTokenizer()
        self.max_seq_length = 128
        self.calls: list[tuple[list[str], int, bool]] = []

    def get_embedding_dimension(self) -> int:
        return EMBEDDING_DIMENSIONS

    def encode(
        self,
        texts: list[str],
        *,
        batch_size: int,
        show_progress_bar: bool,
        convert_to_numpy: bool,
        normalize_embeddings: bool,
    ) -> FakeArray:
        assert show_progress_bar is False
        assert convert_to_numpy is True
        self.calls.append((texts, batch_size, normalize_embeddings))
        return FakeArray([[1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1) for _ in texts])


def test_bge_adapter_loads_once_and_uses_approved_runtime_contract() -> None:
    model = FakeSentenceModel()
    load_count = 0

    def loader(model_id: str) -> FakeSentenceModel:
        nonlocal load_count
        load_count += 1
        assert model_id == "BAAI/bge-small-en-v1.5"
        return model

    adapter = BgeEmbeddingAdapter(model_loader=loader)
    first = adapter.encode(["one two three"], batch_size=16, max_tokens=512)
    second = adapter.encode(["another input"], batch_size=8, max_tokens=512)

    assert load_count == 1
    assert model.max_seq_length == 512
    assert model.calls[0][1:] == (16, True)
    assert first[0].token_count == 5
    assert first[0].embedded_token_count == 5
    assert first[0].truncated is False
    assert second[0].vector.values[0] == 1.0


def test_bge_adapter_reports_token_truncation() -> None:
    adapter = BgeEmbeddingAdapter(model_loader=lambda model_id: FakeSentenceModel())

    result = adapter.encode([" ".join(["word"] * 600)], batch_size=16, max_tokens=512)

    assert result[0].token_count == 602
    assert result[0].embedded_token_count == 512
    assert result[0].truncated is True


def test_mock_embedding_is_deterministic_normalized_and_input_sensitive() -> None:
    adapter = MockEmbeddingAdapter()

    first = adapter.encode(["Arsenal transfer"], batch_size=16, max_tokens=512)[0]
    replay = adapter.encode(["Arsenal transfer"], batch_size=16, max_tokens=512)[0]
    different = adapter.encode(["Arsenal injury"], batch_size=16, max_tokens=512)[0]

    assert first == replay
    assert first.vector != different.vector
    assert len(first.vector.values) == EMBEDDING_DIMENSIONS


def test_embedding_adapter_rejects_context_beyond_model_contract() -> None:
    try:
        MockEmbeddingAdapter().encode(["Article"], batch_size=16, max_tokens=513)
    except ValueError as error:
        assert "contract" in str(error)
    else:
        raise AssertionError("BGE context must not exceed 512 tokens")
