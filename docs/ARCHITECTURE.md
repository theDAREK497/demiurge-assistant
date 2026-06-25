# Worldbuilder Core Architecture

## Product Shape

Worldbuilder Core is not just a RAG chatbot. It is a domain core for a living
fictional world:

- stable wiki entities;
- directed relationships;
- world rules that constrain generation;
- role-aware visibility for Master and Player modes;
- LLM pipelines that can propose updates to the knowledge base.

The backend is UI-agnostic. Any interface can use the same HTTP API.

## Current Layers

```text
FastAPI app
  -> route modules
  -> Pydantic schemas
  -> SQLAlchemy models
  -> SQLite database
```

Current route modules:

- `worlds`;
- `entities`;
- `relationships`;
- `world_rules`.
- `import_export`.
- `llm`.
- `retrieval`.
- `proposals`.

Shared application settings are stored separately from world data in
`app_settings`. This currently powers persistent LLM provider configuration.

## Domain Model

### World

Top-level container for one campaign or fictional universe.

### Entity

Wiki card with a stable UUID. Current supported types:

- `character`;
- `location`;
- `faction`;
- `item`;
- `event`;
- `clue`;
- `concept`.

The display name can change, but relationships should target the UUID.

### Relationship

Directed edge between two entities. Example:

```text
Mira --member_of--> Brass Guild
```

Deleting a relationship never deletes its source or target entities.

### WorldRule

A rule that should constrain generation and context building. Rules have:

- `priority` from 1 to 5;
- `condition`;
- `effect`;
- `tags`;
- `is_active`;
- `is_secret`.

## Visibility

Every entity, relationship, and world rule can be marked as secret.

Player mode must not reveal:

- secret entities;
- secret relationships;
- relationships touching secret entities;
- secret rules.

Master mode can see everything.

## Verification Status

The shared status enum is:

- `verified`;
- `proposed`;
- `unknown`;
- `rejected`.

This supports the write-back pipeline where LLM output is validated before being
committed to the world.

## Next Architecture Additions

### LLM Adapter

The first OpenAI-compatible adapter is in place. It covers:

- LM Studio;
- OpenAI API;
- OpenRouter or similar gateways;
- other compatible local servers.

Current API:

- `GET /api/llm/config`;
- `PUT /api/llm/config`;
- `POST /api/llm/chat`.

The adapter can be used directly, or through the world-aware chat endpoint that
adds retrieved context before calling the model.

Provider settings support model roles:

- chat;
- extractor;
- summarizer;
- critic/validator.

Only chat and extractor are active now. Summarizer and critic settings are kept
as an explicit contract for the next LLM pipelines.

### Retrieval

The first retrieval version is in place. It uses structured SQL search and rule
selection to build role-aware context.

Current API:

- `GET /api/worlds/{world_id}/context`;
- `POST /api/worlds/{world_id}/chat`.

The chat endpoint injects retrieved world context as a system message before
calling the OpenAI-compatible LLM adapter.

When `save_to_wiki=true`, the endpoint also runs extraction over the assistant
completion and stores the result as a pending proposal.

Embeddings can be added later behind the same service interface.

### Import/Export

World snapshots use `worldbuilder.snapshot.v1` and preserve stable UUIDs for:

- world;
- entities;
- relationships;
- world rules.
- extraction proposals.

Import validates referential integrity before writing data. If a world with the
same ID already exists, the caller must pass `replace_existing=true`.

### Write-Back Pipeline

The first write-back pipeline is in place:

```text
LLM/chat text
  -> extraction prompt
  -> strict JSON schema
  -> Pydantic validation
  -> proposal record
  -> user apply/reject
  -> wiki update
```

The LLM should propose changes. The core decides what is safe to write.

Current API:

- `POST /api/worlds/{world_id}/proposals`;
- `POST /api/worlds/{world_id}/proposals/extract`;
- `GET /api/worlds/{world_id}/proposals`;
- `GET /api/proposals/{proposal_id}`;
- `POST /api/proposals/{proposal_id}/apply`;
- `POST /api/proposals/{proposal_id}/reject`.
