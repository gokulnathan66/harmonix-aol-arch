"""
Integration Module - Pluggable Tools and External Hooks

This module provides abstractions for integrating external APIs, LLMs,
and tools into AOL services while maintaining loose coupling.
"""
from integration.base import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationResult,
    IntegrationError
)
from integration.llm_adapter import (
    LLMAdapter,
    LLMConfig,
    LLMResponse,
    OpenAIAdapter,
    AnthropicAdapter
)
from integration.tool_registry import (
    ToolRegistry,
    Tool,
    ToolResult
)

__all__ = [
    'BaseIntegration',
    'IntegrationConfig',
    'IntegrationResult',
    'IntegrationError',
    'LLMAdapter',
    'LLMConfig',
    'LLMResponse',
    'OpenAIAdapter',
    'AnthropicAdapter',
    'ToolRegistry',
    'Tool',
    'ToolResult'
]

