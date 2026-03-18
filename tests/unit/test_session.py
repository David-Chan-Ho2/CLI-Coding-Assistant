"""Tests for session management."""

import pytest

from nexus.core.session import SessionContext
from nexus.core.types import ExecutionMode, MessageRole


def test_session_creation():
    """Test that a session can be created."""
    session = SessionContext()
    assert session.session_id is not None
    assert len(session.session_id) > 0
    assert session.metadata.execution_mode == ExecutionMode.AUTO


def test_add_user_message():
    """Test that user messages can be added."""
    session = SessionContext()
    message = session.add_user_message("Hello, NEXUS!")

    assert message.role == MessageRole.USER
    assert message.content == "Hello, NEXUS!"
    assert len(session.messages) == 1


def test_add_assistant_message():
    """Test that assistant messages can be added."""
    session = SessionContext()
    message = session.add_assistant_message("I'm here to help!")

    assert message.role == MessageRole.ASSISTANT
    assert message.content == "I'm here to help!"
    assert len(session.messages) == 1


def test_conversation_flow():
    """Test a basic conversation flow."""
    session = SessionContext()

    # Add user message
    session.add_user_message("Write a Python script")
    assert len(session.messages) == 1

    # Add assistant response
    session.add_assistant_message("I'll create a script for you.")
    assert len(session.messages) == 2

    # Get conversation
    msgs = session.get_context_messages()
    assert len(msgs) == 2
    assert msgs[0].role == MessageRole.USER
    assert msgs[1].role == MessageRole.ASSISTANT


def test_execution_mode_toggle():
    """Test execution mode changes."""
    session = SessionContext(execution_mode=ExecutionMode.AUTO)
    assert session.metadata.execution_mode == ExecutionMode.AUTO

    session.set_execution_mode(ExecutionMode.MANUAL)
    assert session.metadata.execution_mode == ExecutionMode.MANUAL

    session.set_execution_mode(ExecutionMode.CONFIRMATION)
    assert session.metadata.execution_mode == ExecutionMode.CONFIRMATION


def test_iteration_counting():
    """Test iteration counter."""
    session = SessionContext()
    assert session.iteration_count == 0
    assert not session.reached_max_iterations()

    for _ in range(5):
        session.increment_iteration()

    assert session.iteration_count == 5
    assert not session.reached_max_iterations()

    for _ in range(10):
        session.increment_iteration()

    assert session.reached_max_iterations()


def test_session_serialization():
    """Test session can be serialized to dict."""
    session = SessionContext()
    session.add_user_message("Test message")

    serialized = session.to_dict()
    assert "session_id" in serialized
    assert "messages" in serialized
    assert "metadata" in serialized
    assert len(serialized["messages"]) == 1
