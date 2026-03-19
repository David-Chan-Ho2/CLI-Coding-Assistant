"""Groq LLM provider implementation."""

import asyncio
import json
from typing import Any, Optional

from groq import Groq

from nexus.llm.provider import LLMProvider, LLMResponse, ToolCall, ToolSchema


class GroqProvider(LLMProvider):
    """Groq API provider for LLM inference."""

    def __init__(
        self,
        api_key: str,
        model: str = "mixtral-8x7b-32768",
        timeout: float = 30.0,
    ):
        """Initialize Groq provider.

        Args:
            api_key: Groq API key.
            model: Model name (default: mixtral-8x7b-32768).
            timeout: Request timeout.

        Raises:
            ValueError: If API key is missing.
        """
        if not api_key:
            raise ValueError("GROQ_API_KEY is required")

        super().__init__(model=model, timeout=timeout)
        self.client = Groq(api_key=api_key)

    async def invoke(
        self,
        prompt: str,
        system: Optional[str] = None,
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> LLMResponse:
        """Invoke Groq API.

        Args:
            prompt: User prompt.
            system: System prompt.
            tools: Available tools.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens.
            conversation_history: Previous messages.

        Returns:
            LLMResponse with content and tool calls.

        Raises:
            TimeoutError: If request times out.
            Exception: If API call fails.
        """
        try:
            # Build messages
            messages = []

            if conversation_history:
                messages.extend(conversation_history)

            if prompt:
                messages.append({"role": "user", "content": prompt})

            # Build kwargs
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }

            if system:
                # Groq doesn't support system parameter in same way
                # Prepend to first user message or add as system role
                messages.insert(0, {"role": "system", "content": system})

            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            # Convert tools to Groq format if provided
            if tools:
                tool_definitions = self._convert_tools(tools)
                kwargs["tools"] = tool_definitions

            # Call Groq API with timeout
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None, lambda: self.client.chat.completions.create(**kwargs)
                ),
                timeout=self.timeout,
            )

            # Extract content and tool calls
            content = response.choices[0].message.content or ""
            tool_calls = self._extract_tool_calls(response)

            # Token counts
            input_tokens = getattr(response.usage, "prompt_tokens", 0)
            output_tokens = getattr(response.usage, "completion_tokens", 0)

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                stop_reason=response.choices[0].finish_reason or "end_turn",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        except asyncio.TimeoutError:
            raise TimeoutError(f"Groq API request timed out after {self.timeout}s")
        except Exception as e:
            raise Exception(f"Groq API error: {str(e)}")

    async def health_check(self) -> bool:
        """Check if Groq API is available.

        Returns:
            True if API is reachable.
        """
        try:
            # Try a simple request
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": "ping"}],
                        max_tokens=1,
                    ),
                ),
                timeout=5.0,
            )
            return True
        except Exception:
            return False

    def _convert_tools(self, tools: list[ToolSchema]) -> list[dict]:
        """Convert tool schemas to Groq format.

        Args:
            tools: Generic tool schemas.

        Returns:
            Groq-formatted tool definitions.
        """
        groq_tools = []
        for tool in tools:
            groq_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            groq_tools.append(groq_tool)
        return groq_tools

    def _extract_tool_calls(self, response: Any) -> list[ToolCall]:
        """Extract tool calls from Groq response.

        Args:
            response: Groq API response.

        Returns:
            List of tool calls.
        """
        tool_calls = []

        if not hasattr(response.choices[0].message, "tool_calls"):
            return tool_calls

        if response.choices[0].message.tool_calls is None:
            return tool_calls

        for tool_call in response.choices[0].message.tool_calls:
            try:
                # Parse arguments
                arguments = json.loads(tool_call.function.arguments)
                tool_calls.append(
                    ToolCall(
                        id=tool_call.id,
                        name=tool_call.function.name,
                        arguments=arguments,
                    )
                )
            except json.JSONDecodeError as e:
                print(f"Failed to parse tool arguments: {e}")
                continue

        return tool_calls
