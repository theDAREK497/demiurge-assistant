# Worldbuilder Core

Worldbuilder Core is a modular Python backend for an LLM-wiki: a self-updating
knowledge base for fictional worlds, tabletop campaigns, investigations, quests,
timelines, maps, and AI-assisted worldbuilding.

The current milestone is a backend MVP:

- worlds;
- wiki entities;
- stable directed relationships between entities;
- world rules;
- master/player visibility filtering;
- JSON import/export with stable UUID preservation;
- OpenAI-compatible LLM adapter for LM Studio and similar providers;
- SQLite by default;
- FastAPI HTTP API.

## Quick Start

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

## LM Studio

Start the LM Studio local server, then configure the backend with:

```powershell
$env:WORLDBUILDER_LLM_BASE_URL = "http://127.0.0.1:1234/v1"
$env:WORLDBUILDER_LLM_MODEL = "your-loaded-model"
```

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
```

## Project Notes

- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- LLM adapter: [docs/LLM.md](docs/LLM.md)
- Retrieval/RAG: [docs/RAG.md](docs/RAG.md)
- Visual MVP: [docs/UI.md](docs/UI.md)
- Write-back pipeline: [docs/WRITE_BACK.md](docs/WRITE_BACK.md)
- Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)

## Design Direction

The core is intentionally separated from any specific UI. A React app, desktop
shell, CLI, Discord bot, or another interface can talk to the same API.

Planned next layers:

- RAG context builder;
- background write-back pipeline;
- proposal workflow for extracted facts;
- graph/timeline/journal/quest modules.
