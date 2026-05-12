"""
AI/LLM Provider module.

Provides a unified interface for multiple LLM providers with fallback support.
"""

from abc import ABC, abstractmethod
from typing import Optional
from loguru import logger

from openai import AsyncOpenAI


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Display name of the provider."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Default model name."""
        pass

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """Send a chat completion request."""
        pass

    async def test_connection(self) -> bool:
        """Test if the provider connection is working."""
        try:
            response = await self.chat(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
            )
            return bool(response)
        except Exception:
            return False


class OpenAICompatibleProvider(LLMProvider):
    """
    Provider for OpenAI-compatible APIs.

    Works with OpenAI, DeepSeek, Qwen, Ollama, SiliconFlow, and other compatible APIs.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        display_name: str = "OpenAI Compatible",
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._display_name = display_name
        self._client = AsyncOpenAI(api_key=api_key, base_url=self._base_url)

    @property
    def name(self) -> str:
        return self._display_name

    @property
    def model_name(self) -> str:
        return self._model_name

    async def chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """Send a chat completion request."""
        logger.debug(f"LLM request: model={model or self._model_name}, messages={len(messages)}")
        response = await self._client.chat.completions.create(
            model=model or self._model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        logger.debug(f"LLM response: {len(content)} chars")
        return content


class ModelManager:
    """
    Manager for multiple LLM providers.

    Handles provider registration, selection, and automatic fallback.
    """

    def __init__(self):
        self._providers: dict[str, LLMProvider] = {}
        self._default_id: Optional[str] = None
        self._priority: dict[str, int] = {}

    def register(
        self,
        provider_id: str,
        provider: LLMProvider,
        is_default: bool = False,
        priority: int = 0,
    ) -> None:
        """Register a provider instance."""
        self._providers[provider_id] = provider
        self._priority[provider_id] = priority
        if is_default or self._default_id is None:
            self._default_id = provider_id
        logger.info(f"Registered LLM provider: {provider.name} (id={provider_id}, default={is_default})")

    def register_from_config(self, config: dict) -> str:
        """
        Register a provider from a database config dict.

        Args:
            config: Dict with keys: name, api_key_decrypted, base_url, model_name, is_default, priority

        Returns:
            Provider ID.
        """
        provider_id = f"provider_{config['name']}_{id(config)}"
        provider = OpenAICompatibleProvider(
            api_key=config["api_key_decrypted"],
            base_url=config["base_url"],
            model_name=config["model_name"],
            display_name=config["name"],
        )
        self.register(
            provider_id=provider_id,
            provider=provider,
            is_default=config.get("is_default", False),
            priority=config.get("priority", 0),
        )
        return provider_id

    def get(self, provider_id: Optional[str] = None) -> LLMProvider:
        """Get a provider by ID, falling back to default."""
        if provider_id and provider_id in self._providers:
            return self._providers[provider_id]
        if self._default_id and self._default_id in self._providers:
            return self._providers[self._default_id]
        if self._providers:
            return next(iter(self._providers.values()))
        raise ValueError("No LLM provider registered. Please configure a model first.")

    @property
    def has_providers(self) -> bool:
        return len(self._providers) > 0

    @property
    def provider_list(self) -> list[dict]:
        """Return list of registered providers info."""
        return [
            {
                "id": pid,
                "name": p.name,
                "model": p.model_name,
                "is_default": pid == self._default_id,
                "priority": self._priority.get(pid, 0),
            }
            for pid, p in self._providers.items()
        ]

    async def chat(
        self,
        messages: list[dict],
        provider_id: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """
        Send a chat request with automatic fallback on failure.
        """
        # Build ordered provider list
        ordered = sorted(self._providers.keys(), key=lambda x: -self._priority.get(x, 0))
        if provider_id and provider_id in ordered:
            ordered.remove(provider_id)
            ordered.insert(0, provider_id)

        errors = []
        for pid in ordered:
            try:
                provider = self._providers[pid]
                return await provider.chat(
                    messages=messages, model=model,
                    temperature=temperature, max_tokens=max_tokens,
                )
            except Exception as e:
                errors.append(f"{pid}: {e}")
                logger.warning(f"LLM provider {pid} failed: {e}, trying next...")
                continue

        raise Exception(f"All LLM providers failed: {errors}")


# ─── Global singleton ───
_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get or create the global ModelManager singleton."""
    global _manager
    if _manager is None:
        _manager = ModelManager()
    return _manager
