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
4. If an assistant answer is good, click `Save as draft`.
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
- full-screen journal-style reading view for wiki cards, map locations, and
  detective board nodes;
- drawer-based card create/edit flow;
- graph view;
- timeline view;
- journal / quest / maps module views;
- focused Modules workspace that shows one mini-section at a time;
- persistent map pins with title, note, linked card, normalized coordinates,
  Master/Player filtering, and export/import support;
- random tables with weighted rows, roll results, Master/Player filtering, and
  export/import support;
- AI-suggested new random tables and rows through the normal draft
  proposal review/apply flow;
- detective board with freeform/entity-linked evidence nodes, connections,
  evidence URLs, Master/Player filtering, and export/import support;
- empty-board AI generation and confirmed whole-board deletion;
- collapsible editor sections in module-heavy screens so content stays primary
  and advanced/manual tools stay secondary;
- quick actions and content summaries in maps and detective board so creation
  tools stay close to the module without dominating the screen;
- module toggles in Settings;
- AI chat with draft-save flow;
- local browser chat history with separate branches per world and viewer role;
- prompt template chips in chat for common worldbuilding targets and enabled
  modules;
- markdown rendering, including alignment-aware tables, for chat, wiki cards,
  drafts, and module prose;
- explicit UI-language forwarding to chat/extraction so local models produce
  Russian or English world text consistently;
- review/apply/reject for extracted changes;
- duplicate cleanup for extracted draft entities, relationships, world rules,
  random-table rows, and notes before proposals are stored;
- read-only Player mode that hides Master-only settings and editing tools while
  still using backend visibility filters;
- editable relationships with readable confidence levels;
- force-directed relationship graph layout, manual rebuilding, and saved node
  positions in browser storage per world and role;
- confirmed world deletion;
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

Before an LLM-created proposal is stored, invalid invented entity/table
references are now removed or recovered where possible. One bad relationship or
table row no longer rejects the useful part of the draft with HTTP 422.

## Current Chat UX Notes

Recent chat UX improvements:

- assistant messages are saved manually with `Save as draft`; automatic draft
  creation is not shown in the UI;
- chat branches use a visible list and can be created, copied, renamed, or
  deleted;
- user and assistant messages can be edited or deleted locally;
- Markdown supports headings through level six, emphasis, dividers, lists,
  quotes, code, and aligned pipe tables in chat and draft review;
- quest requests explicitly extract a primary Event card tagged `quest`;
- newly described random tables are extracted as tables and rows rather than
  relationships;
- chat history is restored and rendered after a page reload;
- chat shows a loading indicator while the model is thinking.

## Known Open Work

Roadmap items still intentionally open:

- richer map editor and drawing over maps;
- hex-based world map generator/editor;
- richer detective board layout/editing beyond whole-board AI generation;
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
