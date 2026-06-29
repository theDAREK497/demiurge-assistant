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
- create relationships;
- create world rules;
- switch Master/Player visibility;
- first-entry Master/Player role choice saved in the browser;
- rich wiki cards with optional image URL/path and timeline date metadata;
- image upload for entity and map/location cards;
- relationship graph view;
- timeline view for Event entities;
- event journal, quest journal, and maps/location module views;
- toggle optional world sections in Settings;
- preview the AI memory/context;
- configure persistent LLM provider settings;
- send world-aware chat messages;
- save a liked assistant answer into draft wiki changes;
- review draft changes;
- apply checked, apply all, or reject draft changes;
- export and import world snapshots.

This is still a lightweight UI, but the main testing path is now meant to feel
like a friendly worldbuilding tool rather than a backend console.

## React/Vite Shell

A React/Vite shell now lives in:

- `frontend/`

It is a migration target, not the primary manual-testing UI yet. Run the stable
FastAPI UI at `/app/` for current end-to-end testing with LM Studio.

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
2. Click "Save to world" under an assistant answer you like.
3. Review the created draft changes.
4. Apply all changes or only checked items.

The old automatic `save_to_wiki` flow is still available as an optional checkbox,
but the click-to-save message flow is the preferred manual-testing path.

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

On first entry they choose Master or Player. The selected role is stored in
`localStorage` as `worldbuilder.viewerRole`.

## Worldbuilder Views

The first module views reuse existing entities:

- image-backed wiki cards use `entity.attributes.image_url`;
- timeline sorting uses Event entities and `entity.attributes.timeline_date`;
- quests are entities tagged `quest`;
- maps and pins currently use Location entities with optional images.

The visible module set is stored in `localStorage` as `worldbuilder.modules`.
Users can turn Graph, Timeline, Event journal, Quest journal, and Maps on or off
from Settings.

Uploaded images are stored in `worldbuilder_uploads/` by default and served from
`/assets/...`. The upload endpoint currently accepts PNG, JPEG, GIF, and WebP up
to 5 MB.

Drawing maps, persistent pins, and a richer dedicated map editor are still
future backend/UI work.

## Theme

The selected theme is stored in `localStorage` as `worldbuilder.theme`.

Theme colors are CSS variables in `static/styles.css`. New UI components should
use existing variables such as `--bg`, `--panel`, `--text`, `--muted`, `--line`,
and `--accent` instead of hardcoded colors.
