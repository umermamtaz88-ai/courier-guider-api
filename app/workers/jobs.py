import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


async def enqueue_job(name: str, coro_factory: Callable[[], Awaitable[Any]]) -> None:
    """Lightweight background job — runs asyncio task in-process."""
    asyncio.create_task(_run_job(name, coro_factory))


async def _run_job(name: str, coro_factory: Callable[[], Awaitable[Any]]) -> None:
    try:
        await coro_factory()
    except Exception as exc:
        print(f"[job:{name}] failed: {exc}")
