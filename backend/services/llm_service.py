"""
LLM service — provider fallback chain via LangChain's OpenAI-compatible client.

Providers are tried in order (Groq primary → Groq fallback model → Gemini).
If one hits its free-tier rate limit or fails, the next one answers.
"""

import logging
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage

from backend.config import get_settings

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Module-level cache of (provider_label, llm) pairs
_llms: Optional[list[tuple[str, ChatOpenAI]]] = None


def get_llms() -> list[tuple[str, ChatOpenAI]]:
    """
    Build the ordered provider chain from settings.
    Providers without an API key are skipped.
    """
    global _llms
    if _llms is None:
        settings = get_settings()
        candidates = []
        if settings.LLM_API_KEY:
            candidates.append(("groq", settings.LLM_MODEL, settings.LLM_API_KEY, GROQ_BASE_URL))
            if settings.LLM_FALLBACK_MODEL:
                candidates.append(
                    ("groq", settings.LLM_FALLBACK_MODEL, settings.LLM_API_KEY, GROQ_BASE_URL)
                )
        if settings.GEMINI_API_KEY:
            candidates.append(("gemini", settings.GEMINI_MODEL, settings.GEMINI_API_KEY, GEMINI_BASE_URL))

        if not candidates:
            raise ValueError(
                "No LLM API key is set. Add LLM_API_KEY (free at https://console.groq.com) "
                "and/or GEMINI_API_KEY (free at https://aistudio.google.com) to your .env file."
            )

        _llms = []
        for provider, model, api_key, base_url in candidates:
            llm = ChatOpenAI(
                model=model,
                api_key=api_key,
                base_url=base_url,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
                # Fail over quickly instead of waiting out a rate limit
                max_retries=1,
                timeout=120,
            )
            _llms.append((f"{provider}:{model}", llm))

        logger.info(f"LLM chain: {' → '.join(label for label, _ in _llms)}")

    return _llms


def _friendly_error(error_msg: str) -> str:
    """Map a raw provider error to a user-facing message."""
    lower = error_msg.lower()
    if "429" in error_msg or "rate" in lower or "quota" in lower:
        return (
            "All free LLM providers have hit their rate limits. "
            "Please wait a minute and try again."
        )
    if "401" in error_msg or "auth" in lower or "api key" in lower:
        return "LLM API authentication failed. Please check your API keys in the .env file."
    if "timeout" in lower or "timed out" in lower:
        return "LLM API request timed out. Please try again."
    return f"LLM generation failed: {error_msg}"


def _invoke(messages: list[BaseMessage], **overrides) -> str:
    """Try each provider in order and return the first successful response."""
    last_error = ""
    for label, llm in get_llms():
        try:
            runnable = llm.bind(**overrides) if overrides else llm
            response = runnable.invoke(messages)
            content = response.content if hasattr(response, "content") else str(response)
            logger.info(f"LLM response from {label} ({len(content)} chars)")
            return content
        except Exception as e:
            last_error = str(e)
            logger.warning(f"LLM provider {label} failed, trying next: {last_error[:200]}")

    logger.error(f"All LLM providers failed. Last error: {last_error}")
    raise Exception(_friendly_error(last_error))


def generate_response(
    system_prompt: str,
    user_prompt: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """
    Generate a response from the LLM chain.

    Args:
        system_prompt: System message setting the behavior
        user_prompt: User message / input
        temperature: Override default temperature
        max_tokens: Override default max tokens

    Returns:
        Generated text response
    """
    overrides = {}
    if temperature is not None:
        overrides["temperature"] = temperature
    if max_tokens is not None:
        overrides["max_tokens"] = max_tokens

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    return _invoke(messages, **overrides)


def generate_response_with_history(
    system_prompt: str,
    conversation_history: list[dict],
    user_prompt: str,
) -> str:
    """
    Generate a response with conversation history for multi-turn Q&A.

    Args:
        system_prompt: System message
        conversation_history: List of {"role": "user"|"assistant", "content": str}
        user_prompt: Current user message

    Returns:
        Generated text response
    """
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]

    for turn in conversation_history:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=user_prompt))
    return _invoke(messages)
