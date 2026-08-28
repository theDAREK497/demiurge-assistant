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
- `experience`;
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
  -> merge into one active world draft -> edit/review -> publish
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
Entity aliases participate in SQL candidate selection and ranking, and are
included in model context. Vector-only retrieval remains available for short
queries that do not produce a safe lexical term.

### World Experience And Causality

The experience log is retrieval memory, not model fine-tuning. Entity and
relationship CRUD writes an immutable before/after audit entry in the same
database transaction. Publishing a proposal records its entity and relationship
changes with the proposal ID and available source evidence.

Masters can also record a dated `world_event`, `correction`, or `retcon`, attach
it to a world or entity, select causal predecessors, and mark the entry secret.
Causal links are restricted to the same world and cycles are rejected.

Current API:

- `GET /api/worlds/{world_id}/changes`;
- `POST /api/worlds/{world_id}/changes`;
- `PATCH /api/changes/{change_id}`;
- `GET /api/worlds/{world_id}/entity-revisions`.

Retrieval scores at most 200 recent candidates and injects at most eight
relevant changes, including the causes of selected changes. Full before/after
JSON snapshots are never placed in the LLM context. Player retrieval excludes
secret history.

The relationship graph is rendered by a locally bundled Cytoscape.js build.
Node positions and viewport state are stored per world and viewer role. Current
relationship confidence controls edge opacity; relationship weight controls
edge width and color. The directed layout is also weight-aware: strong edges
pull their endpoints closer, weak edges keep a longer distance, and node size
reflects total incoming and outgoing weight. Relationships also carry free-form world dates, evidence, and an
append-only revision history.

Dense worlds stay in 2D and expose a filtered subgraph rather than adding a 3D
camera. A selected entity can show one, two, or all relationship hops; a weight
threshold removes weak edges, and labels can remain hidden until hover. Filtering
merges saved node positions instead of replacing positions for hidden nodes.

Published duplicate cleanup is explicit and transactional. Candidate scoring is
limited to entities of the same type and combines normalized names/aliases,
name-token containment, shared graph neighbors, and shared descriptive facts.
If a short name matches several longer names, every pair is marked ambiguous.
On confirmation, the canonical card receives unique data and aliases, references
are rewired, exact duplicate relationships are consolidated, and both entity and
relationship history records are appended before the duplicate is deleted.

### Large Document Ingestion

Master users can upload `.txt` and `.docx` sources as a raw streamed request.
DOCX XML is parsed incrementally with the standard library, so large books do
not require a full in-memory XML tree or an optional Word dependency.
Word table rows are emitted as bounded `[DOCUMENT TABLE]` Markdown blocks instead
of disconnected cell paragraphs, preserving roll ranges and outcomes for AI
extraction.

```text
streamed upload
  -> source SHA-256 guard
  -> resumable chunk manifest
  -> batches of at most 500 chunks
  -> normalized SHA-256 exact deduplication
  -> SimHash candidate lookup + lossless token equality guard
  -> shared knowledge chunk + per-document position link
  -> role-aware retrieval for chat
```

Each batch commits progress. Failed or paused work can resume without writing
the completed positions again. Secret sources are never added to Player
context. The local SQLite runtime is suitable for one-machine use; a
Multi-worker deployment uses PostgreSQL, pgvector search, and an external job
worker.

SimHash never decides deletion by itself. A near candidate is shared only when
its normalized word and number sequence is identical, so a changed name, date,
or fact cannot be discarded as a duplicate.

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

Before extraction, the worker compares a chunk with the tail of its predecessor.
Repeated overlap is supplied only as reference context and is removed from the
extractable source, including manifests created by older splitters that began
inside a word. A second boundary guard rejects a one-token lowercase fragment
at the start of a source, while preserving an explicitly capitalized short name.

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
retried up to five times with checkpoint-safe backoff. Successful embedding
batches reset their retry budget; configuration errors fail immediately, model
switches cancel stale active jobs, and an unexpected job exception is isolated
so the worker loop stays alive. Vector writes revalidate the active job lease in
the same transaction, preventing late provider responses from defeating a
cancellation. SQLite keeps a single-machine fallback without
`SKIP LOCKED` or a database vector index.

### Import/Export

World snapshots use `worldbuilder.snapshot.v1` and preserve stable UUIDs for:

- world;
- entities;
- relationships;
- world rules.
- extraction proposals.
- entity revision history;
- world changes and causal links.

Import validates referential integrity before writing data. If a world with the
same ID already exists, the caller must pass `replace_existing=true`.

### Write-Back Pipeline

The first write-back pipeline is in place:

```text
LLM/chat text
  -> extraction prompt
  -> strict JSON schema
  -> Pydantic validation
  -> deterministic conflict and duplicate cleanup
  -> merge into the world's active proposal record
  -> structured user edit/review
  -> publish
  -> wiki update
```

The LLM should propose changes. The core decides what is safe to write.

Publication is atomic. PostgreSQL serializes proposal mutation per world and
locks the changed proposal row. Repeated reviewed entities, relationships,
rules, tables, and table rows update their canonical records instead of creating
parallel copies. Existing secrecy is monotonic in AI publication: a public
draft cannot expose an already secret canonical object.

Current API:

- `POST /api/worlds/{world_id}/proposals`;
- `POST /api/worlds/{world_id}/proposals/extract`;
- `GET /api/worlds/{world_id}/proposals`;
- `GET /api/proposals/{proposal_id}`;
- `POST /api/proposals/{proposal_id}/apply`;
- `POST /api/proposals/{proposal_id}/reject`.
