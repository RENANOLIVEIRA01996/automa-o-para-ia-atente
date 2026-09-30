"""OpenRouter com timeout, retries finitos e fallback para erros transitórios."""

import logging
import time

import httpx
from sqlalchemy.orm import Session

from config import settings
from models import AIUsage

log = logging.getLogger("recepia.openrouter")


class AIUnavailable(Exception):
    """Nenhum modelo configurado conseguiu responder."""


class AIRequestError(Exception):
    """Requisição inválida ou resposta malformada; não aciona fallback."""


class _TransientError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class _DailyQuotaError(_TransientError):
    """O limite diário da conta vale para todos os modelos gratuitos."""


class OpenRouterProvider:
    def __init__(
        self,
        db: Session | None = None,
        client: httpx.Client | None = None,
        *,
        api_key: str | None = None,
        model: str | None = None,
        fallback_model: str | None = None,
        base_url: str | None = None,
        provider_name: str = "openrouter",
    ):
        self.db = db
        self.client = client or httpx.Client(timeout=20.0)
        self.api_key = settings.OPENROUTER_API_KEY if api_key is None else api_key
        self.model = settings.OPENROUTER_MODEL if model is None else model
        self.fallback_model = (
            settings.OPENROUTER_FALLBACK_MODEL
            if fallback_model is None
            else fallback_model
        )
        self.base_url = (base_url or settings.OPENROUTER_BASE_URL).rstrip("/")
        self.provider_name = provider_name

    def supports_tools(self) -> bool:
        return True

    def get_model_name(self) -> str:
        return self.model

    def chat(self, messages: list[dict], *, tenant_id: str | None = None) -> dict:
        return self._call(messages, None, tenant_id)

    def chat_with_tools(
        self, messages: list[dict], tools: list[dict], *, tenant_id: str | None = None
    ) -> dict:
        return self._call(messages, tools, tenant_id)

    def _record(
        self,
        tenant_id: str | None,
        model: str,
        latency_ms: int,
        success: bool,
        error_code: str | None,
        fallback_used: bool,
        usage: dict | None = None,
    ) -> None:
        if self.db is None or tenant_id is None:
            return
        usage = usage or {}
        self.db.add(
            AIUsage(
                clinica_id=tenant_id,
                provider=self.provider_name,
                model=model,
                input_tokens=usage.get("prompt_tokens") or 0,
                output_tokens=usage.get("completion_tokens") or 0,
                latency_ms=latency_ms,
                success=success,
                error_code=error_code,
                fallback_used=fallback_used,
            )
        )

    def _request(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> tuple[dict, dict]:
        body: dict = {"model": model, "messages": messages, "stream": False}
        if tools:
            body["tools"] = tools
            body["parallel_tool_calls"] = False
        try:
            response = self.client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
                timeout=20.0,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise _TransientError(type(exc).__name__) from exc
        if response.status_code == 429:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            error = payload.get("error") if isinstance(payload, dict) else {}
            message = str(error.get("message") or "") if isinstance(error, dict) else ""
            if self.provider_name == "openrouter" and "free-models-per-day" in message:
                raise _DailyQuotaError("429")
            raise _TransientError("429")
        if response.status_code >= 500:
            raise _TransientError(str(response.status_code))
        if response.status_code >= 400:
            raise AIRequestError(f"{self.provider_name} HTTP {response.status_code}")
        try:
            payload = response.json()
            message = payload["choices"][0]["message"]
            if not isinstance(message, dict):
                raise TypeError("message inválida")
            return message, payload.get("usage") or {}
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AIRequestError(f"Resposta inválida do {self.provider_name}") from exc

    def _call(
        self, messages: list[dict], tools: list[dict] | None, tenant_id: str | None
    ) -> dict:
        if not self.api_key or not self.model:
            raise AIUnavailable(f"{self.provider_name} não configurado")
        models = [self.model]
        if self.fallback_model and self.fallback_model != self.model:
            models.append(self.fallback_model)
        for index, model in enumerate(models):
            for attempt in range(2):
                started = time.monotonic()
                try:
                    message, usage = self._request(model, messages, tools)
                except _DailyQuotaError as exc:
                    latency = int((time.monotonic() - started) * 1000)
                    self._record(tenant_id, model, latency, False, exc.code, index > 0)
                    log.warning(
                        "Limite diário OpenRouter atingido: model=%s code=%s",
                        model, exc.code,
                    )
                    raise AIUnavailable("Limite diário OpenRouter atingido") from exc
                except _TransientError as exc:
                    latency = int((time.monotonic() - started) * 1000)
                    self._record(tenant_id, model, latency, False, exc.code, index > 0)
                    log.warning(
                        "Falha temporária de IA: provider=%s model=%s code=%s",
                        self.provider_name, model, exc.code,
                    )
                    if attempt == 0:
                        continue
                    break
                except AIRequestError:
                    latency = int((time.monotonic() - started) * 1000)
                    self._record(
                        tenant_id, model, latency, False, "invalid_request", index > 0
                    )
                    raise
                latency = int((time.monotonic() - started) * 1000)
                self._record(tenant_id, model, latency, True, None, index > 0, usage)
                return message
        raise AIUnavailable(f"{self.provider_name} temporariamente indisponível")
