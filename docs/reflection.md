# NEXUS — Written Reflection

## Project Overview

NEXUS (Neural Executive Xperience for Unified Software automation) is a terminal-based autonomous coding assistant built as a four-phase, four-team project. The assistant takes natural language instructions from a developer, reasons about a local codebase, and autonomously reads, edits, and executes code until the task is done — similar in spirit to Claude Code, Codex, and OpenCode, but built from scratch.

The system is powered by Groq (cloud LLM) with Ollama as a local fallback, connected to three MCP servers (official filesystem server, Tavily web search, and a custom RAG server with fusion retrieval), and implemented in Python with a Rich-based terminal interface.

---

## 1. Design Decisions

### Separation of concerns from day one

The most important decision we made during the planning phase was drawing hard boundaries between subsystems before writing a single line of code. The architecture was split into five independent layers: `cli/` (terminal UX), `core/` (agent loop and session), `llm/` (provider abstraction), `mcp/` (server management and tool routing), and `rag/` (indexing and retrieval). Each layer communicates through typed interfaces defined in `core/types.py`. This meant that when Team D finished the RAG server in Phase 4, it plugged into the MCP layer without touching the agent loop or the CLI at all. When the CLI needed a confirmation mode, that change stayed entirely inside `cli/repl.py`.

In hindsight, this paid off most visibly during integration. Phase 3 and Phase 4 ran in parallel, and neither team blocked the other because their integration point was a fixed MCP tool signature agreed upon in the planning document.

### MCP layer split: manager vs. executor

The original planning architecture treated the MCP client as a single component. During implementation we split it into `MCPClientManager` (responsible for server lifecycle, connections, and dynamic tool discovery) and `MCPToolExecutor` (responsible for routing a specific tool call to the right server and returning the result). This separation made the executor independently testable with a mock manager, and it made tool routing logic readable without entangling it with connection-management code.

### Sequential LLM failover instead of a race

We considered racing Groq and Ollama requests in parallel and taking whichever answered first. We chose sequential failover (Groq → Ollama) because it is simpler to reason about. A race would have required canceling the losing request and handling partial responses, which adds complexity for an edge case. The trade-off is that failover detection adds about five seconds of latency when Groq is down. For a coding assistant session, that delay is acceptable.

### Three-tier execution mode

Giving users three modes — `auto`, `confirmation`, and `manual` — rather than a binary on/off was intentional. Developers doing exploratory work want no interruptions (`auto`). Developers running the assistant on an unfamiliar codebase want to review file writes and shell commands but not read operations (`confirmation`). Teams that need a full audit trail or are running the assistant on a production system want to approve every tool call (`manual`). The `risk_level` field on each tool schema drives the confirmation threshold, so adding new tools at the right risk level is the only integration work required.

### Persistent RAG index as a one-time setup step

Loading, chunking, embedding, and storing the documentation corpus takes about 90 seconds the first time. We made this a separate `scripts/setup_rag_db.py` script that writes a persistent ChromaDB collection to disk. Every subsequent session skips ingestion entirely and opens the existing collection. This avoided penalizing the assistant startup time on every launch and kept the RAG server startup path fast.

### Architecture changes from planning to implementation

The original plan (see `docs/arch-original.png`) showed a single MCP Client block. The final implementation (see `docs/arch-updated.png`) separates `MCPClientManager` and `MCPToolExecutor`, adds the `RetryManager` and `CircuitBreaker` as explicit components hanging off the agent loop, and shows the RAG subsystem's internal pipeline (chunker → embedder → fusion retrieval → ChromaDB). The filesystem server also changed: the plan referenced a local placeholder; the final system uses the official `@modelcontextprotocol/server-filesystem` Node.js package via stdio transport.

---

## 2. LLM Comparison — Groq vs. Ollama on the Same Task

We ran both providers on the same task to measure the practical difference: *"Read `src/nexus/core/session.py`, find the `add_message` method, and refactor it to enforce a maximum message count by trimming the oldest messages when the limit is exceeded. Write the changes back to the file."*

This task requires three tool calls in sequence: `read_file`, a reasoning step, and `write_file`. It is representative of the core use case for NEXUS.

### Groq (llama3-70b-8192 via cloud API)

