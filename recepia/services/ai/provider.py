"""Contrato mínimo de modelos de chat, sem dependência do SDK do fornecedor."""

from typing import Protocol


class AIProvider(Protocol):
    def chat(self, messages: list[dict], *, tenant_id: str | None = None) -> dict: ...

    def chat_with_tools(
        self, messages: list[dict], tools: list[dict], *, tenant_id: str | None = None
    ) -> dict: ...

    def supports_tools(self) -> bool: ...

    def get_model_name(self) -> str: ...
