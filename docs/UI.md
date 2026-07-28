# Visual MVP

The first visual test interface is served by the FastAPI backend.

Start the server:

```text
start_worldbuilder.bat
```

or manually:

```powershell
uvicorn worldbuilder_core.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/app/
```

Current UI coverage:

- switch Russian/English interface language;
- switch light/dark theme;
- create and select worlds;
- create wiki entities;
- browse wiki entities as an encyclopedia-style card grid;
- open wiki cards in a full-screen reading view with image and relationship
  space;
- use the full-screen reader as a journal-like view for wiki cards, map
  locations, and detective board nodes, with direct transitions to linked
  cards;
- create and edit wiki cards through a right-side drawer;
- create relationships;
- create world rules;
- switch Master/Player visibility;
- first-entry Master/Player role choice saved in the browser;
- rich wiki cards with optional image URL/path and timeline date metadata;
- image upload for entity and map/location cards;
- relationship graph view with zoom, hover details, entity colors, and saved
  node positions;
- drag-and-drop timeline view for Event entities;
- event journal, quest Kanban, and maps/location module views;
- focused Modules workspace with one active mini-section at a time instead of
  one noisy all-modules grid;
- open Event, Quest, and Location cards in the shared full-screen reader and
  create, edit, or delete them directly from their module view;
- detective board with evidence nodes, connection lines, empty-board AI
  generation, and confirmed whole-board deletion;
- collapsible editors for maps, random tables, detective board, and advanced
  manual proposal JSON;
- quick action bars and compact content summaries in Maps and Detective board;
- toggle optional world sections in Settings;
- preview the AI memory/context;
- configure persistent LLM provider settings;
- send world-aware chat messages;
- keep local browser chat history in separate branches per world and viewer
  role, with bounded storage and canceled stale world requests;
- insert prepared chat prompt templates for base card types and enabled modules;
- render Markdown, including aligned pipe tables, in chat answers, drafts,
  wiki cards, and module prose;
- save a liked assistant answer into draft wiki changes;
- forward the selected UI language into world-aware chat and extraction so
  generated rules and draft lore match the user's language;
- review draft changes;
- review and apply AI-suggested new random tables or rows for existing tables;
- apply checked, apply all, or reject draft changes;
- use Player mode as a read-only public view without Master settings or editing
  tools;
- edit relationships and see confidence as a percentage with a readable level;
- use force-directed relationship graph arrangement, drag nodes, and keep their
  positions in browser storage per world and viewer role;
- delete worlds only after an explicit confirmation;
- export and import world snapshots.

This is still a lightweight UI, but the main testing path is now meant to feel
like a friendly worldbuilding tool rather than a backend console.

## React/Vite Shell

A React/Vite shell now lives in:

- `frontend/`

It is a migration target, not the primary manual-testing UI yet. Run the stable
FastAPI UI at `/app/` for current end-to-end testing with LM Studio. Its
dependency tree is locked and builds with Vite 8.

## Frontend Structure

The static UI is split into small browser modules:

- `static/app.js`: entrypoint;
- `static/js/api.js`: HTTP API helper;
- `static/js/i18n.js`: language loading and translation;
- `static/js/state.js`: shared UI state;
- `static/js/render.js`: DOM rendering;
- `static/js/actions.js`: user actions and API mutations;
- `static/js/main.js`: bootstrapping and event binding.
- `static/js/theme.js`: light/dark theme handling.

## LLM Settings

The Settings tab calls `GET /api/llm/config` and `PUT /api/llm/config`.
Saved values are stored in the local database and override environment defaults.

For LM Studio, use:

```text
http://127.0.0.1:1234/v1
```

Role-specific model fields are optional. Empty fields fall back to the default
model.

## Chat Write-Back

The recommended user flow is:

1. Ask the AI co-author to expand the world.
2. Click "Save as draft" under an assistant answer you like.
3. Review the created draft changes.
4. Apply all changes or only checked items.

The UI intentionally has no automatic `save_to_wiki` checkbox. Draft creation is
an explicit action on an assistant message. Chat branches are shown as a list and
support create, copy, rename, and delete. Individual messages can be edited or
deleted; this local history is stored per world and viewer role.

## Localization

Language files live in:

- `static/i18n/ru.json`;
- `static/i18n/en.json`.

The selected language is stored in `localStorage` as
`worldbuilder.language`. Russian is the default language.

Static HTML text should use:

```html
data-i18n="some.key"
data-i18n-placeholder="some.placeholder"
```

Dynamic text in JS should use `t("some.key")`. New visible UI strings should be
added to both language files.

## LAN Play

The UI can be used by players on the same local network when the backend is
started on an open host and port:

```powershell
uvicorn worldbuilder_core.main:app --host 0.0.0.0 --port 8000
```

The Windows starter can do this interactively. Players open:

```text
http://YOUR_LOCAL_IP:8000/app/
```

In LAN mode the starter also prints a private Master URL. It carries the
generated Master token in the URL fragment (`#master_token=...`), which is not
sent in the HTTP request or server log. Keep that URL private.

On first entry they choose Master or Player. The selected role is stored in
`localStorage` as `worldbuilder.viewerRole`.

The visible selector is no longer a normal dropdown in the top bar. Users enter
through the role choice modal, and can reopen it with the mode switch button.
Player mode hides Master-only settings, write-back, backup, and editing tools;
public data is fetched through role-aware backend APIs. The backend rejects
remote Master reads and all mutations unless the request has the Master token.
Loopback access is trusted by default so local development stays simple. Behind
a reverse proxy, set `WORLDBUILDER_TRUST_LOCAL_MASTER=false` and configure a
Master token explicitly.

## Worldbuilder Views

The first module views reuse existing entities:

- image-backed wiki cards use `entity.attributes.image_url`;
- timeline sorting uses Event entities and `entity.attributes.timeline_date`;
- quests are entities tagged `quest`;
- quest columns come from world-level status definitions; dragging persists
  `quest_status` and `quest_order`;
- timeline dragging persists `timeline_order`;
- entity card colors override their type color through
  `entity.attributes.color`;
- the quest journal also recognizes older Event cards whose summary explicitly
  identifies them as a quest, so pre-fix cards remain visible;
- maps use Location entities with optional images;
- persistent map pins store title, note, linked card, normalized coordinates,
  and secret/public visibility.
- random tables store weighted rows and let the user roll visible results from
  the Modules view. Draft proposals can add suggested rows to existing tables
  after review.
- detective board nodes can be freeform notes or linked to wiki cards, can
  include evidence URLs, and can be connected with labeled lines.

The visible module set is stored in `localStorage` as `worldbuilder.modules`.
Users can turn Graph, Timeline, Event journal, Quest journal, Maps, and Random
tables, and Detective board on or off from Settings.

Uploaded images are stored in `worldbuilder_uploads/` by default and served from
`/assets/...`. The upload endpoint currently accepts PNG, JPEG, GIF, and WebP up
to 5 MB.

Drawing maps and a richer dedicated map editor are still future backend/UI
work.

## Theme

The selected theme is stored in `localStorage` as `worldbuilder.theme`.

Theme colors are CSS variables in `static/styles.css`. New UI components should
use existing variables such as `--bg`, `--panel`, `--text`, `--muted`, `--line`,
and `--accent` instead of hardcoded colors.
