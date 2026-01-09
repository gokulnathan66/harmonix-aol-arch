"""
LLM Adapter - Pluggable Language Model Integration

This module provides adapters for different LLM providers, allowing
services to swap between providers without changing service logic.
"""

import asyncio
import logging
import os
from abc import abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

try:
    import aiohttp
except ImportError:
    aiohttp = None

from integration.base import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationResult,
    IntegrationError,
)

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig(IntegrationConfig):
    """Configuration specific to LLM integrations"""

    model: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 1.0
    stop_sequences: List[str] = field(default_factory=list)


@dataclass
class LLMResponse:
    """Structured response from LLM"""

    content: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def prompt_tokens(self) -> int:
        return self.usage.get("prompt_tokens", 0)

    @property
    def completion_tokens(self) -> int:
        return self.usage.get("completion_tokens", 0)

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)


class LLMAdapter(BaseIntegration):
    """
    Abstract base class for LLM adapters.

    Provides a unified interface for different LLM providers.
    Subclass this to create provider-specific adapters.
    """

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.llm_config = config

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate a completion for the given prompt.

        Args:
            prompt: User prompt/message
            system_prompt: Optional system prompt
            temperature: Override temperature
            max_tokens: Override max tokens
            **kwargs: Provider-specific arguments

        Returns:
            LLMResponse with generated content
        """
        result = await self.execute(
            action="complete",
            payload={
                "prompt": prompt,
                "system_prompt": system_prompt,
                "temperature": temperature or self.llm_config.temperature,
                "max_tokens": max_tokens or self.llm_config.max_tokens,
                **kwargs,
            },
        )

        if not result.success:
            raise IntegrationError(
                result.error or "Completion failed",
                integration_name=self.name,
                retryable=True,
            )

        return result.data

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate a chat completion for the given messages.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Override temperature
            max_tokens: Override max tokens
            **kwargs: Provider-specific arguments

        Returns:
            LLMResponse with generated content
        """
        result = await self.execute(
            action="chat",
            payload={
                "messages": messages,
                "temperature": temperature or self.llm_config.temperature,
                "max_tokens": max_tokens or self.llm_config.max_tokens,
                **kwargs,
            },
        )

        if not result.success:
            raise IntegrationError(
                result.error or "Chat completion failed",
                integration_name=self.name,
                retryable=True,
            )

        return result.data

    @abstractmethod
    async def _do_execute(
        self, action: str, payload: Dict[str, Any], **kwargs
    ) -> LLMResponse:
        """Provider-specific execution"""
        pass


