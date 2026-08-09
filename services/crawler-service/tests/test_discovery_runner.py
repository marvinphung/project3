from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from footballpulse_crawler_service.discovery.runner import (
    DiscoveryJob,
    DiscoveryRunner,
)


@dataclass
class ConcurrencyProbe:
    active: int = 0
    maximum: int = 0
    domain_active: dict[str, int] | None = None
    domain_maximum: dict[str, int] | None = None

    def __post_init__(self) -> None:
        self.domain_active = {}
        self.domain_maximum = {}

    async def __call__(self, job: DiscoveryJob) -> str:
        domain = job.domain
        self.active += 1
        self.maximum = max(self.maximum, self.active)
        assert self.domain_active is not None
        assert self.domain_maximum is not None
        self.domain_active[domain] = self.domain_active.get(domain, 0) + 1
        self.domain_maximum[domain] = max(
            self.domain_maximum.get(domain, 0), self.domain_active[domain]
        )
        await asyncio.sleep(0.01)
        self.domain_active[domain] -= 1
        self.active -= 1
        if job.key == "broken":
            raise RuntimeError("source unavailable")
        return job.key


@pytest.mark.anyio
async def test_bounds_global_and_per_domain_concurrency_and_isolates_failure() -> None:
    probe = ConcurrencyProbe()
    runner: DiscoveryRunner[str] = DiscoveryRunner(
        handler=probe,
        global_limit=3,
        per_domain_limit=2,
        queue_capacity=2,
    )
    jobs = [
        DiscoveryJob(str(index), f"https://same.example.com/{index}", ("example.com",))
        for index in range(6)
    ] + [DiscoveryJob("broken", "https://other.test/feed", ("other.test",))]

    results = await runner.run(jobs)

    assert probe.maximum <= 3
    assert probe.domain_maximum == {"same.example.com": 2, "other.test": 1}
    assert len(results) == 7
    assert results[-1].error == "source unavailable"
    assert results[-1].value is None
