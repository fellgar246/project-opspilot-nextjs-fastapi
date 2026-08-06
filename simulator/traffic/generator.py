#!/usr/bin/env python3
"""Configurable synthetic traffic generator for demo-service."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import random
import signal
import time

import httpx

DEFAULT_MIX = {
    "/catalog": 0.4,
    "/checkout": 0.3,
    "/orders/{id}": 0.25,
    "/health": 0.05,
}


class TrafficGenerator:
    def __init__(self, base_url: str, rps: float, mix: dict[str, float]) -> None:
        self.base_url = base_url.rstrip("/")
        self.rps = rps
        self.mix = mix
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    def _pick_endpoint(self) -> str:
        roll = random.random()
        acc = 0.0
        for endpoint, weight in self.mix.items():
            acc += weight
            if roll <= acc:
                return endpoint
        return "/health"

    async def run(self) -> None:
        interval = 1.0 / max(self.rps, 0.1)
        async with httpx.AsyncClient(timeout=5.0) as client:
            while not self._stop.is_set():
                endpoint = self._pick_endpoint()
                url = endpoint.replace("{id}", f"ord-{random.randint(1000, 1100)}")
                method = "POST" if endpoint == "/checkout" else "GET"
                started = time.perf_counter()
                try:
                    if method == "POST":
                        await client.post(f"{self.base_url}{url}", json={"sku": "sku-1"})
                    else:
                        await client.get(f"{self.base_url}{url}")
                except httpx.HTTPError:
                    pass
                elapsed = time.perf_counter() - started
                await asyncio.sleep(max(0.0, interval - elapsed))


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Demo-service traffic generator")
    parser.add_argument("--base-url", default=os.environ.get("SIM_URL", "http://demo-service:8080"))
    parser.add_argument("--rps", type=float, default=float(os.environ.get("TRAFFIC_RPS", "5")))
    args = parser.parse_args()

    generator = TrafficGenerator(args.base_url, args.rps, DEFAULT_MIX)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, generator.stop)

    await generator.run()


if __name__ == "__main__":
    asyncio.run(_main())
