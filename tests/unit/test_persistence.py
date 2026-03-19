"""Unit tests for session persistence."""

import pytest

from nexus.core.session import SessionContext
from nexus.core.types import ExecutionMode, MessageRole
from nexus.persistence.store import SessionStore


@pytest.fixture
def store(tmp_path):
    """SessionStore backed by a temp directory."""
    return SessionStore(session_dir=str(tmp_path))


@pytest.fixture
def sample_session():
    """A session with some conversation history."""
    session = SessionContext()
    session.add_user_message("Hello NEXUS")
    session.add_assistant_message("Hello! How can I help?")
    session.add_user_message("Write a script")
    return session


# ---------------------------------------------------------------------------
# from_dict round-trip
# ---------------------------------------------------------------------------

def test_session_round_trip_empty():
    """An empty session survives serialize → deserialize."""
    session = SessionContext()
    restored = SessionContext.from_dict(session.to_dict())

    assert restored.session_id == session.session_id
    assert len(restored.messages) == 0
    assert restored.metadata.execution_mode == session.metadata.execution_mode


def test_session_round_trip_with_messages(sample_session):
    """Message content and roles are preserved through round-trip."""
    restored = SessionContext.from_dict(sample_session.to_dict())

    assert len(restored.messages) == len(sample_session.messages)
    for orig, rest in zip(sample_session.messages, restored.messages):
        assert rest.role == orig.role
        assert rest.content == orig.content
        assert rest.id == orig.id


def test_session_round_trip_metadata(sample_session):
    """Metadata fields are preserved through round-trip."""
    sample_session.set_execution_mode(ExecutionMode.MANUAL)
    restored = SessionContext.from_dict(sample_session.to_dict())

    assert restored.metadata.execution_mode == ExecutionMode.MANUAL
    assert restored.metadata.created_at == sample_session.metadata.created_at
    assert restored.metadata.tool_calls_count == sample_session.metadata.tool_calls_count


def test_session_round_trip_iteration_count():
    """Iteration count is preserved through round-trip."""
    session = SessionContext()
    session.increment_iteration()
    session.increment_iteration()

    restored = SessionContext.from_dict(session.to_dict())
    assert restored.iteration_count == 2


# ---------------------------------------------------------------------------
# SessionStore.save / load
# ---------------------------------------------------------------------------

def test_store_save_creates_file(store, sample_session):
    """save() writes a JSON file named after the session ID."""
    store.save(sample_session)
    path = store.session_dir / f"{sample_session.session_id}.json"
    assert path.exists()


def test_store_load_restores_session(store, sample_session):
    """load() reconstructs the session with correct messages."""
    store.save(sample_session)
    restored = store.load(sample_session.session_id)

    assert restored.session_id == sample_session.session_id
    assert len(restored.messages) == len(sample_session.messages)
    assert restored.messages[0].content == "Hello NEXUS"


def test_store_load_missing_raises(store):
    """Loading a non-existent session raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        store.load("00000000-0000-0000-0000-000000000000")


def test_store_save_overwrites(store, sample_session):
    """Saving the same session twice updates the file."""
    store.save(sample_session)
    sample_session.add_user_message("New message")
    store.save(sample_session)

    restored = store.load(sample_session.session_id)
    assert len(restored.messages) == len(sample_session.messages)


# ---------------------------------------------------------------------------
# SessionStore.exists
# ---------------------------------------------------------------------------

def test_store_exists_true(store, sample_session):
    """exists() returns True after saving."""
    store.save(sample_session)
    assert store.exists(sample_session.session_id) is True


def test_store_exists_false(store):
    """exists() returns False for an unknown session ID."""
    assert store.exists("nonexistent-id") is False


# ---------------------------------------------------------------------------
# SessionStore.list_sessions
# ---------------------------------------------------------------------------

def test_store_list_empty(store):
    """list_sessions() returns an empty list when no sessions are saved."""
    assert store.list_sessions() == []


def test_store_list_returns_all(store):
    """list_sessions() returns one entry per saved session."""
    s1 = SessionContext()
    s2 = SessionContext()
    store.save(s1)
    store.save(s2)

    listed = store.list_sessions()
    ids = [s["session_id"] for s in listed]
    assert s1.session_id in ids
    assert s2.session_id in ids


def test_store_list_has_correct_fields(store, sample_session):
    """list_sessions() entries contain expected metadata fields."""
    store.save(sample_session)
    listed = store.list_sessions()

    assert len(listed) == 1
    entry = listed[0]
    assert "session_id" in entry
    assert "created_at" in entry
    assert "updated_at" in entry
    assert "message_count" in entry
    assert entry["message_count"] == len(sample_session.messages)


# ---------------------------------------------------------------------------
# SessionStore.delete
# ---------------------------------------------------------------------------

def test_store_delete_existing(store, sample_session):
    """delete() removes the file and returns True."""
    store.save(sample_session)
    result = store.delete(sample_session.session_id)

    assert result is True
    assert not store.exists(sample_session.session_id)


def test_store_delete_nonexistent(store):
    """delete() returns False when the session doesn't exist."""
    result = store.delete("nonexistent-id")
    assert result is False
