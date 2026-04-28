# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Full Setup (from scratch)

**Step 1 — Install pyenv and Python 3.13**
```bash
curl https://pyenv.run | bash
# Add to ~/.zshrc (or ~/.bashrc):
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
# Reload shell
source ~/.zshrc

pyenv install 3.13.0
```

**Step 2 — Set Python version for this project**
```bash
unset PYENV_VERSION   # clear if set (PYENV_VERSION env var overrides pyenv local)
pyenv local 3.13.0
python --version      # should show 3.13.x
```
If `python --version` still shows the wrong version, create the venv directly:
```bash
~/.pyenv/versions/3.13.0/bin/python -m venv .venv
```

**Step 3 — Create and activate virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate
```

**Step 4 — Install dependencies**
```bash
pip install chromadb==1.0.15 anthropic==0.58.2 sentence-transformers==5.0.0 fastapi==0.116.1 uvicorn==0.35.0 python-multipart==0.0.20 python-dotenv==1.1.1
```

## Running the Application

```bash
# With uv (if installed)
./run.sh

# Without uv (after pip install above)
cd backend && python -m uvicorn app:app --reload --port 8000
```

App runs at `http://localhost:8000`. API docs at `http://localhost:8000/docs`. Requires Python 3.13+.

## Environment

Copy `.env.example` to `.env` in the project root:
```
ANTHROPIC_API_KEY=your-key-here
ANTHROPIC_BASE_URL=https://your-proxy-url  # optional, only if using a proxy
```

## Architecture

This is a RAG (Retrieval-Augmented Generation) chatbot over course materials. The backend is FastAPI; the frontend is vanilla JS served as static files by FastAPI — no separate frontend server.

**Query flow:**
1. Frontend (`frontend/script.js`) POSTs `{ query, session_id }` to `/api/query`
2. `app.py` delegates to `RAGSystem.query()`
3. `RAGSystem` calls `AIGenerator.generate_response()` with the `search_course_content` tool available
4. Claude decides whether to call the tool. If it does (`stop_reason == "tool_use"`), `_handle_tool_execution()` runs `CourseSearchTool.execute()` → `VectorStore.search()` (ChromaDB), appends results to the message history, and makes a second Claude call to synthesize the final answer
5. Sources (course/lesson labels) are tracked inside `CourseSearchTool.last_sources` and returned alongside the answer

**Key design decisions:**
- Claude drives retrieval (tool-use pattern) — there is no fixed "retrieve then generate" pipeline; Claude decides when and what to search
- Two ChromaDB collections: one for content chunks, one for course catalog metadata. The catalog enables semantic course-name resolution (fuzzy matching by embedding similarity) inside `VectorStore._resolve_course_name()`
- Conversation history is in-memory only (`SessionManager`), capped at `MAX_HISTORY` exchanges (default 2). Sessions are lost on server restart
- `AIGenerator` accepts an optional `base_url` for routing through a proxy — configured via `ANTHROPIC_BASE_URL` in `.env`

**Document ingestion** happens at startup (`app.py` → `startup_event`): `.txt` files from `docs/` are read by `DocumentProcessor`, chunked into sentence-based overlapping segments, and stored in ChromaDB via `VectorStore`.

**Config** lives in `backend/config.py` as a dataclass (`Config`). All tuneable parameters (chunk size, overlap, max results, history length, model name, paths) are there.
