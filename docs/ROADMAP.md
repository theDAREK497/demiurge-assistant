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
- [x] Add persistent provider settings.
- [x] Add model roles:
  - [x] chat model;
  - [x] extractor model;
  - [x] summarizer model;
  - [x] critic/validator model.

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
- [x] Add fine-grained proposal item review.
- [x] Add UI review panel.
- [x] Add click-to-save assistant message flow.

## Milestone 6: UI

- [x] Static Visual MVP served by FastAPI.
- [x] Russian/English UI language switch.
- [x] Light/dark theme switch.
- [x] UI strings moved to language JSON files.
- [x] Frontend split into small ES modules.
- [x] Settings tab for persistent LLM provider configuration.
- [x] Repair Russian localization encoding.
- [x] World list and creation form.
- [x] Wiki list and entity creation.
- [x] Relationships and world rules.
- [x] World-aware chat with `save_to_wiki`.
- [x] Proposal list with apply/reject.
- [x] Context preview.
- [x] Export/import panel.
- [x] Friendly Windows `.bat` starter.
- [x] First-entry Master/Player role choice.
- [x] Richer wiki cards with image URL and timeline metadata.
- [x] Relationship graph view.
- [x] Timeline view.
- [x] First journal/quest/map UI views over existing entities.
- [x] React/Vite shell.
- [x] Rich entity card editing.
- [x] Fine-grained proposal review panel.
- [x] File uploads for entity and map images.
- [x] Network-play polish and player invite screen.
- [x] Friendlier chat write-back UX.
- [x] Toggleable UI sections/modules.

## Milestone 7: Worldbuilder Modules

- [x] Journal: first UI view over Event entities.
- [x] Timeline: first UI view over Event entities.
- [x] Quests: first UI view over entities tagged `quest`.
- Random tables.
- [x] Maps: first UI view over Location entities with images.
- [x] UI toggles for optional worldbuilder modules.
- Maps and pins with upload/drawing/editing.
- Detective board.
