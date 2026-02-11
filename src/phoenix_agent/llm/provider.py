"""LLM provider factory - supports Anthropic, OpenAI, Groq, Ollama."""

from __future__ import annotations

import logging
import os

from phoenix_agent.config import PhoenixConfig

logger = logging.getLogger(__name__)


def _is_ollama_available(base_url: str = "http://localhost:11434") -> bool:
    try:
        import urllib.request
        urllib.request.urlopen(f"{base_url}/api/tags", timeout=2)
        return True
    except Exception:
        return False


def create_llm(config: PhoenixConfig):
    """Create an LLM instance based on configuration."""
    provider = config.llm.provider.lower()
    model = config.llm.model
    temperature = config.llm.temperature
    max_tokens = config.llm.max_tokens

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        api_key = config.llm.api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        logger.info(f"Using Anthropic: {model}")
        return ChatAnthropic(
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        logger.info(f"Using OpenAI: {model}")
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    elif provider == "groq":
        from langchain_groq import ChatGroq
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set")
        logger.info(f"Using Groq: {model}")
        return ChatGroq(
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        base_url = config.llm.base_url or "http://localhost:11434"
        if not _is_ollama_available(base_url):
            raise ConnectionError(f"Ollama not available at {base_url}")
        logger.info(f"Using Ollama: {model}")
        return ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
        )

    elif provider == "auto":
        # Try Ollama first, then Groq, then Anthropic
        if _is_ollama_available():
            config.llm.provider = "ollama"
            return create_llm(config)
        if os.getenv("GROQ_API_KEY"):
            config.llm.provider = "groq"
            config.llm.model = "llama-3.3-70b-versatile"
            return create_llm(config)
        if os.getenv("ANTHROPIC_API_KEY"):
            config.llm.provider = "anthropic"
            return create_llm(config)
        raise ValueError("No LLM provider available. Set ANTHROPIC_API_KEY, GROQ_API_KEY, or run Ollama.")

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
