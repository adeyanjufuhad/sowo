"""Which Qwen3 the app talks to: Ollama (local) or a hosted OpenAI-compatible endpoint, chosen by MODEL_PROVIDER."""

from functools import lru_cache

from app.config import get_settings
from app.services.ollama import ChatModel, OllamaClient
from app.services.openai_compat import OpenAICompatibleClient


@lru_cache
def get_chat_model() -> ChatModel:
    settings = get_settings()
    if settings.model_provider == "openai":
        return OpenAICompatibleClient(
            settings.llm_base_url,
            settings.llm_api_key,
            settings.llm_model,
            timeout=settings.ollama_timeout_seconds,
            temperature=settings.ollama_temperature,
            reasoning_effort=settings.llm_reasoning_effort,
        )
    return OllamaClient(
        settings.ollama_base_url,
        settings.ollama_model,
        timeout=settings.ollama_timeout_seconds,
        temperature=settings.ollama_temperature,
    )
