"""OpenAI-compatible LLM client (OpenRouter by default, local Ollama as fallback)."""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from config import LLMConfig


class LLMError(RuntimeError):
    pass


@dataclass
class LLMResult:
    text: str
    model: str
    tokens: int
    cost: float


def _ollama_root(base_url: str) -> str:
    return re.sub(r"/v1/?$", "", base_url.rstrip("/"))


def ensure_ollama_model(base_url: str, model: str, wait_seconds: int = 180) -> None:
    """Wait for the Ollama server, then pull the model if it is not there yet."""
    root = _ollama_root(base_url)
    deadline = time.time() + wait_seconds
    tags: dict[str, Any] = {}
    while True:
        try:
            with urllib.request.urlopen(f"{root}/api/tags", timeout=10) as resp:
                tags = json.load(resp)
            break
        except (urllib.error.URLError, OSError) as exc:
            if time.time() > deadline:
                raise LLMError(f"Ollama is not reachable at {root}: {exc}") from exc
            time.sleep(3)
    names = {m.get("name") for m in tags.get("models", [])} | {m.get("model") for m in tags.get("models", [])}
    if model in names or f"{model}:latest" in names:
        return
    print(f"[llm] pulling {model} into Ollama (first run only; this can take a while)...", file=sys.stderr)
    req = urllib.request.Request(
        f"{root}/api/pull",
        data=json.dumps({"model": model, "stream": True}).encode(),
        headers={"Content-Type": "application/json"},
    )
    last = ""
    try:
        with urllib.request.urlopen(req, timeout=None) as resp:
            for line in resp:
                status = json.loads(line or b"{}").get("status", "")
                if "error" in status.lower():
                    raise LLMError(f"Ollama pull failed: {status}")
                if status != last:
                    print(f"[llm] {status}", file=sys.stderr)
                    last = status
    except urllib.error.URLError as exc:
        raise LLMError(f"Ollama pull failed: {exc}") from exc


class LLMClient:
    """Small wrapper that returns text plus model name, tokens and USD cost."""

    def __init__(self, cfg: LLMConfig, timeout: float = 600.0):
        self.cfg = cfg
        self.active = cfg
        self.timeout = timeout
        self._clients: dict[str, Any] = {}
        self._ollama_ready = False

    @property
    def model_name(self) -> str:
        return self.active.model

    def _client(self, cfg: LLMConfig):
        if cfg.base_url not in self._clients:
            from openai import OpenAI

            self._clients[cfg.base_url] = OpenAI(
                base_url=cfg.base_url, api_key=cfg.api_key, timeout=self.timeout, max_retries=0
            )
        return self._clients[cfg.base_url]

    def complete(self, system: str, user: str) -> LLMResult:
        try:
            return self._call(self.active, system, user)
        except LLMError as exc:
            if self.active.fallback is None:
                raise
            print(f"[llm] {self.active.provider} failed ({exc}); falling back to Ollama", file=sys.stderr)
            self.active = self.active.fallback
            return self._call(self.active, system, user)

    def _call(self, cfg: LLMConfig, system: str, user: str) -> LLMResult:
        from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

        if cfg.provider == "ollama" and not self._ollama_ready:
            ensure_ollama_model(cfg.base_url, cfg.model)
            self._ollama_ready = True
        last_error: Optional[Exception] = None
        for attempt in range(4):
            try:
                resp = self._client(cfg).chat.completions.create(
                    model=cfg.model,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    temperature=0.2,
                )
                text = (resp.choices[0].message.content or "").strip() if resp.choices else ""
                if not text:
                    raise LLMError("empty completion")
                tokens = int(getattr(resp.usage, "total_tokens", 0) or 0) if resp.usage else 0
                cost = 0.0 if cfg.is_free else round(tokens * cfg.usd_per_1m_tokens / 1_000_000, 6)
                return LLMResult(text=text, model=cfg.model, tokens=tokens, cost=cost)
            except (RateLimitError, APIConnectionError, APITimeoutError, LLMError) as exc:
                last_error = exc
                time.sleep(min(60, 5 * 2**attempt))
            except APIStatusError as exc:
                if exc.status_code >= 500:
                    last_error = exc
                    time.sleep(min(60, 5 * 2**attempt))
                    continue
                raise LLMError(f"HTTP {exc.status_code}: {exc.message}") from exc
        raise LLMError(f"giving up after retries: {last_error}")


def parse_json(text: str) -> Any:
    """Extract the first JSON object from a model reply (tolerates code fences and prose)."""
    cleaned = re.sub(r"```(?:json)?", "", text)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in reply")
    return json.loads(cleaned[start : end + 1])
