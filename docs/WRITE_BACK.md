# Write-Back Pipeline

The write-back pipeline is the safety layer between LLM output and the wiki.

The model is not allowed to directly mutate the world. It can only produce a
structured extraction payload. The core stores that payload as a pending
proposal, validates references, and lets the user apply or reject it.

## Proposal Flow

```text
source text
  -> extraction payload
  -> pending proposal
  -> apply or reject
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
- extracts quest requests as a primary Event entity tagged `quest`;
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
  -> pending proposal
  -> user apply/reject
```

The endpoint returns both the completion and the created proposal. If extraction
fails, the completion is still returned with `wiki_save_error`.

## Apply Or Reject

```http
POST /api/proposals/{proposal_id}/apply
POST /api/proposals/{proposal_id}/apply-selected
POST /api/proposals/{proposal_id}/reject
DELETE /api/proposals/{proposal_id}
```

Applying a proposal writes extracted entities, relationships, and rules into the
wiki. It can also create reviewed random tables and add rows to new or existing
tables. Applying the same proposal twice is blocked. The UI supports applying
all draft items or only the checked items.
Deleting a proposal removes the draft/review record without applying it.

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
