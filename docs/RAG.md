# Retrieval and RAG

The first retrieval layer builds a compact, role-aware world context from:

- active world rules;
- matching wiki entities;
- relationships touching those entities.

It is intentionally structured and SQL-based for the MVP. Vector search can be
added later without changing the public goal of the service.

## Context Endpoint

```http
GET /api/worlds/{world_id}/context?role=master&q=city
```

Useful query parameters:

- `role`: `master` or `player`;
- `q`: optional keyword query;
- `max_entities`: default `12`;
- `max_rules`: default `8`;
- `max_relationships`: default `24`.

Player mode filters out:

- secret entities;
- secret rules;
- secret relationships;
- relationships touching secret entities.

## World-Aware Chat

```http
POST /api/worlds/{world_id}/chat
Content-Type: application/json

{
  "role": "master",
  "query": "harbor city",
  "save_to_wiki": true,
  "messages": [
    {
      "role": "user",
      "content": "Describe what the party sees when they arrive."
    }
  ],
  "temperature": 0.7
}
```

The backend builds context first, prepends it as a system message, then calls the
OpenAI-compatible LLM adapter.

If `save_to_wiki` is `true`, the backend then runs a second extraction call over
the assistant response and stores the result as a pending proposal. The proposal
still has to be reviewed and applied before it mutates the wiki.

If the chat call succeeds but extraction fails, the response still includes the
assistant completion and reports the extraction problem in `wiki_save_error`.
