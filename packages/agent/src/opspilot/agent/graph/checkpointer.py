from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


async def create_postgres_checkpointer(database_url: str) -> AsyncPostgresSaver:
    cm = AsyncPostgresSaver.from_conn_string(database_url)
    checkpointer = await cm.__aenter__()
    await checkpointer.setup()
    return checkpointer


def create_memory_checkpointer() -> MemorySaver:
    return MemorySaver()
