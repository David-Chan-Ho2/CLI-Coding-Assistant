# NEXUS - Autonomous CLI Coding Assistant

**NEXUS** (Neural Executive Xperiment for Unified Software automation) is an autonomous command-line AI coding assistant. Given natural language instructions, NEXUS reasons about your codebase, autonomously reads, edits, and executes code to complete tasks.

> **Tagline**: Autonomous code execution, intelligent reasoning, persistent context

## Features

- ⚡ **Agentic Reasoning** - LLM-driven decision making with multi-turn interactions
- 🛠️ **Multi-Tool Integration** - File operations, web search, semantic documentation retrieval
- 🔄 **Automatic Error Recovery** - Intelligent retry logic, provider failover, graceful degradation
- 💾 **Session Persistence** - Save and resume conversations across sessions
- 🎯 **HyDE-Powered RAG** - Hypothetical Document Embeddings for superior semantic search
- 🔌 **MCP Integration** - Connects to Filesystem, Tavily (web search), and custom RAG servers
- ⚙️ **Multi-Provider Support** - Groq (primary) + Ollama (local fallback)
- 🎮 **Dual Execution Modes** - Auto-execute safe operations or require manual confirmation

## Quick Start

### Prerequisites

- Python 3.12 or higher
- [Groq API Key](https://console.groq.com) (optional - Ollama works offline)
- [uv](https://docs.astral.sh/uv/) - Modern Python package manager (optional, pip works too)

### Installation

1. Clone the repository:

```bash
git clone https://github.com/David-Chan-Ho2/nexus-cli.git
cd nexus-cli
```

2. Create virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
# Using pip
pip install -e ".[dev]"

# Or using uv
uv pip install -e ".[dev]"
```

4. Configure environment:

```bash
cp .env.example .env
# Edit .env with your API keys
```

5. Start NEXUS:

```bash
nexus
```

## Usage

Once NEXUS starts, you'll see an interactive REPL:

```
⟳ NEXUS - Ready for instructions
→ You: write a python script that prints hello world

🔧 Tool: write_file
📄 Created: hello_world.py

⟳ NEXUS: I've created a Python script that prints "Hello, World!" at hello_world.py.
```

### Commands

- `/help` - Show available commands
- `/clear` - Clear conversation history
- `/history` - Show conversation history
- `/mode [auto|manual]` - Toggle execution mode
- `/exit` - Exit NEXUS
- `/context` - Show current context window

## Architecture

NEXUS consists of several components:

- **CLI REPL Interface** - Terminal-based interaction with streaming responses
- **Agentic Loop** - Core reasoning engine that orchestrates LLM calls and tool execution
- **LLM Provider Abstraction** - Supports multiple LLM backends (Groq, Ollama)
- **Tool Registry & Executor** - Manages available tools and safe execution
- **MCP Client Manager** - Connects to 3 MCP servers for extended capabilities:
  - Filesystem server (file operations)
  - Tavily server (web search)
  - Custom RAG server (semantic doc search)
- **Session Manager** - Handles conversation persistence and context management

## Project Structure

```
nexus-cli/
├── src/nexus/
│   ├── cli/              # Terminal interface
│   ├── core/             # Agent loop, session management
│   ├── llm/              # LLM provider abstraction
│   ├── tools/            # Tool registry & execution
│   ├── mcp/              # MCP client connections
│   ├── rag/              # RAG server implementation
│   ├── persistence/      # Session storage
│   ├── config/           # Configuration
│   └── main.py           # Entry point
├── tests/
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── e2e/              # End-to-end tests
├── rag/                  # RAG server data
├── docs/                 # Documentation
├── scripts/              # Setup & utility scripts
├── pyproject.toml
├── README.md
└── .env.example
```

## Development

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src/nexus

# Specific test file
pytest tests/unit/test_session.py
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type checking
mypy src/
```

### Development Setup

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Setup pre-commit hooks
pre-commit install
```

## Configuration

See `.env.example` for all available configuration options:

```bash
# Copy example and update with your values
cp .env.example .env
```

### Environment Variables

- `GROQ_API_KEY` - Groq API key for primary LLM
- `OLLAMA_BASE_URL` - Ollama server URL (default: http://localhost:11434)
- `TAVILY_API_KEY` - Tavily API key for web search
- `EXECUTION_MODE` - Default execution mode (auto/manual)
- `MAX_ITERATIONS` - Max agentic loop iterations
- `SESSION_DIR` - Directory for saving sessions

## Implementation Status

### Phase 1: Foundation ✅ In Progress

- [x] CLI REPL interface
- [x] Session management
- [x] Core types & data structures
- [x] Project structure & dependencies

### Phase 2: Core Loop ⏳ Next

- [x] Agentic loop orchestrator
- [x] LLM provider abstraction
- [x] Error handling & retry logic
- [x] Integration tests

### Phase 3: Tools & MCP ⏳ Future

- [ ] Tool registry & execution
- [ ] MCP client manager
- [ ] Filesystem integration
- [ ] Web search integration

### Phase 4: RAG Server ⏳ Future

- [ ] Custom RAG server
- [ ] HyDE implementation
- [ ] Vector DB setup
- [ ] LangChain doc indexing

## Contributing

This is a course project for ITSC 4681. Team members should:

1. Create feature branches: `git checkout -b feature/xyz`
2. Make commits with conventional messages: `feat:`, `fix:`, `refactor:`, `test:`
3. Submit PRs with description of changes
4. Require 1 cross-team code review before merge

## Team

- **Team A**: Core Infrastructure (CLI, Sessions, Persistence)
- **Team B**: Agentic Loop & LLM Integration
- **Team C**: Tools & MCP Integration
- **Team D**: RAG Server & Vector DB

## License

MIT

## References

- [Anthropic Claude Code in Action](https://anthropic.skilljar.com/claude-code-in-action)
- [Model Context Protocol Documentation](https://modelcontextprotocol.io)
- [LangChain Documentation](https://python.langchain.com)
- [Groq API](https://console.groq.com)
- [Ollama](https://ollama.ai)
- [Chroma Vector Database](https://docs.trychroma.com)
