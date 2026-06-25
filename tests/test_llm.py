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

    response = asyncio.run(client.chat(LLMChatRequest(messages=[LLMMessage(role="user", content="Describe the city.")])))

    assert response.model == "story-model"
    assert response.message.role == "assistant"
    assert response.message.content == "Cinder Port glows under ashfall."
    assert response.usage is not None
    assert response.usage.total_tokens == 20


def test_openai_response_parser_rejects_malformed_payload() -> None:
    with pytest.raises(LLMProviderError):
        parse_openai_chat_response({"choices": []}, fallback_model="story-model")


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
    assert "Mirror Gate" in llm_request.messages[0].content
    assert llm_request.messages[1].content == "What do I see?"