class OpenAIAdapter(LLMAdapter):
    """
    OpenAI API adapter.

    Supports GPT-3.5, GPT-4, and other OpenAI models.
    """

    def __init__(self, config: LLMConfig = None, **kwargs):
        if config is None:
            config = LLMConfig(
                name="openai",
                endpoint=kwargs.get(
                    "endpoint",
                    os.getenv("OPENAI_API_ENDPOINT", "https://api.openai.com/v1"),
                ),
                api_key=kwargs.get("api_key", os.getenv("OPENAI_API_KEY")),
                model=kwargs.get("model", "gpt-4o"),
                timeout=kwargs.get("timeout", 60),
            )
        super().__init__(config)
        self._client = None

    async def _do_initialize(self):
        """Initialize OpenAI client"""
        try:
            import aiohttp

            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                }
            )
        except ImportError:
            raise IntegrationError(
                "aiohttp required for OpenAI adapter", integration_name=self.name
            )

    async def _do_shutdown(self):
        """Close HTTP session"""
        if hasattr(self, "_session") and self._session:
            await self._session.close()

    async def _do_health_check(self) -> bool:
        """Check OpenAI API availability"""
        try:
            async with self._session.get(
                f"{self.config.endpoint}/models", timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def _do_execute(
        self, action: str, payload: Dict[str, Any], **kwargs
    ) -> LLMResponse:
        """Execute OpenAI API call"""
        import aiohttp

        if action == "complete":
            return await self._complete(payload)
        elif action == "chat":
            return await self._chat(payload)
        else:
            raise IntegrationError(
                f"Unknown action: {action}", integration_name=self.name
            )

    async def _complete(self, payload: Dict[str, Any]) -> LLMResponse:
        """Execute completion request"""
        import aiohttp

        messages = []
        if payload.get("system_prompt"):
            messages.append({"role": "system", "content": payload["system_prompt"]})
        messages.append({"role": "user", "content": payload["prompt"]})

        body = {
            "model": self.llm_config.model,
            "messages": messages,
            "temperature": payload.get("temperature", self.llm_config.temperature),
            "max_tokens": payload.get("max_tokens", self.llm_config.max_tokens),
        }

        async with self._session.post(
            f"{self.config.endpoint}/chat/completions",
            json=body,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout),
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise IntegrationError(
                    f"OpenAI API error: {error}",
                    integration_name=self.name,
                    error_code=str(resp.status),
                    retryable=resp.status >= 500,
                )

            data = await resp.json()
            choice = data["choices"][0]

            return LLMResponse(
                content=choice["message"]["content"],
                model=data["model"],
                usage=data.get("usage", {}),
                finish_reason=choice.get("finish_reason", "stop"),
            )

    async def _chat(self, payload: Dict[str, Any]) -> LLMResponse:
        """Execute chat completion request"""
        import aiohttp

        body = {
            "model": self.llm_config.model,
            "messages": payload["messages"],
            "temperature": payload.get("temperature", self.llm_config.temperature),
            "max_tokens": payload.get("max_tokens", self.llm_config.max_tokens),
        }

        async with self._session.post(
            f"{self.config.endpoint}/chat/completions",
            json=body,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout),
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise IntegrationError(
                    f"OpenAI API error: {error}",
                    integration_name=self.name,
                    error_code=str(resp.status),
                    retryable=resp.status >= 500,
                )

            data = await resp.json()
            choice = data["choices"][0]

            return LLMResponse(
                content=choice["message"]["content"],
                model=data["model"],
                usage=data.get("usage", {}),
                finish_reason=choice.get("finish_reason", "stop"),
            )


class AnthropicAdapter(LLMAdapter):
    """
    Anthropic Claude API adapter.

    Supports Claude 3 models.
    """

    def __init__(self, config: LLMConfig = None, **kwargs):
        if config is None:
            config = LLMConfig(
                name="anthropic",
                endpoint=kwargs.get(
                    "endpoint",
                    os.getenv("ANTHROPIC_API_ENDPOINT", "https://api.anthropic.com/v1"),
                ),
                api_key=kwargs.get("api_key", os.getenv("ANTHROPIC_API_KEY")),
                model=kwargs.get("model", "claude-3-sonnet-20240229"),
                timeout=kwargs.get("timeout", 60),
            )
        super().__init__(config)
        self._session = None

    async def _do_initialize(self):
        """Initialize Anthropic client"""
        import aiohttp

        self._session = aiohttp.ClientSession(
            headers={
                "x-api-key": self.config.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
        )

    async def _do_shutdown(self):
        """Close HTTP session"""
        if self._session:
            await self._session.close()

    async def _do_health_check(self) -> bool:
        """Check Anthropic API availability"""
        # Anthropic doesn't have a health endpoint, so we just check connectivity
        return True

    async def _do_execute(
        self, action: str, payload: Dict[str, Any], **kwargs
    ) -> LLMResponse:
        """Execute Anthropic API call"""
        import aiohttp

        if action in ("complete", "chat"):
            return await self._messages(payload)
        else:
            raise IntegrationError(
                f"Unknown action: {action}", integration_name=self.name
            )

    async def _messages(self, payload: Dict[str, Any]) -> LLMResponse:
        """Execute messages API request"""
        import aiohttp

        # Build messages
        if "messages" in payload:
            messages = payload["messages"]
        else:
            messages = [{"role": "user", "content": payload["prompt"]}]

        body = {
            "model": self.llm_config.model,
            "messages": messages,
            "max_tokens": payload.get("max_tokens", self.llm_config.max_tokens),
        }

        # Add system prompt if provided
        if payload.get("system_prompt"):
            body["system"] = payload["system_prompt"]

        async with self._session.post(
            f"{self.config.endpoint}/messages",
            json=body,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout),
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise IntegrationError(
                    f"Anthropic API error: {error}",
                    integration_name=self.name,
                    error_code=str(resp.status),
                    retryable=resp.status >= 500,
                )

            data = await resp.json()

            return LLMResponse(
                content=data["content"][0]["text"],
                model=data["model"],
                usage={
                    "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
                    "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
                    "total_tokens": (
                        data.get("usage", {}).get("input_tokens", 0)
                        + data.get("usage", {}).get("output_tokens", 0)
                    ),
                },
                finish_reason=data.get("stop_reason", "stop"),
            )


def create_llm_adapter(provider: str, **kwargs) -> LLMAdapter:
    """
    Factory function to create LLM adapters.

    Args:
        provider: Provider name ("openai", "anthropic", etc.)
        **kwargs: Provider-specific configuration

    Returns:
        Configured LLM adapter
    """
    adapters = {
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
    }

    if provider not in adapters:
        raise ValueError(f"Unknown LLM provider: {provider}")

    return adapters[provider](**kwargs)
