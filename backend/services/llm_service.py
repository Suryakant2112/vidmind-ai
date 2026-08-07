"""
LLM service — isolated integration with Groq API via LangChain.
Change this one file to switch LLM providers.
"""

import logging
from typing import Optional
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from backend.config import get_settings

logger = logging.getLogger(__name__)

# Module-level LLM instance cache
_llm: Optional[ChatGroq] = None


def get_llm() -> ChatGroq:
    """
    Get or create the LLM instance (Groq via LangChain).

    Uses GROQ_API_KEY from environment.
    To switch providers, replace ChatGroq with ChatOpenAI, ChatAnthropic, etc.
    """
    global _llm
    if _llm is None:
        settings = get_settings()

        if not settings.LLM_API_KEY:
            raise ValueError(
                "LLM_API_KEY is not set. "
                "Get a free API key from https://console.groq.com "
                "and add it to your .env file."
            )

        _llm = ChatGroq(
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            max_retries=2,
        )
        logger.info(f"LLM initialized: {settings.LLM_MODEL} via Groq")

    return _llm


def generate_response(
    system_prompt: str,
    user_prompt: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """
    Generate a response from the LLM.

    Args:
        system_prompt: System message setting the behavior
        user_prompt: User message / input
        temperature: Override default temperature
        max_tokens: Override default max tokens

    Returns:
        Generated text response

    Raises:
        Exception with user-friendly error messages for API failures
    """
    try:
        llm = get_llm()

        # Apply overrides if provided
        kwargs = {}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        if kwargs:
            llm = llm.bind(**kwargs) if hasattr(llm, "bind") else llm

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        response = llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)

        logger.info(
            f"LLM response generated ({len(content)} chars)"
        )
        return content

    except Exception as e:
        error_msg = str(e)
        logger.error(f"LLM generation failed: {error_msg}")

        if "429" in error_msg or "rate" in error_msg.lower():
            raise Exception(
                "LLM rate limit reached. The free tier has request limits. "
                "Please wait a moment and try again."
            )
        elif "401" in error_msg or "auth" in error_msg.lower():
            raise Exception(
                "LLM API authentication failed. "
                "Please check your LLM_API_KEY in the .env file."
            )
        elif "timeout" in error_msg.lower():
            raise Exception(
                "LLM API request timed out. Please try again."
            )
        else:
            raise Exception(f"LLM generation failed: {error_msg}")


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
    try:
        llm = get_llm()
        from langchain_core.messages import AIMessage

        messages = [SystemMessage(content=system_prompt)]

        # Add conversation history
        for turn in conversation_history:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

        # Add current question
        messages.append(HumanMessage(content=user_prompt))

        response = llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)

        return content

    except Exception as e:
        error_msg = str(e)
        logger.error(f"LLM generation with history failed: {error_msg}")

        if "429" in error_msg or "rate" in error_msg.lower():
            raise Exception(
                "LLM rate limit reached. Please wait a moment and try again."
            )
        else:
            raise Exception(f"LLM generation failed: {error_msg}")
