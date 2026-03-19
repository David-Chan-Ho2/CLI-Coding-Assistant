"""Ollama LLM provider implementation for local inference."""

import asyncio
import json
from typing import Any, Optional

import httpx

from nexus.llm.provider import LLMProvider, LLMResponse, ToolCall, ToolSchema


class OllamaProvider(LLMProvider):
    """Ollama provider for local LLM inference."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mistral",
        timeout: float = 120.0,
    ):
        """Initialize Ollama provider.

        Args:
            base_url: Ollama server URL.
            model: Model name (default: mistral).
            timeout: Request timeout (default: 120s for local inference).
        """
        super().__init__(model=model, timeout=timeout)
        self.base_url = base_url.rstrip("/")

    async def invoke(
        self,
        prompt: str,
        system: Optional[str] = None,
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> LLMResponse:
        """Invoke Ollama API.

        Args:
            prompt: User prompt.
            system: System prompt.
            tools: Available tools (not supported by Ollama yet).
            temperature: Sampling temperature.
            max_tokens: Maximum tokens.
            conversation_history: Previous messages.

        Returns:
            LLMResponse with content.

        Raises:
            TimeoutError: If request times out.
            Exception: If API call fails.
        """
        try:
            # Build messages
            messages = []

            if system:
                messages.append({"role": "system", "content": system})

            if conversation_history:
                messages.extend(conversation_history)

            if prompt:
                messages.append({"role": "user", "content": prompt})

            # Note: Ollama doesn't support tool calling yet (as of 0.6.1)
            # Tools are ignored for local inference
            if tools:
                print(
                    "⚠️  Note: Ollama does not support tool calling. "
                    "Tools will be ignored."
                )

            # Build request payload
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                },
            }

            if max_tokens:
                payload["options"]["num_predict"] = max_tokens

            # Call Ollama API
            async with httpx.AsyncClient(timeout=None) as client:
                response = await asyncio.wait_for(
                    client.post(
                        f"{self.base_url}/api/chat",
                        json=payload,
                        timeout=self.timeout,
                    ),
                    timeout=self.timeout + 5.0,
                )

                if response.status_code != 200:
                    raise Exception(
                        f"Ollama API error: {response.status_code} {response.text}"
                    )

                data = response.json()
                content = data.get("message", {}).get("content", "")

                # Ollama doesn't provide token counts, estimate
                input_tokens = len(prompt.split()) // 3  # Very rough estimate
                output_tokens = len(content.split()) // 3

                return LLMResponse(
                    content=content,
                    tool_calls=[],  # Ollama doesn't support tool calling
                    stop_reason="end_turn",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Ollama request timed out after {self.timeout}s. "
                f"Is Ollama running at {self.base_url}?"
            )
        except Exception as e:
            raise Exception(f"Ollama error: {str(e)}")

    async def health_check(self) -> bool:
        """Check if Ollama is running and ready.

        Returns:
            True if Ollama is reachable.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    def _convert_tools(self, tools: list[ToolSchema]) -> list[dict]:
        """Ollama doesn't support tools.

        Args:
            tools: Tool schemas (ignored).

        Returns:
            Empty list.
        """
        return []

    def _extract_tool_calls(self, response: Any) -> list[ToolCall]:
        """Ollama doesn't support tool calls.

        Args:
            response: API response.

        Returns:
            Empty list.
        """
        return []
