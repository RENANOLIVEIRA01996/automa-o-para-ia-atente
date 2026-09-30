"""Fallback entre provedores independentes de chat com ferramentas."""

import logging

import httpx
from sqlalchemy.orm import Session

from config import settings
from services.ai.openrouter import AIUnavailable, OpenRouterProvider
from services.ai.provider import AIProvider

log = logging.getLogger("recepia.ai.failover")


class FailoverProvider:
    def __init__(self, primary: AIProvider, secondary: AIProvider):
        self.primary = primary
        self.secondary = secondary
        self.active = primary

    def supports_tools(self) -> bool:
        return self.active.supports_tools()

    def get_model_name(self) -> str:
        return self.active.get_model_name()

    def chat(self, messages: list[dict], *, tenant_id: str | None = None) -> dict:
        return self._call("chat", messages, None, tenant_id)

    def chat_with_tools(
        self, messages: list[dict], tools: list[dict], *, tenant_id: str | None = None
    ) -> dict:
        return self._call("chat_with_tools", messages, tools, tenant_id)

    def _call(
        self, method: str, messages: list[dict], tools: list[dict] | None,
        tenant_id: str | None,
    ) -> dict:
        args = (messages, tools) if tools is not None else (messages,)
        try:
            return getattr(self.active, method)(*args, tenant_id=tenant_id)
        except AIUnavailable:
            if self.active is self.secondary:
                raise
            log.warning("Provedor principal indisponível; usando Groq: tenant=%s", tenant_id)
            self.active = self.secondary
            return getattr(self.active, method)(*args, tenant_id=tenant_id)


def create_provider(db: Session, *, groq_client: httpx.Client | None = None) -> AIProvider:
    primary = OpenRouterProvider(db)
    if not settings.GROQ_API_KEY or not settings.GROQ_FALLBACK_MODEL:
        return primary
    secondary = OpenRouterProvider(
        db,
        client=groq_client,
        api_key=settings.GROQ_API_KEY,
        model=settings.GROQ_FALLBACK_MODEL,
        fallback_model="",
        base_url="https://api.groq.com/openai/v1",
        provider_name="groq",
    )
    return FailoverProvider(primary, secondary)
