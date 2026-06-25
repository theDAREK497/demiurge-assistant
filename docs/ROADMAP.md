# Roadmap

## Milestone 1: Backend Core

Status: started.

- [x] Python/FastAPI project scaffold.
- [x] SQLAlchemy models.
- [x] SQLite default database.
- [x] CRUD for worlds.
- [x] CRUD for wiki entities.
- [x] CRUD for directed relationships.
- [x] CRUD for world rules.
- [x] Master/player visibility filtering.
- [x] Basic API test.

## Milestone 2: Import/Export

- [x] Export a full world to one JSON file.
- [x] Import a full world from JSON.
- [x] Preserve stable UUIDs during import.
- [x] Add version metadata to exports.
- [x] Validate snapshot referential integrity before import.
- [x] Protect existing worlds with explicit replace mode.

## Milestone 3: LLM Adapter

- [x] Add provider settings.
- [x] Implement OpenAI-compatible chat client.
- [x] Support LM Studio endpoint configuration.
- [x] Add LLM config endpoint.
- [x] Add LLM chat endpoint.
- [x] Test provider request/response parsing without network calls.
- [ ] Add persistent provider settings.
- Add model roles:
  - chat model;
  - extractor model;
  - summarizer model;
  - critic/validator model.

## Milestone 4: Retrieval

- [x] Build context from world rules.
- [x] Build context from matching entities.
- [x] Build context from relevant relationships.
- [x] Add role-aware context filtering.
- [x] Add first RAG context endpoint.
- [x] Add first world-aware LLM chat endpoint.
- Later: add embeddings and vector search.

## Milestone 5: Write-Back Pipeline

- [x] Define extraction schema.
- [x] Store changes as proposals.
- [x] Add apply/reject endpoints.
- [x] Apply proposed entities, relationships, and rules into the wiki.
- [x] Support client-local IDs for relationship extraction.
- [x] Add LLM extraction endpoint.
- [x] Add `save_to_wiki` to world-aware chat.
- [x] Return extraction failures as non-fatal `wiki_save_error` for chat.
- [x] Add one retry for malformed structured LLM output.
- [x] Include proposals in JSON backup/export.
- [ ] Add fine-grained proposal item review.
- [ ] Add UI review panel.

## Milestone 6: UI

- [x] Static Visual MVP served by FastAPI.
- [x] Russian/English UI language switch.
- [x] Light/dark theme switch.
- [x] UI strings moved to language JSON files.
- [x] Frontend split into small ES modules.
- [x] World list and creation form.
- [x] Wiki list and entity creation.
- [x] Relationships and world rules.
- [x] World-aware chat with `save_to_wiki`.
- [x] Proposal list with apply/reject.
- [x] Context preview.
- [x] Export/import panel.
- [ ] React/Vite shell.
- [ ] Rich entity card editing.
- [ ] Fine-grained proposal review panel.
- Relationship graph view.

## Milestone 7: Worldbuilder Modules

- Journal.
- Timeline.
- Quests.
- Random tables.
- Maps and pins.
- Detective board.
