# Worldbuilder Core

Worldbuilder Core is a modular Python backend for an LLM-wiki: a self-updating
knowledge base for fictional worlds, tabletop campaigns, investigations, quests,
timelines, maps, and AI-assisted worldbuilding.

The current milestone is a backend MVP:

- worlds;
- wiki entities;
- stable directed relationships between entities;
- world rules;
- server-enforced master/player visibility filtering;
- JSON import/export with stable UUID preservation;
- OpenAI-compatible LLM adapter for LM Studio and similar providers;
- persistent LLM provider settings with model roles;
- lightweight RU/EN visual UI with light/dark themes;
- image uploads for wiki cards and map/location views;
- React/Vite shell for the next UI migration;
- SQLite by default;
- FastAPI HTTP API.

## Quick Start

For a friendly Windows start, double-click:

```text
start_worldbuilder.bat
```

The starter asks for local/LAN mode, port, LM Studio base URL, and an optional
model name. In LAN mode it binds to `0.0.0.0`, creates a Master access key, and
prints separate Player and private Master URLs.

Manual start:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
uvicorn worldbuilder_core.main:app --reload
```

Open:

- Visual app: <http://127.0.0.1:8000/app/>
- API docs: <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/health>

The React/Vite shell lives in [frontend](frontend/). The stable UI for manual
testing is still `/app/`.

For local network play, start with:

```powershell
uvicorn worldbuilder_core.main:app --host 0.0.0.0 --port 8000
```

Players then open `http://YOUR_LOCAL_IP:8000/app/` and choose Player on first
entry. A remote client cannot turn Player mode into Master mode by changing the
URL or calling the API directly. For a manual LAN start, set
`WORLDBUILDER_MASTER_TOKEN` if Master access is needed from another computer.

## LM Studio

Start the LM Studio local server, then configure the backend with:

```powershell
$env:WORLDBUILDER_LLM_BASE_URL = "http://127.0.0.1:1234/v1"
$env:WORLDBUILDER_LLM_MODEL = "your-loaded-model"
```

Or configure it from the visual app:

1. Open <http://127.0.0.1:8000/app/>.
2. Go to the Settings tab.
3. Set Base URL to `http://127.0.0.1:1234/v1`.
4. Set the default/chat/extractor model names to the model loaded in LM Studio.
5. Save the settings.

Then call:

- LLM config: <http://127.0.0.1:8000/api/llm/config>
- LLM chat: `POST /api/llm/chat`
- World context: `GET /api/worlds/{world_id}/context`
- World-aware chat: `POST /api/worlds/{world_id}/chat`
- World-aware chat with pending wiki save: `POST /api/worlds/{world_id}/chat` with `save_to_wiki=true`
- Create extraction proposal: `POST /api/worlds/{world_id}/proposals`
- LLM extraction proposal: `POST /api/worlds/{world_id}/proposals/extract`
- Apply/reject proposal: `POST /api/proposals/{proposal_id}/apply` or `/reject`

## Checks

```powershell
python -m pytest
python -m compileall src tests
ruff check src tests
bandit -r src -q
pip-audit --local --skip-editable
cd frontend
npm audit
npm run build
```

## License

MIT. See [LICENSE](LICENSE).

## PostgreSQL + pgvector

Copy `.env.example` to `.env`, set strong `POSTGRES_PASSWORD` and
`WORLDBUILDER_MASTER_TOKEN` values, and set
`WORLDBUILDER_EMBEDDING_DIMENSIONS` to the number of floats returned by the
configured embedding model. BGE-M3 returns `1024`; this must match the fixed
pgvector column size.

```powershell
docker compose up --build -d
```

Open `http://127.0.0.1:8000/app/?role=master#master_token=YOUR_TOKEN`.
The stack starts PostgreSQL/pgvector, FastAPI, and a separate AI worker. It
builds embeddings and extracts ready document chunks into reviewable drafts.

For local SQLite use, the API starts one sequential AI worker automatically.
Set `WORLDBUILDER_LOCAL_WORKER_ENABLED=false` only when running
`start_embedding_worker.bat` as a dedicated process.

Database diagnostics:

```powershell
python -m worldbuilder_core.check_database
```

## Project Notes

- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Active context for new branches/chats: [docs/CONTEXT.md](docs/CONTEXT.md)
- LLM adapter: [docs/LLM.md](docs/LLM.md)
- Retrieval/RAG: [docs/RAG.md](docs/RAG.md)
- Visual MVP: [docs/UI.md](docs/UI.md)
- Write-back pipeline: [docs/WRITE_BACK.md](docs/WRITE_BACK.md)
- Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)
- Security and audit notes: [docs/SECURITY.md](docs/SECURITY.md)

## Design Direction

The core is intentionally separated from any specific UI. A React app, desktop
shell, CLI, Discord bot, or another interface can talk to the same API.

Planned next layers:

- RAG context builder;
- background write-back pipeline;
- proposal workflow for extracted facts;
- graph/timeline/journal/quest modules.
