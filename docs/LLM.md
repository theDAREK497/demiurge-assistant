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
