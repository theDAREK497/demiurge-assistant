import asyncio
import json

import httpx
import pytest

from worldbuilder_core.models import ViewerRole
from worldbuilder_core.schemas import LLMChatRequest, LLMMessage, WorldContextRead, WorldLLMChatRequest, WorldRead
from worldbuilder_core.services.llm import LLMProviderError, OpenAICompatibleLLMClient, parse_openai_chat_response
from worldbuilder_core.services.world_chat import build_world_llm_request


def test_openai_compatible_client_chat_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://llm.test/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        payload = json.loads(request.content)
        assert payload["model"] == "story-model"
        assert payload["messages"] == [{"role": "user", "content": "Describe the city."}]
        assert payload["reasoning_effort"] == "none"
        return httpx.Response(
            200,
            json={
                "model": "story-model",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "Cinder Port glows under ashfall."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
            },
        )

    client = OpenAICompatibleLLMClient(
        base_url="http://llm.test/v1",
        api_key="test-key",
        default_model="story-model",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )

    response = asyncio.run(
        client.chat(
            LLMChatRequest(
                messages=[LLMMessage(role="user", content="Describe the city.")],
                reasoning_effort="none",
            )
        )
    )

    assert response.model == "story-model"
    assert response.message.role == "assistant"
    assert response.message.content == "Cinder Port glows under ashfall."
    assert response.usage is not None
    assert response.usage.total_tokens == 20


def test_chat_caches_unsupported_structured_output() -> None:
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append(payload)
        if len(calls) == 1:
            assert "response_format" in payload
            return httpx.Response(400, text="Failed to compile grammar")
        assert "response_format" not in payload
        return httpx.Response(
            200,
            json={
                "model": "grammar-cache-model",
                "choices": [{"message": {"role": "assistant", "content": "{}"}}],
            },
        )

    client = OpenAICompatibleLLMClient(
        base_url="http://grammar-cache.test/v1",
        default_model="grammar-cache-model",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )
    request = LLMChatRequest(
        messages=[LLMMessage(role="user", content="Extract.")],
        response_format={"type": "json_schema", "json_schema": {"name": "result", "schema": {}}},
    )

    asyncio.run(client.chat(request))
    asyncio.run(client.chat(request))

    assert len(calls) == 3


def test_openai_compatible_client_parses_embedding_batch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://llm.test/v1/embeddings"
        payload = json.loads(request.content)
        assert payload == {"model": "embed-model", "input": ["one", "two"]}
        return httpx.Response(
            200,
            json={
                "model": "embed-model",
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ],
            },
        )

    client = OpenAICompatibleLLMClient(
        base_url="http://llm.test/v1",
        default_model="embed-model",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )
    model, vectors = asyncio.run(client.embeddings(["one", "two"]))
    assert model == "embed-model"
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]


def test_openai_compatible_client_rejects_non_finite_embeddings() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"model": "embed-model", "data": [{"index": 0, "embedding": [1.0, "NaN"]}]},
        )

    client = OpenAICompatibleLLMClient(
        base_url="http://llm.test/v1",
        default_model="embed-model",
        timeout_seconds=10,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMProviderError, match="non-finite"):
        asyncio.run(client.embeddings(["one"]))


def test_openai_response_parser_rejects_malformed_payload() -> None:
    with pytest.raises(LLMProviderError):
        parse_openai_chat_response({"choices": []}, fallback_model="story-model")


def test_openai_compatible_client_reports_timeout_type_and_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("", request=request)

    client = OpenAICompatibleLLMClient(
        base_url="http://llm.test/v1",
        default_model="story-model",
        timeout_seconds=12,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMProviderError, match="ReadTimeout after 12 seconds"):
        asyncio.run(client.chat(LLMChatRequest(messages=[LLMMessage(role="user", content="Wait.")])))


def test_openai_compatible_client_retries_lm_studio_channel_error() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(500, text="Channel Error")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "Виктор Тимофеев найден."}}]},
        )

    client = OpenAICompatibleLLMClient(
        base_url="http://llm.test/v1",
        default_model="story-model",
        timeout_seconds=12,
        transport=httpx.MockTransport(handler),
    )

    response = asyncio.run(
        client.chat(LLMChatRequest(messages=[LLMMessage(role="user", content="Кто такой Виктор Тимофеев?")]))
    )

    assert calls == 2
    assert response.message.content == "Виктор Тимофеев найден."


def test_openai_response_parser_accepts_multipart_message_content() -> None:
    response = parse_openai_chat_response(
        {
            "model": "story-model",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "Cinder Port "},
                            {"type": "text", "text": {"value": "glows."}},
                        ],
                    },
                    "finish_reason": "stop",
                }
            ],
        },
        fallback_model="fallback-model",
    )

    assert response.model == "story-model"
    assert response.message.content == "Cinder Port glows."


def test_openai_response_parser_accepts_delta_or_text_choice_content() -> None:
    delta_response = parse_openai_chat_response(
        {"choices": [{"delta": {"role": "model", "content": "Delta answer."}}]},
        fallback_model="story-model",
    )
    text_response = parse_openai_chat_response(
        {"choices": [{"text": "Legacy answer."}]},
        fallback_model="story-model",
    )

    assert delta_response.message.role == "assistant"
    assert delta_response.message.content == "Delta answer."
    assert text_response.message.content == "Legacy answer."


def test_world_chat_request_prepends_role_aware_context() -> None:
    context = WorldContextRead(
        world=WorldRead(
            id="world-1",
            name="Glass Marches",
            description=None,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        ),
        role=ViewerRole.player,
        query=None,
        context_text="World: Glass Marches\nRelevant entities:\n- location: Mirror Gate [entity-1] - A public crossing.",
    )
    request = WorldLLMChatRequest(messages=[LLMMessage(role="user", content="What do I see?")])

    llm_request = build_world_llm_request(context, request)

    assert llm_request.messages[0].role == "system"
    assert "viewer role is player" in llm_request.messages[0].content
    assert "in Russian" in llm_request.messages[0].content
    assert "Mirror Gate" in llm_request.messages[0].content
    assert llm_request.messages[1].content == "What do I see?"
    assert llm_request.reasoning_effort == "none"


def test_world_chat_request_bounds_large_context_and_history() -> None:
    context = WorldContextRead(
        world=WorldRead(
            id="world-1",
            name="Bounded World",
            description=None,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        ),
        role=ViewerRole.master,
        query=None,
        context_text="C" * 50_000,
    )
    request = WorldLLMChatRequest(
        messages=[
            LLMMessage(role="user", content=f"message-{index}:" + "x" * 19_000)
            for index in range(4)
        ]
    )

    llm_request = build_world_llm_request(context, request)

    assert len(llm_request.messages[0].content) < 33_000
    assert sum(len(message.content) for message in llm_request.messages[1:]) <= 32_000
    assert llm_request.messages[-1].content.startswith("message-3:")
    assert "[truncated]" in llm_request.messages[-1].content
