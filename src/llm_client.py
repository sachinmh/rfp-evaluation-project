"""
Provider-agnostic LLM client for the Evaluation Agent.

Both providers expose the same interface: generate_json(system, user) -> str (raw text,
expected to be JSON). Parsing/validation happens later in validation.py — this layer's
only job is talking to the model.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        ...


class AnthropicClient(LLMClient):
    def __init__(self, api_key: str, model: str = "claude-sonnet-5"):
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model

    def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content


class OpenRouterClient(LLMClient):
    """OpenRouter exposes an OpenAI-compatible API, so we reuse the openai SDK with a
    different base_url. Model names use OpenRouter's "<provider>/<model>" convention,
    e.g. "anthropic/claude-sonnet-5", "openai/gpt-4o-mini", "meta-llama/llama-3.1-70b-instruct".
    We don't force response_format here since not every model routed through OpenRouter
    supports strict JSON mode — validation.py already tolerates non-strict JSON output.
    """

    def __init__(self, api_key: str, model: str = "google/gemma-4-26b-a4b-it:free"):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        self._model = model

    def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content


def get_llm_client(provider: str, api_key: str, model: str | None = None) -> LLMClient:
    provider = provider.lower().strip()
    if provider == "anthropic":
        return AnthropicClient(api_key=api_key, model=model or "claude-sonnet-5")
    if provider == "openai":
        return OpenAIClient(api_key=api_key, model=model or "gpt-4o-mini")
    if provider == "openrouter":
        return OpenRouterClient(api_key=api_key, model=model or "openai/gpt-4o-mini")
    raise ValueError(f"Unsupported LLM provider: {provider!r}. Use 'anthropic', 'openai', or 'openrouter'.")
