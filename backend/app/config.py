"""
config.py — Central LLM configuration.

Switch models/providers by editing just two env vars in .env:
    LLM_PROVIDER=openai          # or: anthropic | google_genai | groq | ollama
    LLM_MODEL=gpt-4o-mini        # any model name valid for that provider

Internally uses LangChain's `init_chat_model` which is a universal factory
that returns the correct BaseChatModel subclass for any supported provider.
"""

import os
from functools import lru_cache
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

load_dotenv()


def get_llm(
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
) -> BaseChatModel:
    """
    Return a configured chat model.

    Call with no args to use the env-configured defaults.
    Pass overrides to use a different model for a specific task
    (e.g., a faster/cheaper model for the Manager's routing call).

    Examples
    --------
    get_llm()                                           # reads .env
    get_llm(provider="anthropic", model="claude-3-haiku-20240307")
    get_llm(provider="groq", model="llama-3.3-70b-versatile", temperature=0.0)
    get_llm(provider="ollama", model="llama3")          # fully local
    """
    _provider    = provider    or os.getenv("LLM_PROVIDER",    "openai")
    _model       = model       or os.getenv("LLM_MODEL",       "gpt-4o-mini")
    _temperature = temperature if temperature is not None else float(
        os.getenv("LLM_TEMPERATURE", "0.7")
    )

    _max_tokens = int(os.getenv("MAX_TOKENS", "300"))

    return init_chat_model(
        model=_model,
        model_provider=_provider,
        temperature=_temperature,
        max_tokens=_max_tokens,
    )




def active_config() -> dict:
    """Return the active LLM config as a dict (for health/debug endpoint)."""
    return {
        "provider":    os.getenv("LLM_PROVIDER", "openai"),
        "model":       os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "temperature": os.getenv("LLM_TEMPERATURE", "0.7"),
    }
