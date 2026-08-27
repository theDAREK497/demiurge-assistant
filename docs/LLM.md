# LLM Adapter

Worldbuilder Core currently supports OpenAI-compatible chat completion
providers. This is enough for LM Studio, OpenAI, OpenRouter-style gateways, and
many local servers that expose `/v1/chat/completions`.

## Environment

```powershell
$env:WORLDBUILDER_LLM_BASE_URL = "http://127.0.0.1:1234/v1"
$env:WORLDBUILDER_LLM_MODEL = "your-loaded-model"
$env:WORLDBUILDER_LLM_API_KEY = ""
$env:WORLDBUILDER_LLM_TIMEOUT_SECONDS = "120"
```

For LM Studio, the API key can usually stay empty.

Environment variables are defaults. If provider settings are saved through the
API or the visual Settings tab, the database values take precedence.

## Persistent Provider Settings

Inspect current config:

```http
GET /api/llm/config
```

Save config:

```http
PUT /api/llm/config
Content-Type: application/json

{
  "base_url": "http://127.0.0.1:1234/v1",
  "default_model": "your-loaded-model",
  "chat_model": "your-loaded-model",
  "extractor_model": "your-loaded-model",
  "summarizer_model": null,
  "critic_model": null,
  "api_key": null,
  "clear_api_key": false,
  "timeout_seconds": 120,
  "max_entities_per_extract": 12
}
```

Model role fields are optional. Empty role fields fall back to `default_model`.
The current pipeline uses:

- `chat_model` for normal chat and world-aware chat;
- `extractor_model` for structured wiki extraction.

`summarizer_model` and `critic_model` are stored now so the future summarizer
and validator pipelines can use the same settings contract.

## Local Reasoning Models

Structured extraction and world-aware chat send `reasoning_effort: "none"`.
This prevents local reasoning models from spending the whole output budget
before emitting user-visible text or JSON. The raw provider chat endpoint keeps
the provider default for technical experiments. Extraction output tokens scale
from 1536 to 4096 with the requested entity count; this avoids truncated JSON
and a second repair generation.

Document extraction treats prose as evidence, not as a list of entities. The
extractor keeps explicit reusable canon facts and ignores document navigation,
front matter, literary decoration, internal monologue, unnamed background
details, and ordinary scene actions. A source segment without canon facts may
produce an empty extraction payload and no draft changes. This is a model-backed
semantic filter, so pending proposals remain the human review boundary.

Extraction accepts strict JSON first. Malformed local-model output falls back to
the MIT-licensed `json-repair` parser and is still validated against the strict
Pydantic extraction schema. Responses that cannot produce a valid schema continue
through the model-repair and retry flow instead of being silently accepted.
Long-running document jobs show elapsed wall time and an ETA derived from average
completed-chunk time; retries and pauses can move the ETA.

## API

Inspect current config:

```http
GET /api/llm/config
```

Send a plain chat completion request:

```http
POST /api/llm/chat
Content-Type: application/json

{
  "messages": [
    {
      "role": "user",
      "content": "Describe a harbor city built on cooled lava."
    }
  ],
  "temperature": 0.7
}
```

This endpoint does not yet inject world rules or wiki context. Retrieval comes
Use `POST /api/worlds/{world_id}/chat` when you want role-aware world context to
be injected before the model call.
