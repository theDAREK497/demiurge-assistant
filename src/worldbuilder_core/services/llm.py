import asyncio
from math import isfinite
from time import monotonic
from typing import Any

import httpx

from worldbuilder_core.config import Settings, get_settings
from worldbuilder_core.schemas import LLMChatRequest, LLMChatResponse, LLMMessage, LLMUsage
from worldbuilder_core.services.llm_settings import LLMRuntimeSettings


class LLMProviderError(Exception):
    """Raised when an LLM provider returns an error or an unexpected response."""


STRUCTURED_OUTPUT_RETRY_SECONDS = 3_600
STRUCTURED_OUTPUT_CACHE_MAX_ENTRIES = 256
TRANSIENT_CHAT_RETRIES = 1
TRANSIENT_CHAT_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
_structured_output_disabled_until: dict[tuple[str, str], float] = {}


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
        model = str(request.model or self.default_model or "").strip()
        if not model:
            raise LLMProviderError("Configure a chat or default model before sending an AI request")
        payload = request.model_dump(exclude_none=True)
        payload["model"] = model
        structured_output_key = (self.base_url, model)
        _prune_structured_output_cache(monotonic())
        structured_output_requested = "response_format" in payload
        if _structured_output_disabled_until.get(structured_output_key, 0) > monotonic():
            payload.pop("response_format", None)
        structured_output_sent = "response_format" in payload

        response = None
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport) as client:
                for attempt in range(TRANSIENT_CHAT_RETRIES + 1):
                    try:
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
                            _structured_output_disabled_until[structured_output_key] = (
                                monotonic() + STRUCTURED_OUTPUT_RETRY_SECONDS
                            )
                            _prune_structured_output_cache(monotonic())
                            payload.pop("response_format", None)
                            response = await client.post(
                                f"{self.base_url}/chat/completions",
                                headers=self._headers(),
                                json=payload,
                            )
                        elif response.status_code < 400 and structured_output_requested and structured_output_sent:
                            _structured_output_disabled_until.pop(structured_output_key, None)
                    except httpx.HTTPError:
                        if attempt >= TRANSIENT_CHAT_RETRIES:
                            raise
                        await asyncio.sleep(0.4 * (attempt + 1))
                        continue
                    if not _is_transient_chat_response(response) or attempt >= TRANSIENT_CHAT_RETRIES:
                        break
                    await asyncio.sleep(0.4 * (attempt + 1))
        except httpx.HTTPError as exc:
            detail = str(exc).strip() or exc.__class__.__name__
            if isinstance(exc, httpx.TimeoutException):
                detail = f"{detail} after {self.timeout_seconds:g} seconds"
            raise LLMProviderError(f"LLM provider request failed: {detail}") from exc

        if response is None:
            raise LLMProviderError("LLM provider request did not return a response")

        if response.status_code >= 400:
            raise LLMProviderError(f"LLM provider returned HTTP {response.status_code}: {response.text}")

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMProviderError("LLM provider returned invalid JSON") from exc

        return parse_openai_chat_response(data, fallback_model=model)

    async def embeddings(self, inputs: list[str], *, model: str | None = None) -> tuple[str, list[list[float]]]:
        selected_model = str(model or self.default_model or "").strip()
        if not selected_model:
            raise LLMProviderError("Configure an embedding model before building the semantic index")
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
        if any(not isfinite(value) for vector in vectors for value in vector):
            raise LLMProviderError("Embedding provider returned non-finite vector values")
        dimensions = len(vectors[0])
        if any(len(vector) != dimensions for vector in vectors):
            raise LLMProviderError("Embedding vectors have inconsistent dimensions")
        return str(payload.get("model") or selected_model), vectors

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


def _is_transient_chat_response(response: httpx.Response) -> bool:
    return response.status_code in TRANSIENT_CHAT_STATUS_CODES or "channel error" in response.text.casefold()


def _prune_structured_output_cache(now: float) -> None:
    for key, expires_at in list(_structured_output_disabled_until.items()):
        if expires_at <= now:
            _structured_output_disabled_until.pop(key, None)
    overflow = len(_structured_output_disabled_until) - STRUCTURED_OUTPUT_CACHE_MAX_ENTRIES
    if overflow > 0:
        for key, _ in sorted(_structured_output_disabled_until.items(), key=lambda item: item[1])[:overflow]:
            _structured_output_disabled_until.pop(key, None)


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
        default_model=str(default_model or model or "").strip(),
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
