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

Every world starts with these entity types:

- `character`
- `location`
- `faction`
- `item`
- `event`
- `clue`
- `concept`

Entity types are now world configuration, not a closed enum. A Master can add
types and set their colors in Settings. Extraction may also introduce a concise
new type key; applying the proposal registers it automatically.

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
- graph view with saved layout, zoom, type/card colors, and entity hover details;
- drag-and-drop timeline view with persisted manual order;
- journal / quest / maps module views;
- quest Kanban with drag-and-drop cards and configurable world statuses;
- focused Modules workspace that shows one mini-section at a time;
- direct open/create/edit/delete actions for Event, Quest, and Location cards
  inside their module views;
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
- bounded Master Assistant tab with three scenarios: resumable source
  extraction, read-only world consistency audit, and adventure generation into
  a reviewable draft;
- adventure generation uses a compact mandatory schema for quests, clues,
  timeline events, graph links, and random tables instead of a slow prose-then-
  extraction chain;
- one automatic sequential AI worker in local SQLite mode, with pause/resume
  controls and per-segment checkpoints for long source extraction;
- Assistant runs require explicit confirmation, never apply world changes
  automatically, and keep a bounded per-world browser history;
- local browser chat history with separate branches per world and viewer role;
- prompt template chips in chat for common worldbuilding targets and enabled
  modules;
- markdown rendering, including alignment-aware tables, for chat, wiki cards,
  drafts, and module prose;
- explicit UI-language forwarding to chat/extraction so local models produce
  Russian or English world text consistently;
- review/apply/reject for extracted changes;
- duplicate cleanup for extracted draft entities, relationships, world rules,
  random-table rows, and notes before proposals are stored; close entity-name
  variants are reconciled with one unambiguous existing card and retained as
  aliases;
- read-only Player mode that hides Master-only settings and editing tools while
  using server-enforced visibility and Master authorization;
- editable relationships with readable confidence levels;
- force-directed relationship graph layout, manual rebuilding, and saved node
  positions in browser storage per world and role;
- confirmed world deletion;
- import/export;
- LAN-friendly starter flow through `start_worldbuilder.bat`.
- generated private LAN Master links with token-based API access;
- bounded chat history, abortable stale world requests, image signature checks,
  orphan upload cleanup, request size limits, and SQLite foreign-key checks;
- dependency lock/audit for the React shell on Vite 8.

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
- quest requests carry the original user intent into extraction and
  deterministically produce one primary Event card tagged `quest`, even when
  the model returns only locations, characters, items, or quest stages;
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
- optional encryption-at-rest for persisted third-party LLM API keys.
- embeddings are configurable through the LLM settings and imported books use hybrid retrieval when indexed;
- production mode uses PostgreSQL + pgvector HNSW and an external leased worker;
- ready imported sources can be extracted chunk-by-chunk by the leased AI worker;
- extracted facts are deduplicated into pending proposals, inherit source secrecy,
  and remain review-only until the master applies them.
- DOCX XML is parsed as a stream; AI extraction checkpoints completed
  sub-chunks and caches unsupported structured-output grammar to reduce RAM,
  retries, and duplicate LM Studio calls on large books.
- temporary LM Studio channel errors and timeouts keep the checkpoint and use
  bounded backoff; the UI reports an automatic retry instead of a terminal
  failure while attempts remain.
- document and embedding actions refresh all world data when they finish; a
  stale workspace also refreshes when its tab is opened or the page regains
  focus.
- Cytoscape.js 3.33.4 is bundled locally under its MIT license for graph
  layout, zoom, pan, node dragging, and weighted relationship rendering.
- relationships have confidence, 0-10 weight, validity period, evidence, and
  revision history; extraction uses structured JSON output when supported.

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