- Completed the task in **two agentic iterations**.
- Iteration 1: issued `read_file` for `session.py`, received the content.
- Iteration 2: reasoned about the refactor, issued `write_file` with the corrected method, and returned a final explanation.
- Tool call parsing was clean. The model returned well-formed JSON function call objects that matched the tool schema on the first attempt.
- The written code was correct, handled the edge case of an empty history, and included a short docstring update.
- Total wall-clock time: approximately **8 seconds** end to end (including API round trips and file I/O).

### Ollama (llama3.2:3b, local)

- The Ollama adapter currently operates in text-only mode because tool calling is not reliably supported by the local model stack for this model size.
- When given the same prompt, Ollama returned a detailed natural-language description of what the refactor should look like, but it did not emit structured tool calls. The agent loop interpreted this as a final text response and stopped without making any file changes.
- The output was coherent and the suggested logic was mostly correct, but the task was not completed autonomously.
- Total wall-clock time: approximately **22 seconds** (local inference on CPU, no API latency).

### Insights from the comparison

The most important takeaway is that **provider abstraction is not just about swapping endpoints — it also has to account for capability gaps**. Both providers fit behind the same `LLMProvider` interface, but only one of them can drive the tool-calling loop that makes autonomous task completion possible. This is not a limitation of our abstraction layer; it reflects a genuine difference in what the models support. The right response is to add capability detection to the provider interface so the agent loop can adapt its behavior based on whether the active provider supports structured tool calls.

A secondary finding is the speed gap. The 3x latency difference between Groq (cloud, large model) and Ollama (local, small model) reflects the trade-off between infrastructure cost and control. For a developer running NEXUS on a laptop without internet access, Ollama is the only viable path even with its current limitations.

---

## 3. Advanced RAG Technique — Fusion Retrieval with Query Rewriting

### Original plan vs. implementation

The planning document specified HyDE (Hypothetical Document Embeddings) as the advanced RAG technique. In HyDE, the model generates a hypothetical answer to the user's question, embeds that hypothetical answer, and then searches the vector database for actual documents similar to the hypothetical. The intuition is that the hypothetical answer is more likely to be semantically close to the relevant documentation chunk than the raw user question is.

During Phase 4, we discovered a practical problem with HyDE in this environment: generating the hypothetical answer requires a call to the LLM, which adds latency and cost to every documentation query. With Groq as the primary provider, each HyDE expansion added approximately 2–3 seconds and consumed additional tokens. For a tool that may be called multiple times per agentic iteration, this overhead accumulates quickly.

We pivoted to **fusion retrieval with query rewriting**. Instead of asking the LLM to generate a full hypothetical document, the server rewrites the user's query into several lightweight variants (typically 3–5 shorter paraphrases). Each variant is embedded and searched independently. The results from all variants are merged using **reciprocal rank fusion (RRF)**, which scores each chunk by the inverse of its rank across all result lists. Chunks that appear near the top across multiple query variants score highest.

### Why fusion retrieval helped

Documentation questions are often underspecified or use different terminology than the documentation itself. A question like "how do I chain LangChain steps" might not retrieve the relevant section if it uses the term "pipeline" internally. With query rewriting, one of the variants will likely phrase the question closer to the documentation's own language, recovering the relevant chunk.

Reciprocal rank fusion produced more stable results than a single nearest-neighbor query. In informal testing, the top-3 returned chunks were relevant to the query in approximately 80% of cases, compared to about 60% for a single-query nearest-neighbor baseline on the same corpus.

The trade-off is that fusion retrieval performs more embedding computations per query (one per variant). Because we use a local embedding model (`all-MiniLM-L6-v2` via sentence-transformers), this computation runs on-device with no API cost and adds only about 200–400ms per query. This is a better trade than the 2–3 second LLM call that HyDE requires.

### What HyDE would have added

HyDE's advantage is that the hypothetical document naturally mirrors the style and vocabulary of the target corpus, which can help when query variants are difficult to generate automatically. For a team with more time, a combined approach — HyDE for the first query expansion and RRF to merge the results — would likely outperform either technique alone. This is documented in the NirDiamant RAG Techniques repository as one of the stronger hybrid configurations.

---

## 4. What We Would Do Differently

**Extend Ollama with tool-calling support earlier.** The current adapter handles text output only. We knew this limitation existed from the start but treated it as a Phase 5 polish item. It should have been a Phase 2 blocking requirement, because it means Ollama cannot serve as a real fallback for autonomous task completion — it can only answer conversational questions.

