"""
Backboard.io client adapter.
Handles storage and retrieval of chunks via the Backboard.io Memories API.

Architecture:
  - BackboardClient (ABC): common interface for store/retrieve.
  - BackboardAPIClient: real Backboard.io integration via their REST API + SDK.
  - LocalMemoryStore: in-memory dict for testing without API keys.
  - BackboardMemoryAdapter: high-level wrapper used by the ingestion pipeline.
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from abc import ABC, abstractmethod
from pathlib import Path as _EnvPath

# Load .env from project root
try:
    from dotenv import load_dotenv
    load_dotenv(_EnvPath(__file__).resolve().parents[3] / ".env")
except ImportError:
    pass

logger = logging.getLogger(__name__)


class BackboardClient(ABC):
    """Abstract base class for Backboard storage clients."""

    @abstractmethod
    def store_chunk(
        self,
        chunk_content: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Store a single chunk."""
        pass

    @abstractmethod
    def store_chunks(
        self,
        chunks: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Store multiple chunks."""
        pass

    @abstractmethod
    def retrieve_chunks(
        self,
        user_id: str,
        query: Optional[str] = None,
        source_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Retrieve chunks matching criteria."""
        pass


# ─── Helpers ──────────────────────────────────────────────────────────────────

# Module-level persistent event loop so the SDK's async HTTP client
# isn't invalidated between calls (asyncio.run() creates + closes a loop each time).
_loop: Optional[asyncio.AbstractEventLoop] = None


def _run_async(coro):
    """Run an async coroutine from synchronous code, reusing a persistent loop."""
    global _loop

    # If we're already inside a running loop (Jupyter, FastAPI), offload.
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None

    if running and running.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()

    # Reuse a persistent loop so the SDK's httpx client stays valid.
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    return _loop.run_until_complete(coro)


# ─── Real Backboard.io Client ────────────────────────────────────────────────

class BackboardAPIClient(BackboardClient):
    """
    Backboard.io API client using the official SDK.

    Uses the Memories API (POST /assistants/{id}/memories) to store each
    ingestion chunk as an individual memory entry. Metadata (user_id,
    source_type, category, etc.) is attached to each memory.

    Requires:
      - BACKBOARD_API_KEY env var (or passed directly)
      - BACKBOARD_ASSISTANT_ID env var (or passed directly, or auto-created)
    """

    ASSISTANT_NAME = "KnowledgeMap Ingestion"
    ASSISTANT_PROMPT = (
        "You are a knowledge-map assistant that stores and retrieves "
        "user knowledge from ingested text, GitHub repos, and PDFs."
    )

    def __init__(
        self,
        api_key: Optional[str] = None,
        assistant_id: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("BACKBOARD_API_KEY")
        self.assistant_id = assistant_id or os.getenv("BACKBOARD_ASSISTANT_ID")

        if not self.api_key:
            raise ValueError(
                "Backboard API key required. "
                "Set BACKBOARD_API_KEY environment variable or pass api_key."
            )

        # Lazy-import so the rest of the codebase doesn't hard-depend on SDK
        try:
            from backboard import BackboardClient as _SDKClient
            self._sdk = _SDKClient(api_key=self.api_key)
        except ImportError:
            raise ImportError(
                "backboard-sdk is required for BackboardAPIClient. "
                "Install it with: pip install backboard-sdk"
            )

        # Auto-create assistant if none provided
        if not self.assistant_id:
            self.assistant_id = self._get_or_create_assistant()

    def _get_or_create_assistant(self) -> str:
        """Find an existing KnowledgeMap assistant or create a new one."""
        async def _resolve():
            # Look for existing assistant with our name
            assistants = await self._sdk.list_assistants()
            for a in assistants:
                if a.name == self.ASSISTANT_NAME:
                    logger.info(f"Found existing Backboard assistant: {a.assistant_id}")
                    return a.assistant_id

            # Create a new one
            assistant = await self._sdk.create_assistant(
                name=self.ASSISTANT_NAME,
                system_prompt=self.ASSISTANT_PROMPT,
            )
            logger.info(f"Created new Backboard assistant: {assistant.assistant_id}")
            return assistant.assistant_id

        aid = _run_async(_resolve())
        # Persist to .env for next run
        self._persist_assistant_id(aid)
        return aid

    @staticmethod
    def _persist_assistant_id(assistant_id: str):
        """Write assistant_id back to .env so future runs reuse it."""
        from pathlib import Path as _Path
        env_path = _Path(__file__).resolve().parents[2] / ".env"
        try:
            if env_path.exists():
                lines = env_path.read_text().splitlines()
                found = False
                for i, line in enumerate(lines):
                    if line.startswith("BACKBOARD_ASSISTANT_ID="):
                        lines[i] = f"BACKBOARD_ASSISTANT_ID={assistant_id}"
                        found = True
                        break
                if not found:
                    lines.append(f"BACKBOARD_ASSISTANT_ID={assistant_id}")
                env_path.write_text("\n".join(lines) + "\n")
            else:
                env_path.write_text(f"BACKBOARD_ASSISTANT_ID={assistant_id}\n")
            logger.info(f"Saved BACKBOARD_ASSISTANT_ID to {env_path}")
        except Exception as e:
            logger.warning(f"Could not persist assistant_id to .env: {e}")

    # ── Store ──

    def store_chunk(
        self,
        chunk_content: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Store a single chunk as a Backboard memory."""
        return self.store_chunks(
            [{"content": chunk_content, "metadata": metadata}], {}
        )

    def store_chunks(
        self,
        chunks: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Store multiple chunks as individual Backboard memories.

        Each chunk becomes one memory entry with its metadata attached.
        """
        if not chunks:
            return {"success": False, "error": "No chunks to store", "stored_count": 0}

        async def _store_all():
            memory_ids = []
            errors = []
            for i, chunk in enumerate(chunks):
                content = chunk.get("content", "")
                chunk_meta = {**chunk.get("metadata", {})}
                chunk_meta["chunk_index"] = chunk_meta.get("chunk_index", i)

                # Flatten any non-serializable values
                safe_meta = {}
                for k, v in chunk_meta.items():
                    if isinstance(v, (str, int, float, bool)) or v is None:
                        safe_meta[k] = v
                    elif isinstance(v, (list, dict)):
                        safe_meta[k] = json.dumps(v) if not isinstance(v, str) else v
                    else:
                        safe_meta[k] = str(v)

                try:
                    result = await self._sdk.add_memory(
                        assistant_id=self.assistant_id,
                        content=content,
                        metadata=safe_meta,
                    )
                    # SDK returns dict with 'memory_id' key
                    if isinstance(result, dict):
                        mid = result.get("memory_id") or result.get("id")
                    else:
                        mid = getattr(result, "memory_id", None) or getattr(result, "id", str(result))
                    memory_ids.append(mid)
                except Exception as e:
                    logger.error(f"Failed to store chunk {i}: {e}")
                    errors.append({"chunk_index": i, "error": str(e)})

            return memory_ids, errors

        memory_ids, errors = _run_async(_store_all())

        success = len(memory_ids) > 0
        result = {
            "success": success,
            "stored_count": len(memory_ids),
            "memory_ids": memory_ids,
            "message": f"Stored {len(memory_ids)}/{len(chunks)} chunks in Backboard.io",
        }
        if errors:
            result["errors"] = errors
        return result

    # ── Retrieve ──

    def retrieve_chunks(
        self,
        user_id: str,
        query: Optional[str] = None,
        source_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve memories from Backboard.io for a given user.

        Uses GET /assistants/{id}/memories and filters client-side by
        user_id and optional source_type.
        """
        async def _retrieve():
            resp = await self._sdk.get_memories(self.assistant_id)
            return resp

        try:
            resp = _run_async(_retrieve())
            memories = resp.memories if hasattr(resp, "memories") else []

            results = []
            for mem in memories:
                meta = mem.metadata or {}
                # Filter by user_id
                if meta.get("user_id") != user_id:
                    continue
                # Filter by source_type
                if source_type and meta.get("source_type") != source_type:
                    continue
                results.append({
                    "id": mem.id,
                    "content": mem.content,
                    "metadata": meta,
                    "created_at": mem.created_at,
                })
                if len(results) >= limit:
                    break

            return results

        except Exception as e:
            logger.error(f"Error retrieving memories from Backboard.io: {e}")
            return []

    # ── Cleanup helpers (optional) ──

    def get_stats(self) -> Dict[str, Any]:
        """Get memory stats for the assistant."""
        async def _stats():
            return await self._sdk.get_memory_stats(self.assistant_id)
        try:
            stats = _run_async(_stats())
            return {
                "total_memories": stats.total_memories,
                "last_updated": stats.last_updated,
                "limits": stats.limits,
            }
        except Exception as e:
            return {"error": str(e)}

    def delete_memory(self, memory_id: str) -> Dict[str, Any]:
        """Delete a single memory."""
        async def _delete():
            return await self._sdk.delete_memory(self.assistant_id, memory_id)
        try:
            return _run_async(_delete())
        except Exception as e:
            return {"success": False, "error": str(e)}


# ─── High-level Adapter ──────────────────────────────────────────────────────

class BackboardMemoryAdapter:
    """
    High-level adapter for Backboard memory operations.
    Provides clean interface for ingestion pipeline.
    """

    def __init__(self, client: Optional[BackboardClient] = None):
        """
        Initialize adapter.

        Args:
            client: A BackboardClient instance.
                    If None, tries to create BackboardAPIClient (needs env vars).
                    Falls back to LocalMemoryStore if env vars are missing.
        """
        if client is not None:
            self.client = client
        else:
            try:
                self.client = BackboardAPIClient()
            except (ValueError, ImportError) as e:
                logger.warning(
                    f"Could not initialise BackboardAPIClient ({e}). "
                    "Falling back to LocalMemoryStore."
                )
                self.client = LocalMemoryStore()

    @property
    def is_live(self) -> bool:
        """True if using the real Backboard.io API."""
        return isinstance(self.client, BackboardAPIClient)

    def save_ingestion_result(
        self,
        user_id: str,
        input_type: str,
        chunks: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Save ingestion result to Backboard.

        Args:
            user_id: User ID
            input_type: Type of input (text_prompt, github_repo, pdf)
            chunks: List of chunks with content and metadata
            metadata: Additional metadata

        Returns:
            Storage result
        """
        # Ensure all chunks have proper metadata
        for chunk in chunks:
            if "metadata" not in chunk:
                chunk["metadata"] = {}

            chunk["metadata"]["user_id"] = user_id
            chunk["metadata"]["source_type"] = input_type
            chunk["metadata"]["ingestion_timestamp"] = datetime.utcnow().isoformat()

            # Merge with provided metadata
            chunk["metadata"].update(metadata)

        # Store all chunks
        result = self.client.store_chunks(chunks, metadata)

        return {
            **result,
            "input_type": input_type,
            "user_id": user_id,
            "total_chunks": len(chunks),
        }

    def search_memories(
        self,
        user_id: str,
        query: str,
        source_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search user's memories.

        Args:
            user_id: User ID
            query: Search query
            source_type: Optional filter by type
            limit: Max results

        Returns:
            List of matching chunks
        """
        return self.client.retrieve_chunks(
            user_id=user_id,
            query=query,
            source_type=source_type,
            limit=limit,
        )


# ─── Local In-Memory Store (testing / offline) ───────────────────────────────

class LocalMemoryStore(BackboardClient):
    """
    Local in-memory storage for development and testing.
    Can be swapped with BackboardAPIClient in production.
    """

    def __init__(self):
        """Initialize local store."""
        self.store: Dict[str, List[Dict[str, Any]]] = {}

    def store_chunk(
        self,
        chunk_content: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Store a single chunk locally."""
        return self.store_chunks([{
            "content": chunk_content,
            "metadata": metadata,
        }], {})

    def store_chunks(
        self,
        chunks: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Store multiple chunks locally."""
        user_id = chunks[0].get("metadata", {}).get("user_id") if chunks else "unknown"
        source_type = chunks[0].get("metadata", {}).get("source_type", "unknown") if chunks else "unknown"

        if user_id not in self.store:
            self.store[user_id] = []

        chunk_ids = []
        for chunk in chunks:
            chunk_id = f"{source_type}_{len(self.store[user_id])}"
            chunk["id"] = chunk_id
            chunk["stored_at"] = datetime.utcnow().isoformat()
            self.store[user_id].append(chunk)
            chunk_ids.append(chunk_id)

        return {
            "success": True,
            "stored_count": len(chunks),
            "chunk_ids": chunk_ids,
        }

    def retrieve_chunks(
        self,
        user_id: str,
        query: Optional[str] = None,
        source_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Retrieve chunks locally."""
        if user_id not in self.store:
            return []

        chunks = self.store[user_id]

        # Filter by source type if provided
        if source_type:
            chunks = [
                c for c in chunks
                if c.get("metadata", {}).get("source_type") == source_type
            ]

        return chunks[:limit]


# ─── Example / smoke test ────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("Backboard.io Client – Smoke Test")
    print("=" * 60)

    # Check if real API keys are available
    api_key = os.getenv("BACKBOARD_API_KEY")
    assistant_id = os.getenv("BACKBOARD_ASSISTANT_ID")

    if api_key:
        print(f"\n✅ BACKBOARD_API_KEY found")
        if assistant_id:
            print(f"   BACKBOARD_ASSISTANT_ID: {assistant_id}")
        else:
            print("   BACKBOARD_ASSISTANT_ID not set — will auto-create")
        print("   Using real Backboard.io API\n")

        adapter = BackboardMemoryAdapter()  # auto-creates BackboardAPIClient
        print(f"   Live mode: {adapter.is_live}")

        # Store a test memory
        chunks = [
            {"content": "Test chunk from smoke test", "metadata": {"user_id": "smoke_test_user"}},
        ]
        result = adapter.save_ingestion_result(
            user_id="smoke_test_user",
            input_type="text_prompt",
            chunks=chunks,
            metadata={"category": "test"},
        )
        print(f"\n   Store result: {json.dumps(result, indent=2, default=str)}")

        # Retrieve
        retrieved = adapter.search_memories("smoke_test_user", "test")
        print(f"   Retrieved {len(retrieved)} memories")
        for m in retrieved[:3]:
            print(f"     - [{m.get('id', '?')[:8]}...] {m.get('content', '')[:60]}")

        # Stats
        if isinstance(adapter.client, BackboardAPIClient):
            stats = adapter.client.get_stats()
            print(f"\n   Stats: {json.dumps(stats, indent=2, default=str)}")

    else:
        print("\n⚠️  No BACKBOARD_API_KEY / BACKBOARD_ASSISTANT_ID found")
        print("   Falling back to LocalMemoryStore\n")

        adapter = BackboardMemoryAdapter()
        print(f"   Live mode: {adapter.is_live}")

        chunks = [
            {"content": "Test chunk 1", "metadata": {"user_id": "user_1"}},
            {"content": "Test chunk 2", "metadata": {"user_id": "user_1"}},
        ]
        result = adapter.save_ingestion_result(
            user_id="user_1",
            input_type="text_prompt",
            chunks=chunks,
            metadata={"category": "skill"},
        )
        print(f"   Store result: {result}")

        retrieved = adapter.search_memories("user_1", "test")
        print(f"   Retrieved {len(retrieved)} chunks")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)
