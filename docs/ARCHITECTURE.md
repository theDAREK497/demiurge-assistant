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
- `world_rules`;
- `map_pins`;
- `random_tables`;
- `detective_board`;
- `documents`;
- `assets`;
- `import_export`;
- `llm`;
- `retrieval`;
- `proposals`.

Shared application settings are stored separately from world data in
`app_settings`. This currently powers persistent LLM provider configuration.

### Bounded Master Assistant

The `/app/` Assistant tab is a client-side orchestrator over existing APIs, not
an autonomous write path:

```text
explicit user confirmation
  -> source: document extraction job -> pending proposals
  -> audit: role-aware retrieval + chat -> read-only report
  -> adventure: one structured generation call -> validated pending proposal
  -> manual proposal review/apply
```

Assistant run summaries are bounded to 20 entries and stored per world in
browser local storage. Reloaded in-progress browser runs are marked
interrupted. Durable source extraction continues through its leased backend
job and remains visible in Sources.

## Domain Model

### World

Top-level container for one campaign or fictional universe.

### Entity

Wiki card with a stable UUID. `Entity.type` is a normalized string. Built-in
types remain `character`, `location`, `faction`, `item`, `event`, `clue`, and
`concept`, but each world may add more.

`EntityTypeDefinition` stores the world-local key, display name, color, order,
and built-in flag. Unknown types arriving through an applied AI proposal are
registered automatically.

`QuestStatusDefinition` stores ordered, colored Kanban columns. Quest cards
persist `quest_status` and `quest_order` in `Entity.attributes`; timeline cards
persist `timeline_order` there as well.

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

Visibility is also an authorization boundary. Remote Player requests can read
only explicitly public role-aware routes and roll public random tables. Master
reads, settings, exports, drafts, and all mutations require either trusted
loopback access or `X-Worldbuilder-Master-Token`. The selected UI role alone is
not accepted as authorization.

## Runtime Safety

- request bodies are capped before full parsing;
- uploaded images are size, MIME, and signature checked;
- generated upload files are removed when no card references them, and stale
  abandoned uploads are cleaned after one day;
- SQLite foreign-key enforcement is enabled on every connection;
- relationship, map, random-table, and detective-board reads eager-load related
  records to avoid N+1 query growth;
- browser responses include CSP and common security headers.

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

Imported knowledge sources participate in hybrid retrieval. Lexical matches are
combined with cosine similarity from an OpenAI-compatible embedding endpoint.
Indexing is resumable in bounded batches and falls back to lexical retrieval
when no embedding model is configured or the provider is unavailable.

The relationship graph is rendered by a locally bundled Cytoscape.js build.
Node positions and viewport state are stored per world and viewer role. Current
relationship confidence controls edge opacity; relationship weight controls
edge width. Relationships also carry free-form world dates, evidence, and an
append-only revision history.

### Large Document Ingestion

Master users can upload `.txt` and `.docx` sources as a raw streamed request.
DOCX XML is parsed incrementally with the standard library, so large books do
not require a full in-memory XML tree or an optional Word dependency.

```text
streamed upload
  -> source SHA-256 guard
  -> resumable chunk manifest
  -> batches of at most 500 chunks
  -> normalized SHA-256 exact deduplication
  -> conservative SimHash near-duplicate check
  -> shared knowledge chunk + per-document position link
  -> role-aware retrieval for chat
```

Each batch commits progress. Failed or paused work can resume without writing
the completed positions again. Secret sources are never added to Player
context. The local SQLite runtime is suitable for one-machine use; a
Multi-worker deployment uses PostgreSQL, pgvector search, and an external job
worker.

After chunking, the master can enqueue bounded AI extraction:

```text
ready document
  -> leased document_extraction_job
  -> one source chunk per worker pass
  -> structured extraction and world-aware matching
  -> proposal-level deduplication
  -> pending proposals for manual review
```

Extraction inherits source secrecy and never applies results directly to the
world. Each source chunk is split into bounded model segments. Completed
segments are checkpointed in the job, so provider or schema failures resume at
the next segment instead of regenerating the whole chunk. Temporary failures
use 15/30/60/120-second backoff before the next leased attempt. When an
OpenAI-compatible provider rejects JSON grammar, that capability failure is
cached temporarily to avoid repeating a known failing request for every
segment.

The local SQLite runtime starts one sequential AI worker inside the API
process. Document segments are capped at 2200 characters, four extracted
entities, and 1280 output tokens, use strict JSON output with model reasoning disabled, and can be
paused after the current segment. Segment-local client IDs are namespaced
before merging so repeated model IDs cannot collide. PostgreSQL deployments
keep the external worker shown below and disable the embedded worker.

The production path now provides that split:

```text
FastAPI -> embedding_jobs/document_extraction_jobs <- AI worker(s)
   |                                  |
   +---------- PostgreSQL ------------+
                + pgvector
                + HNSW cosine index
```

Workers claim jobs with `FOR UPDATE SKIP LOCKED`. A lease and heartbeat allow a
different worker to recover work after a crashed process. Provider failures are
retried up to five times with checkpoint-safe backoff. SQLite keeps a single-machine fallback without
`SKIP LOCKED` or a database vector index.

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