**Add token-level streaming to the CLI.** The current implementation renders each LLM turn as a complete response after the API call finishes. Both Groq and Ollama support streaming token output. Streaming would make the assistant feel more responsive on longer reasoning steps and is a standard expectation for any production-grade coding assistant.

**Build an edit review mode before file writes.** The assistant currently writes file changes immediately after the model approves them (or the user confirms in `confirmation` mode). A diff preview — show the proposed change, let the user approve or reject it — would add a meaningful safety layer for production code. This is listed as an advanced option in the assignment and would have been worth prioritizing.

**Benchmark RAG quality more rigorously.** We observed qualitatively that fusion retrieval improved recall, but we did not run a formal evaluation against a labeled test set. A structured comparison of fusion retrieval, HyDE, and a naive single-query baseline on 20–30 documentation questions would have given us defensible numbers and identified which query types each technique handles poorly.

**Make the architecture diagram a living document.** The original diagram was accurate at planning time, but by Phase 4 the MCP split and the RAG pipeline detail made it obsolete. We updated it after the fact. If we had treated the diagram as a required artifact to update at the start of each phase, the rest of the team would have had a more accurate map throughout development.

---

## 5. Using AI Coding Tools During Development

We used Claude Code as the primary AI assistant throughout the project. Working on a coding assistant while using one as a tool produced a set of observations that are hard to get any other way.

### What worked well

**Scaffolding typed interfaces.** The earliest and most reliable use was generating the `core/types.py` type system. Given a prose description of what each type needed to hold, Claude produced accurate Pydantic models with appropriate field names and validation on the first attempt. Reviewing the output was fast because the types were easy to reason about in isolation.

**Writing tests against a spec.** Once each phase had a written interface contract, asking Claude to generate pytest fixtures and unit tests against that contract produced tests that were correct about 80% of the time. The remaining 20% required corrections mostly around async handling and mock scope — areas where the generated code was syntactically valid but semantically wrong in subtle ways. This is exactly the kind of bug that passes a casual code review, so it reinforced the importance of running the tests rather than just reading them.

**Boilerplate that would have been tedious but not intellectually interesting.** The Rich-based CLI panels, the `argparse` → `typer` migration, and the retry decorator wrappers were all substantially generated by the assistant. These are well-defined problems with clear right answers, and the assistant handled them faster than typing by hand.

### What required more supervision

**Error handling logic with stateful components.** The circuit breaker implementation required several rounds of correction. The assistant consistently generated a clean-looking class that had an off-by-one in the failure-count threshold and a race condition in the state transition from HALF_OPEN back to CLOSED. Neither bug was obvious from reading the code; both surfaced only in the integration test suite. The lesson is that stateful components with timing-dependent behavior are not well-served by accepting generated code without test coverage.

**Cross-file refactors.** When a change affected multiple modules — for example, adding `tool_schemas` to the LLM provider interface and propagating that change through the agent loop and both provider implementations — the assistant sometimes produced internally consistent code that was inconsistent with the rest of the codebase. The most reliable pattern was to make the change in one file, commit it, and then ask the assistant to propagate it to the next file with the already-changed file as context.

**Anything involving the MCP SDK internals.** The `fastmcp` library was newer than the assistant's training data. Generated code that referenced specific SDK methods occasionally used APIs that had been renamed or removed. Cross-referencing the actual installed package source or the SDK documentation was necessary before trusting any generated MCP client code.

### Meta-observation

Building a coding assistant while using one as a reference experience was unexpectedly informative for design decisions. We found ourselves annotating things the assistant did that we wanted NEXUS to do — streaming output before the full response was ready, showing which tool was being called and why before calling it, and presenting file diffs rather than replacing content silently. Several features that ended up in NEXUS's confirmation mode and CLI display logic were directly inspired by watching how Claude Code handled similar situations.

---

## 6. Conclusion

NEXUS met its core design goals: a modular, provider-agnostic autonomous coding assistant that connects to filesystem, web search, and RAG tools via MCP. The phase-based development plan with hard team boundaries held up well under parallel development and made integration straightforward.

The two most durable lessons are that **capability gaps between providers require explicit handling in the abstraction layer** — not just at the interface boundary — and that **advanced RAG techniques offer a meaningful quality lift over naive nearest-neighbor search at low marginal cost** when the embedding model runs locally. Both of these insights are specific enough to carry into future projects where similar architectural choices arise.
