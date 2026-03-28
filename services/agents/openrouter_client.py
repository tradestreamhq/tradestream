"""OpenRouter chat completion client with retry logic.

Sends chat completions via the OpenRouter API using the OpenAI-compatible
interface.  Supports per-call model overrides and retries on 429/5xx with
exponential backoff.
"""

import logging
import os
import time
from typing import Any

from openai import OpenAI

from services.shared.model_config import MODEL_PRIMARY, OPENROUTER_BASE_URL

logger = logging.getLogger(__name__)

# Retry configuration
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_INITIAL_DELAY = 1.0  # seconds
_DEFAULT_BACKOFF_FACTOR = 2.0
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class OpenRouterClient:
    """Client for OpenRouter chat completions with automatic retries."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        initial_delay: float = _DEFAULT_INITIAL_DELAY,
        backoff_factor: float = _DEFAULT_BACKOFF_FACTOR,
    ):
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self._base_url = base_url or OPENROUTER_BASE_URL
        self._default_model = default_model or MODEL_PRIMARY
        self._max_retries = max_retries
        self._initial_delay = initial_delay
        self._backoff_factor = backoff_factor
        self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | None = "auto",
        temperature: float | None = None,
    ) -> Any:
        """Send a chat completion request with retry on transient errors.

        Args:
            messages: Chat messages in OpenAI format.
            model: Model to use; falls back to the client default.
            tools: Optional tool definitions.
            tool_choice: Tool choice strategy (default "auto").
            temperature: Sampling temperature.

        Returns:
            The ChatCompletion response object.

        Raises:
            Exception: After all retries are exhausted.
        """
        model = model or self._default_model
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if tools is not None:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        if temperature is not None:
            kwargs["temperature"] = temperature

        delay = self._initial_delay
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                return self._client.chat.completions.create(**kwargs)
            except Exception as exc:
                last_exc = exc
                status = getattr(exc, "status_code", None)
                if status not in _RETRYABLE_STATUS_CODES:
                    raise
                if attempt == self._max_retries:
                    raise
                logger.warning(
                    "OpenRouter request failed (status=%s, attempt=%d/%d), "
                    "retrying in %.1fs: %s",
                    status,
                    attempt + 1,
                    self._max_retries + 1,
                    delay,
                    exc,
                )
                time.sleep(delay)
                delay *= self._backoff_factor

        raise last_exc  # type: ignore[misc]
