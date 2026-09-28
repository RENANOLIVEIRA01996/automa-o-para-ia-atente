"""Chamadas simuladas ao OpenRouter; nenhuma chave ou token real é usado."""

import httpx
import pytest

from models import AIUsage
from services.ai.openrouter import AIRequestError, OpenRouterProvider


def test_fallback_temporario_e_registro_por_tenant(db_session, clinica_fake):
    calls = []

    def handler(request):
        body = __import__("json").loads(request.content)
        calls.append(body["model"])
        if body["model"] == "primary":
            return httpx.Response(429, json={"error": "rate limit"})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "Olá"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenRouterProvider(
        db_session, client, api_key="test-key", model="primary", fallback_model="backup"
    )
    result = provider.chat(
        [{"role": "user", "content": "oi"}], tenant_id=clinica_fake["clinica"].id
    )
    db_session.flush()
    assert result["content"] == "Olá"
    assert calls == ["primary", "primary", "backup"]
    usage = db_session.query(AIUsage).order_by(AIUsage.criado_em).all()
    assert len(usage) == 3
    assert all(u.clinica_id == clinica_fake["clinica"].id for u in usage)
    assert usage[-1].fallback_used and usage[-1].input_tokens == 12


def test_erro_de_argumento_nao_faz_fallback():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(400, json={"error": "invalid"})

    provider = OpenRouterProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_key="test-key",
        model="primary",
        fallback_model="backup",
    )
    with pytest.raises(AIRequestError):
        provider.chat([{"role": "user", "content": "oi"}])
    assert len(calls) == 1


def test_tool_call_envia_schema_ao_backend():
    def handler(request):
        body = __import__("json").loads(request.content)
        assert body["tools"][0]["function"]["name"] == "listServices"
        assert body["parallel_tool_calls"] is False
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "1",
                                    "type": "function",
                                    "function": {
                                        "name": "listServices",
                                        "arguments": "{}",
                                    },
                                }
                            ],
                        }
                    }
                ],
            },
        )

    provider = OpenRouterProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_key="test-key",
        model="primary",
    )
    result = provider.chat_with_tools(
        [{"role": "user", "content": "Quais serviços?"}],
        [
            {
                "type": "function",
                "function": {"name": "listServices", "parameters": {"type": "object"}},
            }
        ],
    )
    assert result["tool_calls"][0]["function"]["name"] == "listServices"
