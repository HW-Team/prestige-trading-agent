"""Mem0-powered cross-session memory for the Prestige agent.

Fully self-hosted: Chroma (local disk) vector store + fastembed (local)
embeddings + OpenRouter LLM for memory extraction. No external services.

The Memory object is expensive to build (Chroma client + embedding model),
so it is created lazily on first use and cached per process. If mem0 or any
of its deps fail to load (e.g. in a constrained container), we degrade to
"no memory" instead of breaking the funnel — the agent keeps working, it
just won't recall across sessions.
"""

from __future__ import annotations

import os
from typing import Any

import structlog

logger = structlog.get_logger()

_MEMORY: Any | None = None


def _build_memory() -> Any | None:
    """Build the mem0 Memory object (lazy). Returns None on any failure."""
    try:
        os.environ.setdefault(
            "OPENROUTER_API_KEY", os.environ.get("PRESTIGE_MODEL_API_KEY", "")
        )
        from mem0 import Memory  # type: ignore[import-untyped]

        config: dict[str, Any] = {
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "prestige_memory",
                    "path": "/data/mem0",
                },
            },
            "embedder": {
                "provider": "fastembed",
                "config": {"model": "BAAI/bge-small-en-v1.5"},
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": os.environ.get(
                        "PRESTIGE_MODEL", "openai/gpt-5.6-luna"
                    ),
                    "openrouter_base_url": os.environ.get(
                        "PRESTIGE_MODEL_BASE_URL", "https://openrouter.ai/api/v1"
                    ),
                    "site_url": os.environ.get(
                        "PRESTIGE_PUBLIC_BASE_URL", "https://agent.prestigetradingclub.com"
                    ),
                    "app_name": "Prestige Trading Agent",
                },
            },
            "history_db_path": "/data/mem0/history.db",
        }
        memory = Memory.from_config(config)
        logger.info("mem0_ready")
        return memory
    except Exception as exc:
        logger.warning("mem0_unavailable", error=str(exc))
        return None


def get_memory() -> Any | None:
    """Return the process-wide mem0 Memory instance (or None if unavailable)."""
    global _MEMORY
    if _MEMORY is None:
        _MEMORY = _build_memory()
    return _MEMORY


async def remember(external_id: str, text: str) -> None:
    """Store a customer message into long-term memory (never breaks the funnel)."""
    try:
        memory = get_memory()
        if memory is None:
            return
        # Run in a threadpool — mem0's sync calls would block the event loop.
        import asyncio

        await asyncio.to_thread(memory.add, text, user_id=external_id)
    except Exception as exc:
        logger.warning("mem0_add_failed", error=str(exc))


async def recall(external_id: str, query: str) -> str:
    """Return a compact summary of what mem0 remembers about this customer."""
    try:
        memory = get_memory()
        if memory is None:
            return ""
        import asyncio

        results = await asyncio.to_thread(
            memory.search, query, filters={"user_id": external_id}
        )
        memories = [r.get("memory", "") for r in (results or {}).get("results", [])]
        return " | ".join(memories) if memories else ""
    except Exception as exc:
        logger.warning("mem0_search_failed", error=str(exc))
        return ""
