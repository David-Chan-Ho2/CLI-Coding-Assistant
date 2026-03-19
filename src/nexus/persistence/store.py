"""Session persistence for NEXUS."""

import json
import pathlib

from nexus.config.settings import settings
from nexus.core.session import SessionContext


class SessionStore:
    """Saves and loads sessions to/from disk."""

    def __init__(self, session_dir: str = None):
        self.session_dir = pathlib.Path(session_dir or settings.SESSION_DIR)
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def save(self, session: SessionContext) -> None:
        """Serialize and write a session to disk."""
        path = self.session_dir / f"{session.session_id}.json"
        path.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")

    def load(self, session_id: str) -> SessionContext:
        """Load and reconstruct a session from disk.

        Raises:
            FileNotFoundError: If the session does not exist.
        """
        path = self.session_dir / f"{session_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return SessionContext.from_dict(data)

    def exists(self, session_id: str) -> bool:
        """Return True if a session file exists for the given ID."""
        return (self.session_dir / f"{session_id}.json").exists()

    def list_sessions(self) -> list[dict]:
        """Return summary metadata for all saved sessions, newest first."""
        sessions = []
        for path in sorted(
            self.session_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                meta = data.get("metadata", {})
                sessions.append({
                    "session_id": data["session_id"],
                    "created_at": meta.get("created_at", ""),
                    "updated_at": meta.get("updated_at", ""),
                    "message_count": len(data.get("messages", [])),
                    "status": meta.get("status", "unknown"),
                })
            except Exception:
                continue
        return sessions

    def delete(self, session_id: str) -> bool:
        """Delete a session file. Returns True if it existed."""
        path = self.session_dir / f"{session_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False
