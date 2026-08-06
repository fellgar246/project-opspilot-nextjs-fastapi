from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

EMBEDDING_DIM = 768
DEFAULT_MODEL_NAME = "text-embedding-3-small"


class EmbeddingDimensionError(ValueError):
    """Raised when stored vectors do not match the configured embedding model."""


def pad_embedding(vector: list[float], *, dim: int = EMBEDDING_DIM) -> list[float]:
    if len(vector) == dim:
        return vector
    if len(vector) > dim:
        return vector[:dim]
    return vector + [0.0] * (dim - len(vector))


async def embed_texts_batched(
    embed_fn: Callable[[list[str]], Awaitable[list[list[float]]]],
    texts: list[str],
    *,
    batch_size: int = 16,
    concurrency: int = 2,
    expected_dim: int = EMBEDDING_DIM,
    model_name: str = DEFAULT_MODEL_NAME,
) -> list[list[float]]:
    if not texts:
        return []

    semaphore = asyncio.Semaphore(concurrency)
    results: list[list[float] | None] = [None] * len(texts)

    async def _process_batch(start: int, batch: list[str]) -> None:
        async with semaphore:
            vectors = await embed_fn(batch)
            if len(vectors) != len(batch):
                raise ValueError("embed_fn returned unexpected batch size")
            for offset, vector in enumerate(vectors):
                padded = pad_embedding(vector, dim=expected_dim)
                if len(padded) != expected_dim:
                    raise EmbeddingDimensionError(
                        f"Model {model_name} produced dimension {len(vector)}, "
                        f"expected {expected_dim}"
                    )
                results[start + offset] = padded

    tasks = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        tasks.append(asyncio.create_task(_process_batch(start, batch)))
    await asyncio.gather(*tasks)
    return [item for item in results if item is not None]
