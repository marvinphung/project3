from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class DiscoveryJob:
    key: str
    url: str
    allowed_domains: tuple[str, ...]

    @property
    def domain(self) -> str:
        return (urlsplit(self.url).hostname or "").lower()


@dataclass(frozen=True, slots=True)
class DiscoveryResult[T]:
    key: str
    value: T | None
    error: str | None


type Handler[T] = Callable[[DiscoveryJob], Awaitable[T]]


class DiscoveryRunner[T]:
    def __init__(
        self,
        *,
        handler: Handler[T],
        global_limit: int,
        per_domain_limit: int,
        queue_capacity: int,
    ) -> None:
        if min(global_limit, per_domain_limit, queue_capacity) < 1:
            raise ValueError("discovery limits must be positive")
        self._handler = handler
        self._global_limit = global_limit
        self._per_domain_limit = per_domain_limit
        self._queue_capacity = queue_capacity

    async def run(self, jobs: Sequence[DiscoveryJob]) -> list[DiscoveryResult[T]]:
        queue: asyncio.Queue[tuple[int, DiscoveryJob] | None] = asyncio.Queue(
            maxsize=self._queue_capacity
        )
        results: list[DiscoveryResult[T] | None] = [None] * len(jobs)
        global_semaphore = asyncio.Semaphore(self._global_limit)
        domain_semaphores: dict[str, asyncio.Semaphore] = {}

        async def produce() -> None:
            for index, job in enumerate(jobs):
                await queue.put((index, job))
            for _ in range(self._global_limit):
                await queue.put(None)

        async def consume() -> None:
            while True:
                item = await queue.get()
                try:
                    if item is None:
                        return
                    index, job = item
                    domain_semaphore = domain_semaphores.setdefault(
                        job.domain,
                        asyncio.Semaphore(self._per_domain_limit),
                    )
                    try:
                        async with global_semaphore, domain_semaphore:
                            value = await self._handler(job)
                    except Exception as exc:
                        results[index] = DiscoveryResult(job.key, None, str(exc)[:500])
                    else:
                        results[index] = DiscoveryResult(job.key, value, None)
                finally:
                    queue.task_done()

        async with asyncio.TaskGroup() as group:
            group.create_task(produce())
            for _ in range(self._global_limit):
                group.create_task(consume())

        return [result for result in results if result is not None]
