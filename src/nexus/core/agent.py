"""Agentic loop orchestrator for NEXUS."""

import asyncio
import json
from typing import Optional

from nexus.core.error_handler import CircuitBreaker, RetryManager, ErrorCategory
from nexus.core.session import SessionContext
from nexus.core.types import ExecutionResult, ToolCall, ToolResult, RiskLevel
from nexus.llm.provider import LLMProvider, LLMResponse, ToolSchema


class Agent:
    """Autonomous agent orchestrator."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        session: SessionContext,
        tool_executor: Optional["ToolExecutor"] = None,
        max_iterations: Optional[int] = None,
    ):
        """Initialize agent.

        Args:
            llm_provider: LLM provider for reasoning.
            session: Session context for conversation.
            tool_executor: Optional tool executor.
            max_iterations: Max iterations (overrides session default).
        """
        self.llm_provider = llm_provider
        self.session = session
        self.tool_executor = tool_executor

        if max_iterations:
            self.session.max_iterations = max_iterations

        # Error handling
        self.retry_manager = RetryManager(max_retries=3, backoff_base=1.0)
        self.circuit_breaker = CircuitBreaker("llm_provider", failure_threshold=3)

    async def execute(self, user_input: str) -> ExecutionResult:
        """Execute agent loop until completion.

        Args:
            user_input: The user's instruction.

        Returns:
            ExecutionResult with final response and metadata.
        """
        # Add user message to session
        self.session.add_user_message(user_input)

        result = ExecutionResult(
            success=False,
            message="",
            iterations=0,
            tool_calls_made=0,
            error=None,
            error_category=None,
        )

        try:
            # Main agentic loop
            while not self.session.reached_max_iterations():
                self.session.increment_iteration()
                result.iterations += 1

                # Step 1: Get reasoning from LLM
                llm_response = await self._invoke_llm()

                # Step 2: Process LLM response
                if llm_response.tool_calls:
                    # Tool calls detected
                    result.tool_calls_made += len(llm_response.tool_calls)

                    # Save assistant message with tool calls before executing
                    core_tool_calls = [
                        ToolCall(id=tc.id, name=tc.name, arguments=tc.arguments)
                        for tc in llm_response.tool_calls
                    ]
                    self.session.add_assistant_message(
                        llm_response.content, core_tool_calls
                    )

                    # Execute tools
                    tool_results = await self._execute_tool_calls(
                        llm_response.tool_calls
                    )

                    # Add tool results to session
                    for tool_result in tool_results:
                        self.session.add_tool_result(
                            tool_result.tool_call_id, tool_result
                        )

                    # Continue loop with tool results in context
                    continue

                else:
                    # No tool calls - LLM concluded
                    self.session.add_assistant_message(llm_response.content)
                    result.success = True
                    result.message = llm_response.content
                    result.final_response = llm_response.content
                    break

            # Check if loop ended due to max iterations
            if not result.success and self.session.reached_max_iterations():
                result.success = False
                result.message = (
                    f"Agent reached max iterations ({self.session.max_iterations}). "
                    "Task may be incomplete."
                )
                result.error = result.message
                result.error_category = ErrorCategory.UNKNOWN

            return result

        except Exception as e:
            result.success = False
            result.message = f"Agent execution failed: {str(e)}"
            result.error = str(e)
            result.error_category = ErrorCategory.UNKNOWN
            return result

    async def _invoke_llm(self) -> LLMResponse:
        """Invoke the LLM with current context.

        Returns:
            LLM response.

        Raises:
            Exception: If LLM invocation fails.
        """
        try:
            # Build context messages, preserving tool call/result structure
            context_messages = []
            for msg in self.session.get_context_messages():
                if msg.role.value == "user":
                    context_messages.append({"role": "user", "content": msg.content})
                elif msg.role.value == "assistant":
                    if msg.tool_calls:
                        context_messages.append({
                            "role": "assistant",
                            "content": msg.content or "",
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.name,
                                        "arguments": json.dumps(tc.arguments),
                                    },
                                }
                                for tc in msg.tool_calls
                            ],
                        })
                        for tr in msg.tool_results:
                            context_messages.append({
                                "role": "tool",
                                "tool_call_id": tr.tool_call_id,
                                "content": tr.output,
                            })
                    else:
                        context_messages.append({
                            "role": "assistant",
                            "content": msg.content,
                        })

            # Build tool schemas if executor available
            tool_schemas = []
            if self.tool_executor:
                tool_schemas = self.tool_executor.get_tool_schemas()

            # Invoke LLM with retry and circuit breaker
            response = await self.circuit_breaker.call(
                self.retry_manager.execute_with_retry,
                self.llm_provider.invoke,
                categorize_error=self._categorize_llm_error,
                prompt="",  # Using conversation history instead
                system=self.session.get_system_prompt(),
                tools=tool_schemas if tool_schemas else None,
                temperature=0.7,
                conversation_history=context_messages,
            )

            return response

        except Exception as e:
            print(f"❌ LLM invocation failed: {e}")
            raise

    async def _execute_tool_calls(
        self, tool_calls: list[ToolCall]
    ) -> list[ToolResult]:
        """Execute tool calls.

        Args:
            tool_calls: List of tool calls from LLM.

        Returns:
            List of tool results.
        """
        if not self.tool_executor:
            # No executor, return dummy results
            return [
                ToolResult(
                    tool_call_id=tc.id,
                    tool_name=tc.name,
                    output="Tool executor not available",
                    success=False,
                    error="No tool executor configured",
                )
                for tc in tool_calls
            ]

        results = []
        for tool_call in tool_calls:
            try:
                # Check if confirmation needed
                risk = getattr(tool_call, "risk_level", RiskLevel.MEDIUM)
                risk_value = risk.value if hasattr(risk, "value") else str(risk)
                should_confirm = self.session.should_confirm_tool(
                    tool_call.name, risk_value
                )

                if should_confirm:
                    # In real implementation, prompt user
                    print(
                        f"⚠️  Tool '{tool_call.name}' requires confirmation "
                        f"(risk: {tool_call.risk_level.value})"
                    )
                    # For now, auto-confirm in non-interactive mode
                    confirmed = True
                else:
                    confirmed = True

                if not confirmed:
                    result = ToolResult(
                        tool_call_id=tool_call.id,
                        tool_name=tool_call.name,
                        output="User declined execution",
                        success=False,
                        error="User did not confirm",
                    )
                else:
                    # Execute tool
                    result = await self.tool_executor.execute(tool_call)

                results.append(result)

            except Exception as e:
                result = ToolResult(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    output=str(e),
                    success=False,
                    error=str(e),
                )
                results.append(result)

        return results

    def _categorize_llm_error(self, exception: Exception) -> ErrorCategory:
        """Categorize LLM errors for retry logic.

        Args:
            exception: The exception.

        Returns:
            Error category.
        """
        error_str = str(exception).lower()

        if "timeout" in error_str:
            return ErrorCategory.TRANSIENT

        if "429" in error_str or "rate limit" in error_str:
            return ErrorCategory.RATE_LIMIT

        if "api_error" in error_str or "authentication" in error_str:
            return ErrorCategory.VALIDATION_ERROR

        if "unavailable" in error_str or "connection" in error_str:
            return ErrorCategory.PROVIDER_UNAVAILABLE

        return ErrorCategory.UNKNOWN


class ToolExecutor:
    """Executor for tool calls (stub for Phase 3)."""

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call.

        Args:
            tool_call: The tool call to execute.

        Returns:
            Tool result.
        """
        raise NotImplementedError("Tool executor not implemented in Phase 2")

    def get_tool_schemas(self) -> list[ToolSchema]:
        """Get available tool schemas.

        Returns:
            List of tool schemas.
        """
        return []
