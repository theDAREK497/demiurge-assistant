# Write-Back Pipeline

The write-back pipeline is the safety layer between LLM output and the wiki.

The model is not allowed to directly mutate the world. It can only produce a
structured extraction payload. The core validates it, merges it into the
world's single active draft, and lets the user edit it before publication.

## Proposal Flow

```text
source text
  -> extraction payload
  -> validation, conflict resolution, and deduplication
  -> one active pending proposal per world
  -> structured edit/review
  -> publish
  -> wiki update
```

## Manual Proposal API

```http
POST /api/worlds/{world_id}/proposals
Content-Type: application/json

{
  "source_text": "Mara founded the Rust Garden.",
  "payload": {
    "entities": [
      {
        "client_id": "mara",
        "type": "character",
        "name": "Mara"
      },
      {
        "client_id": "rust-garden",
        "type": "faction",
        "name": "Rust Garden"
      }
    ],
    "relationships": [
      {
        "source_client_id": "mara",
        "target_client_id": "rust-garden",
        "type": "founded"
      }
    ],
    "random_table_rows": [
      {
        "table_id": "existing-random-table-uuid",
        "label": "Market rumor",
        "result": "A masked buyer pays double for unbroken glass.",
        "weight": 1,
        "is_secret": false
      }
    ]
  }
}
```

New entities can use temporary `client_id` values. Relationships in the same
payload may point at those IDs. Relationships can also point at existing wiki
UUIDs through `source_entity_id` and `target_entity_id`.

## LLM Extraction API

```http
POST /api/worlds/{world_id}/proposals/extract
Content-Type: application/json

{
  "role": "master",
  "source_text": "Mara founded the Rust Garden and forbade sky fire.",
  "query": "Mara Rust Garden",
  "max_entities": 12
}
```

The backend:

- builds role-aware world context;
- asks the configured OpenAI-compatible model for strict JSON;
- validates the JSON with Pydantic;
- removes repeated draft entities, relationships, world rules, random-table
  rows, and notes before storing the proposal;
- forwards the original user request into extraction and guarantees a primary
  Event entity tagged `quest` when a quest was requested;
- reconciles unambiguous near-duplicate entity names with existing cards and
  stores the generated name variant as an alias;
- separates newly described random tables and their rows from relationships;
- recovers invalid invented match IDs as new draft entities when possible and
  drops dangling relationships or unknown table rows instead of failing the
  entire LLM-created draft;
- performs one repair retry if the model returns malformed JSON;
- stores the result as a pending proposal.

## Chat With `save_to_wiki`

The world-aware chat endpoint can create a pending proposal from the assistant
response:

```http
POST /api/worlds/{world_id}/chat
Content-Type: application/json

{
  "role": "master",
  "save_to_wiki": true,
  "messages": [
    {
      "role": "user",
      "content": "Invent a rumor about a new faction."
    }
  ]
}
```

Flow:

```text
world-aware chat
  -> assistant completion
  -> extraction call over completion
  -> merge into the active pending proposal
  -> user edit/publish
```

The endpoint returns both the completion and the created proposal. If extraction
fails, the completion is still returned with `wiki_save_error`.

## Edit Or Publish

```http
PATCH /api/proposals/{proposal_id}
POST /api/worlds/{world_id}/proposals/consolidate
POST /api/proposals/{proposal_id}/apply
POST /api/proposals/{proposal_id}/apply-selected
POST /api/proposals/{proposal_id}/reject
DELETE /api/proposals/{proposal_id}
```

Applying a proposal writes extracted entities, relationships, and rules into the
wiki. It can also create reviewed random tables and add rows to new or existing
tables. Applying the same proposal twice is blocked. The primary UI exposes a
structured editor and one publish action; selected apply/reject remain API
compatibility operations.
Deleting a proposal removes the draft/review record without applying it.

Publishing also performs a canonical-world upsert. Same-type entities are
matched without crossing entity-type boundaries; relationships use their
source, target, and type; rules use condition and effect; random-table rows use
table, label, and result. Existing secret records stay secret. A failure after
any write rolls the entire publication back before the proposal error is saved.

New chat answers, adventure packages, manual payloads, and document chunks do
not create parallel pending drafts. The merge remaps temporary IDs, reconciles
duplicate entities, keeps richer non-empty text, preserves the strongest
relationship confidence, uses the median weight among equally confident
observations instead of biasing it upward, and validates every reference again.
Applied and rejected records remain as compact history.
Fuzzy entity comparison uses a bounded candidate index instead of scanning the
whole draft for every item, and distinct numeric identifiers such as `T-115`
and `T-116` are never merged by edit-distance similarity.

World-audit reports are also review input, not executable instructions. The UI
splits report sections into selectable findings, leaves probable and weak items
unchecked, removes explicit no-finding items, and sends only the master's
selection through `/proposals/extract`. The result merges into the same pending
proposal and still requires normal editing and publication.

Already-published cards use a separate duplicate resolver. Name similarity only
creates a candidate; it never deletes a card. The master chooses the canonical
card and final fields, then confirms a transactional merge through
`POST /worlds/{world_id}/entities/merge`. The operation preserves aliases and
unique text, moves relationships and UI references, records history, and only
then deletes the duplicate.

## Statuses

Proposal status:

- `pending`;
- `applied`;
- `rejected`.

Wiki item status:

- `verified`;
- `proposed`;
- `unknown`;
- `rejected`.

Fine-grained review is available for supported proposal item types. New proposal
item families should be added to the review UI before they become writable.
