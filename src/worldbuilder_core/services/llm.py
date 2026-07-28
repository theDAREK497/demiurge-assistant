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
                if (
                    response.status_code == 400
                    and "response_format" in payload
                    and "grammar" in response.text.casefold()
                ):
                    payload.pop("response_format", None)
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    )
        except httpx.HTTPError as exc:
            detail = str(exc).strip() or exc.__class__.__name__
            if isinstance(exc, httpx.TimeoutException):
                detail = f"{detail} after {self.timeout_seconds:g} seconds"
            raise LLMProviderError(f"LLM provider request failed: {detail}") from exc

        if response.status_code >= 400:
            raise LLMProviderError(f"LLM provider returned HTTP {response.status_code}: {response.text}")

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMProviderError("LLM provider returned invalid JSON") from exc

        return parse_openai_chat_response(data, fallback_model=model)

    async def embeddings(self, inputs: list[str], *, model: str | None = None) -> tuple[str, list[list[float]]]:
        selected_model = model or self.default_model
        if not inputs:
            return selected_model, []
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=self._headers(),
                    json={"model": selected_model, "input": inputs},
                )
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"Embedding provider request failed: {exc}") from exc
        if response.status_code >= 400:
            raise LLMProviderError(f"Embedding provider returned HTTP {response.status_code}: {response.text}")
        try:
            payload = response.json()
            rows = sorted(payload["data"], key=lambda row: row.get("index", 0))
            vectors = [[float(value) for value in row["embedding"]] for row in rows]
        except (KeyError, TypeError, ValueError) as exc:
            raise LLMProviderError("Embedding provider returned malformed vectors") from exc
        if len(vectors) != len(inputs) or any(not vector for vector in vectors):
            raise LLMProviderError("Embedding provider returned an unexpected vector count")
        dimensions = len(vectors[0])
        if any(len(vector) != dimensions for vector in vectors):
            raise LLMProviderError("Embedding vectors have inconsistent dimensions")
        return str(payload.get("model") or selected_model), vectors

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
        delta = first_choice.get("delta")
        if isinstance(delta, dict):
            message = delta
        elif isinstance(first_choice.get("text"), str):
            message = {"role": "assistant", "content": first_choice["text"]}
        else:
            raise LLMProviderError("LLM provider response choice does not contain a message")

    role = message.get("role", "assistant")
    content = normalize_openai_message_content(message.get("content"))
    if role not in {"system", "user", "assistant"}:
        role = "assistant"
    if not content:
        raise LLMProviderError("LLM provider response message is malformed")

    usage_data = data.get("usage")
    usage = LLMUsage.model_validate(usage_data) if isinstance(usage_data, dict) else None

    return LLMChatResponse(
        model=data.get("model") or fallback_model,
        message=LLMMessage(role=role, content=content),
        finish_reason=first_choice.get("finish_reason"),
        usage=usage,
    )


def normalize_openai_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            text = item.get("text") or item.get("content") or item.get("value")
            if isinstance(text, str):
                parts.append(text)
            elif isinstance(text, dict) and isinstance(text.get("value"), str):
                parts.append(text["value"])
        return "".join(parts)
    return ""
