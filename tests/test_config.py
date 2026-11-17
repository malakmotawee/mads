"""The configuration must never select a billed model by accident."""
import pytest

from config import PaidModelError, load_llm_config


def test_no_key_uses_local_ollama():
    cfg = load_llm_config({})
    assert cfg.provider == "ollama" and cfg.is_free


def test_default_openrouter_model_is_free():
    cfg = load_llm_config({"LLM_API_KEY": "sk-test"})
    assert cfg.model.endswith(":free") and cfg.is_free


def test_paid_openrouter_model_is_refused():
    with pytest.raises(PaidModelError):
        load_llm_config({"LLM_API_KEY": "sk-test", "LLM_MODEL": "openai/gpt-oss-120b"})


def test_paid_model_with_zero_price_is_refused_even_when_allowed():
    env = {"LLM_API_KEY": "sk-test", "LLM_MODEL": "openai/gpt-oss-120b", "ALLOW_PAID_MODEL": "true"}
    with pytest.raises(PaidModelError):
        load_llm_config(env)


def test_fallback_to_ollama_can_be_disabled():
    cfg = load_llm_config({"LLM_API_KEY": "sk-test", "LLM_FALLBACK_TO_OLLAMA": "false"})
    assert cfg.fallback is None
