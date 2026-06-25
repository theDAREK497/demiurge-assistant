from typing import Any

import httpx

from worldbuilder_core.config import Settings, get_settings
from worldbuilder_core.schemas import LLMChatRequest, LLMChatResponse, LLMMessage, LLMUsage
from worldbuilder_core.services.llm_settings import LLMRuntimeSettings


class LLMProviderError(Exception):
    """Raised when an LLM provider returns an error or an unexpected response."""


class OpenAICompatibleLLMClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        default_model: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def chat(self, request: LLMChatRequest) -> LLMChatResponse:
        model = request.model or self.default_model
        payload = request.model_dump(exclude_none=True)
        payload["model"] = model

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"LLM provider request failed: {exc}") from exc

        if response.status_code >= 400:
            raise LLMProviderError(f"LLM provider returned HTTP {response.status_code}: {response.text}")

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMProviderError("LLM provider returned invalid JSON") from exc

        return parse_openai_chat_response(data, fallback_model=model)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


def build_llm_client(
    settings: Settings | LLMRuntimeSettings | None = None,
    *,
    default_model: str | None = None,
) -> OpenAICompatibleLLMClient:
    settings = settings or get_settings()
    base_url = settings.base_url if isinstance(settings, LLMRuntimeSettings) else settings.llm_base_url
    api_key = settings.api_key if isinstance(settings, LLMRuntimeSettings) else settings.llm_api_key
    model = settings.default_model if isinstance(settings, LLMRuntimeSettings) else settings.llm_model
    timeout_seconds = settings.timeout_seconds if isinstance(settings, LLMRuntimeSettings) else settings.llm_timeout_seconds
    return OpenAICompatibleLLMClient(
        base_url=base_url,
        api_key=api_key,
        default_model=default_model or model,
        timeout_seconds=timeout_seconds,
    )


def parse_openai_chat_response(data: dict[str, Any], *, fallback_model: str) -> LLMChatResponse:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMProviderError("LLM provider response does not contain choices")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise LLMProviderError("LLM provider response choice is malformed")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise LLMProviderError("LLM provider response choice does not contain a message")

    role = message.get("role", "assistant")
    content = message.get("content")
    if role not in {"system", "user", "assistant"} or not isinstance(content, str) or not content:
        raise LLMProviderError("LLM provider response message is malformed")

    usage_data = data.get("usage")
    usage = LLMUsage.model_validate(usage_data) if isinstance(usage_data, dict) else None

    return LLMChatResponse(
        model=data.get("model") or fallback_model,
        message=LLMMessage(role=role, content=content),
        finish_reason=first_choice.get("finish_reason"),
        usage=usage,
    )
