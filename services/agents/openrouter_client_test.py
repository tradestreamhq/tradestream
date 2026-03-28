"""Tests for OpenRouterClient."""

import types
from unittest.mock import MagicMock, patch

import pytest

from services.agents.openrouter_client import OpenRouterClient


class _FakeAPIError(Exception):
    """Simulates an OpenAI API error with a status_code attribute."""

    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__(f"API error {status_code}")


def _make_completion(content="hello"):
    """Return a minimal fake ChatCompletion-like object."""
    message = types.SimpleNamespace(content=content, tool_calls=None)
    usage = types.SimpleNamespace(total_tokens=10)
    choice = types.SimpleNamespace(message=message, finish_reason="stop")
    return types.SimpleNamespace(choices=[choice], usage=usage)


class TestOpenRouterClient:
    """Tests for the OpenRouter chat completion client."""

    def test_chat_success(self):
        client = OpenRouterClient(api_key="test-key")
        fake_resp = _make_completion("world")
        client._client = MagicMock()
        client._client.chat.completions.create.return_value = fake_resp

        result = client.chat([{"role": "user", "content": "hi"}])

        assert result.choices[0].message.content == "world"
        client._client.chat.completions.create.assert_called_once()

    def test_chat_model_override(self):
        client = OpenRouterClient(api_key="test-key", default_model="model-a")
        client._client = MagicMock()
        client._client.chat.completions.create.return_value = _make_completion()

        client.chat([{"role": "user", "content": "hi"}], model="model-b")

        call_kwargs = client._client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "model-b"

    def test_chat_uses_default_model(self):
        client = OpenRouterClient(api_key="test-key", default_model="model-a")
        client._client = MagicMock()
        client._client.chat.completions.create.return_value = _make_completion()

        client.chat([{"role": "user", "content": "hi"}])

        call_kwargs = client._client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "model-a"

    def test_chat_passes_tools(self):
        client = OpenRouterClient(api_key="test-key")
        client._client = MagicMock()
        client._client.chat.completions.create.return_value = _make_completion()
        tools = [{"type": "function", "function": {"name": "foo"}}]

        client.chat([{"role": "user", "content": "hi"}], tools=tools)

        call_kwargs = client._client.chat.completions.create.call_args
        assert call_kwargs.kwargs["tools"] == tools
        assert call_kwargs.kwargs["tool_choice"] == "auto"

    @patch("services.agents.openrouter_client.time.sleep")
    def test_retry_on_429(self, mock_sleep):
        client = OpenRouterClient(api_key="test-key", max_retries=2, initial_delay=0.1)
        client._client = MagicMock()
        client._client.chat.completions.create.side_effect = [
            _FakeAPIError(429),
            _make_completion("ok"),
        ]

        result = client.chat([{"role": "user", "content": "hi"}])

        assert result.choices[0].message.content == "ok"
        assert client._client.chat.completions.create.call_count == 2
        mock_sleep.assert_called_once()

    @patch("services.agents.openrouter_client.time.sleep")
    def test_retry_on_500(self, mock_sleep):
        client = OpenRouterClient(api_key="test-key", max_retries=2, initial_delay=0.1)
        client._client = MagicMock()
        client._client.chat.completions.create.side_effect = [
            _FakeAPIError(500),
            _make_completion("recovered"),
        ]

        result = client.chat([{"role": "user", "content": "hi"}])

        assert result.choices[0].message.content == "recovered"
        mock_sleep.assert_called_once()

    @patch("services.agents.openrouter_client.time.sleep")
    def test_raises_after_max_retries(self, mock_sleep):
        client = OpenRouterClient(api_key="test-key", max_retries=2, initial_delay=0.1)
        client._client = MagicMock()
        client._client.chat.completions.create.side_effect = _FakeAPIError(429)

        with pytest.raises(Exception, match="429"):
            client.chat([{"role": "user", "content": "hi"}])

        assert client._client.chat.completions.create.call_count == 3  # 1 + 2 retries

    def test_no_retry_on_400(self):
        client = OpenRouterClient(api_key="test-key", max_retries=2)
        client._client = MagicMock()
        client._client.chat.completions.create.side_effect = _FakeAPIError(400)

        with pytest.raises(Exception, match="400"):
            client.chat([{"role": "user", "content": "hi"}])

        assert client._client.chat.completions.create.call_count == 1

    @patch("services.agents.openrouter_client.time.sleep")
    def test_exponential_backoff_delays(self, mock_sleep):
        client = OpenRouterClient(
            api_key="test-key",
            max_retries=3,
            initial_delay=1.0,
            backoff_factor=2.0,
        )
        client._client = MagicMock()
        client._client.chat.completions.create.side_effect = [
            _FakeAPIError(429),
            _FakeAPIError(429),
            _FakeAPIError(429),
            _make_completion("ok"),
        ]

        client.chat([{"role": "user", "content": "hi"}])

        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays == [1.0, 2.0, 4.0]

    def test_reads_api_key_from_env(self):
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "env-key"}):
            client = OpenRouterClient()
            assert client._api_key == "env-key"
