# Project Context

## Purpose

`demiurge-assistant` is a Python/FastAPI worldbuilding platform for an
LLM-wiki style knowledge base.

The project goal is not "just chat with lore". The real goal is a reusable core
that can:

- store stable world knowledge;
- let AI read that knowledge with role-aware visibility;
- let AI propose structured updates back into the wiki;
- support multiple future interfaces over one backend.

The current stable manual-testing UI is the FastAPI-served app at `/app/`.

## Current Stack

- Backend: Python, FastAPI, SQLAlchemy, Pydantic, SQLite by default.
- Stable UI: static HTML/CSS/ES modules served by FastAPI.
- Future UI direction: `frontend/` React/Vite shell.
- LLM integration: OpenAI-compatible API, tested primarily with LM Studio.
- Current local model setup: `gemma-4-e4b-uncensored-hauhaucs-aggressive`
  through `http://127.0.0.1:1234/v1`.

## Core Domain

The main world model currently includes:

- worlds;
- wiki cards/entities;
- directed relationships;
- world rules;
- master/player visibility filtering;
- extraction proposals for AI write-back.

Supported entity types:

- `character`
- `location`
- `faction`
- `item`
- `event`
- `clue`
- `concept`

## Stable User Flow

The current intended UX flow is:

1. Create or open a world.
2. Add or edit wiki cards manually.
3. Chat with the AI co-author.
4. If an assistant answer is good, click `Save to world`.
5. Review the created draft changes.
6. Apply all changes or only checked items.

This is the preferred manual-testing path.

## Current UI State

The `/app/` UI already supports:

- RU/EN language switch;
- light/dark theme;
- first-entry Master/Player role choice;
- less technical RU/EN section names for the main worldbuilding flow;
- settings for LLM provider and model names;
- rich wiki cards with image URL/upload and timeline metadata;
- encyclopedia-style card grid;
- full-screen wiki card reading view;
- drawer-based card create/edit flow;
- graph view;
- timeline view;
- journal / quest / maps module views;
- module toggles in Settings;
- AI chat with draft-save flow;
- explicit UI-language forwarding to chat/extraction so local models produce
  Russian or English world text consistently;
- review/apply/reject for extracted changes;
- import/export;
- LAN-friendly starter flow through `start_worldbuilder.bat`.

## Important Recent Fixes

As of 2026-06-30, one important backend issue was fixed in the extraction
pipeline.

Problem:

- LM Studio models could answer correctly in chat, but fail on
  `POST /api/worlds/{world_id}/proposals/extract`.
- The old parser expected nearly perfect schema output and broke on common local
  model variants such as:
  - `id` instead of `client_id`;
  - `source_id` / `target_id` instead of source/target client/entity fields;
  - `rule_name` + `description` instead of `condition` + `effect`;
  - unsupported type labels like `organization`, `resource`,
    `world_concept`, `setting_element`.

Current behavior:

- extraction now normalizes many common model-output variants before strict
  schema validation;
- entity types are mapped into supported internal types;
- malformed or ambiguous relationships are skipped instead of crashing the
  entire extraction;
- JSON fenced or wrapped in extra text is parsed more robustly;
- the repair prompt now explicitly asks the model to correct field names.

This means "chat works but save to wiki fails" should now be much less common.

## Current Chat UX Notes

Recent chat UX improvements:

- assistant messages can be saved individually with `Save to world`;
- the old `save_to_wiki` checkbox still exists as an optional auto-draft mode;
- chat now shows a loading indicator while the model is thinking.

## Known Open Work

Roadmap items still intentionally open:

- random tables;
- map editor / pins / drawing over maps;
- hex-based world map generator/editor;
- detective board;
- continued polish of non-technical, friendly UX;
- richer React migration if and when `/app/` stops being enough.

## How To Run

Preferred Windows path:

```text
start_worldbuilder.bat
```

Manual path:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
uvicorn worldbuilder_core.main:app --reload
```

Open:

- App: `http://127.0.0.1:8000/app/`
- Docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

LM Studio default local endpoint:

```text
http://127.0.0.1:1234/v1
```

Current local model used for manual testing:

```text
gemma-4-e4b-uncensored-hauhaucs-aggressive
```

## How To Continue In A New Branch Or Chat

If a new Codex thread needs project context, start with:

```text
Read docs/CONTEXT.md first, then continue from there.
```

If the task is UI-related, also read:

- `docs/UI.md`
- `docs/ROADMAP.md`

If the task is backend write-back or proposal related, also read:

- `docs/WRITE_BACK.md`
- `docs/ARCHITECTURE.md`

If the task is ongoing implementation planning, also read:

- `docs/LOOP_TASK.md`
- `docs/NEXT_IMPLEMENTATIONS_PLAN.md`

## Working Rule For This File

This file should be updated during development whenever one of these changes:

- the main user flow;
- the recommended startup/test flow;
- the architecture shape;
- the most important known issue or recent fix;
- the list of meaningful unfinished areas.
