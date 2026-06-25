# Visual MVP

The first visual test interface is served by the FastAPI backend.

Start the server:

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
- preview retrieved RAG context;
- send world-aware chat messages;
- enable `save_to_wiki`;
- review pending proposals;
- apply or reject proposals;
- export and import world snapshots.

This is intentionally a lightweight operational UI. It is meant to validate the
backend loop before we invest in a richer React interface.

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

## Theme

The selected theme is stored in `localStorage` as `worldbuilder.theme`.

Theme colors are CSS variables in `static/styles.css`. New UI components should
use existing variables such as `--bg`, `--panel`, `--text`, `--muted`, `--line`,
and `--accent` instead of hardcoded colors.
