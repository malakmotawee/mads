"""decision_log.json writer: one entry per agent action.

Every entry has the five required keys (action, sources, model, cost,
approved_by) plus timestamp and agent. Extra keys (outcome, tokens, detail)
are allowed. The file is rewritten atomically after every append.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

REQUIRED_KEYS = ("timestamp", "agent", "action", "sources", "model", "cost", "approved_by")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class DecisionLog:
    def __init__(self, path: str, reset: bool = True):
        self.path = path
        self.entries: list[dict[str, Any]] = []
        if not reset and os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                self.entries = json.load(fh)
        self._flush()

    def record(
        self,
        agent: str,
        action: str,
        *,
        sources: Optional[Iterable[str]] = None,
        model: Optional[str] = None,
        cost: float = 0,
        approved_by: Optional[str] = None,
        **extra: Any,
    ) -> dict[str, Any]:
        if not action or not isinstance(action, str):
            raise ValueError("action must be a non-empty string")
        srcs = sorted({s for s in (sources or []) if isinstance(s, str) and s.startswith("http")})
        entry: dict[str, Any] = {
            "timestamp": utc_now(),
            "agent": agent,
            "action": action,
            "sources": srcs,
            "model": model,
            "cost": float(cost or 0),
            "approved_by": approved_by,
        }
        entry.update({k: v for k, v in extra.items() if k not in entry})
        self.entries.append(entry)
        self._flush()
        return entry

    @property
    def total_cost(self) -> float:
        return round(sum(e["cost"] for e in self.entries), 6)

    @property
    def total_tokens(self) -> int:
        return sum(int(e.get("tokens") or 0) for e in self.entries)

    def _flush(self) -> None:
        directory = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(self.entries, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, self.path)
