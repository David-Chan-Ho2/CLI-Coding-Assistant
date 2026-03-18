"""NEXUS configuration and settings."""

import os
from typing import Optional


class Settings:
    """Application settings."""

    # App settings
    APP_NAME = "NEXUS"
    APP_VERSION = "0.1.0"
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"

    # LLM settings
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "mixtral-8x7b-32768")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")

    # Tavily API
    TAVILY_API_KEY: Optional[str] = os.getenv("TAVILY_API_KEY")

    # Execution settings
    EXECUTION_MODE = os.getenv("EXECUTION_MODE", "auto")
    MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))
    MAX_CONTEXT_MESSAGES = int(os.getenv("MAX_CONTEXT_MESSAGES", "20"))

    # Paths
    SESSION_DIR = os.getenv("SESSION_DIR", "./nexus_sessions")
    RAG_DB_DIR = os.getenv("RAG_DB_DIR", "./rag/chroma_db")
    LOG_DIR = os.getenv("LOG_DIR", "./logs")

    # Timeouts
    LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30.0"))
    TOOL_TIMEOUT = float(os.getenv("TOOL_TIMEOUT", "60.0"))
    MCP_TIMEOUT = float(os.getenv("MCP_TIMEOUT", "10.0"))

    # Retry settings
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_BACKOFF_BASE = float(os.getenv("RETRY_BACKOFF_BASE", "1.0"))

    # Embedding settings
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    USE_LOCAL_EMBEDDINGS = os.getenv("USE_LOCAL_EMBEDDINGS", "true").lower() == "true"

    @classmethod
    def validate(cls) -> None:
        """Validate settings."""
        # Create necessary directories
        os.makedirs(cls.SESSION_DIR, exist_ok=True)
        os.makedirs(cls.RAG_DB_DIR, exist_ok=True)
        os.makedirs(cls.LOG_DIR, exist_ok=True)

        # Warn if critical keys are missing
        if not cls.GROQ_API_KEY:
            print("⚠️  Warning: GROQ_API_KEY not set. Will fallback to Ollama.")


settings = Settings()
