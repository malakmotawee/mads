"""Runtime configuration, read from the environment (and an optional, untracked .env).

LLM selection:
1. If LLM_API_KEY is set, use the OpenAI-compatible endpoint at LLM_BASE_URL
   (default: OpenRouter) with LLM_MODEL (default: nvidia/nemotron-3-ultra-550b-a55b:free).
2. If no key is set, use the local Ollama server (OLLAMA_BASE_URL) with
   OLLAMA_MODEL (default: gpt-oss:20b). docker-compose.yml runs it as a service.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv is optional at import time
    load_dotenv = None

DEFAULT_LLM_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_LLM_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_OLLAMA_MODEL = "gpt-oss:20b"

_PLACEHOLDER_PREFIXES = ("your-", "your_", "changeme", "replace-me", "<")


@dataclass(frozen=True)
class LLMConfig:
    provider: str  # "openrouter", "ollama" or "custom"
    base_url: str
    api_key: str
    model: str
    usd_per_1m_tokens: float = 0.0
    fallback: Optional["LLMConfig"] = None

    @property
    def is_free(self) -> bool:
        # OpenRouter bills every model whose id lacks the ":free" suffix, so a zero
        # price setting must not make a paid OpenRouter model count as free.
        if self.provider == "ollama":
            return True
        if self.provider == "openrouter":
            return self.model.endswith(":free")
        return self.usd_per_1m_tokens == 0  # custom endpoint (e.g. a local server)


class PaidModelError(ValueError):
    """Raised when the configuration would send requests to a billed model."""


@dataclass(frozen=True)
class AppConfig:
    llm: LLMConfig
    outputs_dir: str
    decision_log_path: str
    search_max_results: int
    search_pause_seconds: float


def _is_unset(value: Optional[str]) -> bool:
    if value is None:
        return True
    v = value.strip()
    return v == "" or v.lower().startswith(_PLACEHOLDER_PREFIXES)


def _get(env: Mapping[str, str], key: str, default: str) -> str:
    value = env.get(key)
    return default if _is_unset(value) else value.strip()


def load_llm_config(env: Optional[Mapping[str, str]] = None) -> LLMConfig:
    env = os.environ if env is None else env
    ollama = LLMConfig(
        provider="ollama",
        base_url=_get(env, "OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
        api_key="ollama",  # Ollama ignores the key; the client requires a value
        model=_get(env, "OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
    )
    key = env.get("LLM_API_KEY")
    if _is_unset(key):
        return ollama
    base_url = _get(env, "LLM_BASE_URL", DEFAULT_LLM_BASE_URL)
    fallback_on = _get(env, "LLM_FALLBACK_TO_OLLAMA", "true").lower() not in ("0", "false", "no")
    cfg = LLMConfig(
        provider="openrouter" if "openrouter.ai" in base_url else "custom",
        base_url=base_url,
        api_key=key.strip(),
        model=_get(env, "LLM_MODEL", DEFAULT_LLM_MODEL),
        usd_per_1m_tokens=float(_get(env, "LLM_USD_PER_1M_TOKENS", "0")),
        fallback=ollama if fallback_on else None,
    )
    _check_free(cfg, env)
    return cfg


def _check_free(cfg: LLMConfig, env: Mapping[str, str]) -> None:
    """Refuse a billed OpenRouter model unless ALLOW_PAID_MODEL=true and a price is set."""
    if cfg.provider != "openrouter" or cfg.is_free:
        return
    if _get(env, "ALLOW_PAID_MODEL", "false").lower() not in ("1", "true", "yes"):
        raise PaidModelError(
            f"LLM_MODEL={cfg.model} is a paid OpenRouter model. Use a model id ending in "
            "':free' (default: nvidia/nemotron-3-ultra-550b-a55b:free), or set ALLOW_PAID_MODEL=true."
        )
    if cfg.usd_per_1m_tokens <= 0:
        raise PaidModelError(
            "ALLOW_PAID_MODEL=true needs LLM_USD_PER_1M_TOKENS > 0 so decision_log.json reports the real cost."
        )


def load_config(env: Optional[Mapping[str, str]] = None) -> AppConfig:
    if env is None and load_dotenv is not None:
        load_dotenv(override=False)
    env = os.environ if env is None else env
    return AppConfig(
        llm=load_llm_config(env),
        outputs_dir=_get(env, "OUTPUTS_DIR", "outputs"),
        decision_log_path=_get(env, "DECISION_LOG_PATH", "decision_log.json"),
        search_max_results=int(_get(env, "SEARCH_MAX_RESULTS", "8")),
        search_pause_seconds=float(_get(env, "SEARCH_PAUSE_SECONDS", "1.5")),
    )
