"""Hindsight memory layer with graceful local fallback.

Primary path: real Hindsight via hindsight-client (retain/recall/reflect).
Fallback path: local JSONL keyword store, used ONLY when the Hindsight
server is unreachable, so live demos never crash. The API shape is
identical, and /stats reports which mode is active.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


class HindsightMemory:
    def __init__(self, base_url: str, api_key: str | None, bank_id: str,
                 fallback_path: str = "./data/memory_fallback.jsonl"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or None
        self.bank_id = bank_id
        self.fallback_path = Path(fallback_path)
        self.fallback_path.parent.mkdir(parents=True, exist_ok=True)
        self.mode = "fallback"
        self._init_error = None
        # Probe once at startup to decide the primary mode. Per-request
        # clients are created fresh (see _fresh_client) because the SDK's
        # async session cannot be shared across worker threads.
        try:
            self._fresh_client().recall(bank_id=bank_id, query="health check", max_tokens=64)
            self.mode = "hindsight"
        except Exception as e:  # noqa: BLE001 - must never break demo
            self._init_error = str(e)[:300]
            self.mode = "fallback"

    def _fresh_client(self):
        from hindsight_client import Hindsight
        return Hindsight(base_url=self.base_url, api_key=self.api_key)

    # ---- public API ----

    def retain(self, content: str, context: str | None = None,
               metadata: dict | None = None) -> dict:
        """Store one memory. Returns {ok, mode}."""
        if self.mode == "hindsight":
            try:
                self._fresh_client().retain(
                    bank_id=self.bank_id,
                    content=content,
                    context=context,
                    metadata={k: str(v) for k, v in (metadata or {}).items()},
                )
                return {"ok": True, "mode": "hindsight"}
            except Exception as e:  # noqa: BLE001 - fall through to local store
                self._init_error = str(e)[:300]
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "bank_id": self.bank_id,
            "content": content,
            "context": context,
            "metadata": metadata or {},
        }
        with open(self.fallback_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return {"ok": True, "mode": "fallback"}

    def recall(self, query: str, max_tokens: int = 2048) -> dict:
        """Retrieve relevant memories. Returns {mode, memories: [{content, ...}]}."""
        if self.mode == "hindsight":
            try:
                resp = self._fresh_client().recall(
                    bank_id=self.bank_id,
                    query=query,
                    max_tokens=max_tokens,
                    prefer_observations=True,
                )
                memories = []
                # SDK returns objects with .fact / .content / .text depending on version
                results = getattr(resp, "results", None) or getattr(resp, "memories", None) or []
                for r in results:
                    text = (
                        getattr(r, "fact", None) or getattr(r, "content", None)
                        or getattr(r, "text", None) or str(r)
                    )
                    memories.append({"content": str(text)})
                return {"mode": "hindsight", "memories": memories}
            except Exception as e:  # fall through for this call only; retry fresh next time
                self._init_error = str(e)[:300]
        return {"mode": "fallback", "memories": self._keyword_search(query)}

    def status(self) -> dict:
        return {
            "mode": self.mode,
            "bank_id": self.bank_id,
            "fallback_records": self._count_fallback(),
            "init_error": self._init_error,
        }

    # ---- fallback internals ----

    def _count_fallback(self) -> int:
        if not self.fallback_path.exists():
            return 0
        with open(self.fallback_path, encoding="utf-8") as f:
            return sum(1 for _ in f)

    def _keyword_search(self, query: str, limit: int = 8) -> list[dict]:
        if not self.fallback_path.exists():
            return []
        tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9]+", query) if len(t) > 2]
        scored = []
        with open(self.fallback_path, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                hay = (rec.get("content", "") + " " + str(rec.get("context", ""))).lower()
                score = sum(1 for t in tokens if t in hay)
                if score > 0:
                    scored.append((score, rec))
        scored.sort(key=lambda x: -x[0])
        return [{"content": r["content"], "context": r.get("context")} for _, r in scored[:limit]]


def build_memory_from_env() -> HindsightMemory:
    base_url = os.getenv("HINDSIGHT_BASE_URL", "http://localhost:8888")
    api_key = os.getenv("HINDSIGHT_API_KEY", "")
    bank_id = os.getenv("HINDSIGHT_BANK_ID", "ap-vendor-memory")
    fallback = os.getenv("MEMORY_FALLBACK_PATH", "./data/memory_fallback.jsonl")
    return HindsightMemory(base_url, api_key, bank_id, fallback)
