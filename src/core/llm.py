"""LLM client using OpenRouter."""

from typing import Type, TypeVar
from langchain_openai import ChatOpenAI
from langchain_core.runnables import Runnable
from src.config import settings
from src.core.logging import get_logger

logger = get_logger("llm")

T = TypeVar("T")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

SUPPORTED_MODELS = {
    "claude-sonnet-4": {
        "provider": "openrouter",
        "model_id": "anthropic/claude-sonnet-4",
        "structured_method": "function_calling",
    },
    "claude-opus-4": {
        "provider": "openrouter",
        "model_id": "anthropic/claude-opus-4",
        "structured_method": "function_calling",
    },
    "gpt-4o": {
        "provider": "openrouter",
        "model_id": "openai/gpt-4o",
        "structured_method": "json_schema",
    },
    "gpt-4o-mini": {
        "provider": "openrouter",
        "model_id": "openai/gpt-4o-mini",
        "structured_method": "json_schema",
    },
    "deepseek-r1": {
        "provider": "openrouter",
        "model_id": "deepseek/deepseek-r1",
        "structured_method": "function_calling",
    },
}


def get_chat_llm(
    model: str = "claude-sonnet-4",
    temperature: float = 0.0,
    top_p: float = 0.95,
) -> ChatOpenAI:
    """Get a chat LLM instance via OpenRouter."""
    api_key = settings.openrouter_api_key
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not configured")

    config = SUPPORTED_MODELS.get(model, SUPPORTED_MODELS["claude-sonnet-4"])
    model_id = config["model_id"]

    logger.info(f"[LLM] Using OpenRouter: {model} -> {model_id}")

    return ChatOpenAI(
        model=model_id,
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        temperature=temperature,
        top_p=top_p,
    )


def get_structured_llm(
    output_model: Type[T],
    model: str = "claude-sonnet-4",
    temperature: float = 0.0,
) -> Runnable:
    """Get a structured output LLM instance."""
    config = SUPPORTED_MODELS.get(model, SUPPORTED_MODELS["claude-sonnet-4"])
    base_llm = get_chat_llm(model=model, temperature=temperature)
    return base_llm.with_structured_output(output_model, method=config["structured_method"])
