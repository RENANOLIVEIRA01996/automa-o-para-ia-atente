from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://recepia:recepia@localhost:5432/recepia"
    APP_URL: str = "http://localhost:8000"
    PUBLIC_BASE_URL: str = ""
    DOMAIN: str = ""

    # Auth — SEM defaults seguros. Pydantic falha boot se não vier do .env.
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 60 * 24 * 7  # 7 dias
    ADMIN_API_KEY: str
    # Hash PBKDF2 da senha humana do Admin Master; valor em claro nunca vai ao .env.
    ADMIN_PANEL_PASSWORD_HASH: str = ""

    # Evolution API (WhatsApp self-hosted)
    EVOLUTION_API_URL: str = "http://localhost:8080"
    # Render fornece host:porta do serviço privado; em Compose vale EVOLUTION_API_URL.
    EVOLUTION_API_HOSTPORT: str = ""
    EVOLUTION_API_KEY: str = ""
    # URL pública da Recepia (usada pra apontar webhook do Evolution pra cá)
    # Ex: https://recepia.app.br ou https://abc.trycloudflare.com
    PUBLIC_WEBHOOK_URL: str = ""
    # Token estático que o Evolution reenvia em X-Webhook-Token; a Recepia o
    # valida no webhook (F2). Gera com: openssl rand -hex 32
    EVOLUTION_WEBHOOK_SECRET: str = ""

    # Groq (IA classificadora de respostas)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_FALLBACK_MODEL: str = "openai/gpt-oss-20b"

    # Agente comercial; modelo escolhido pelo operador, sem default que possa
    # desaparecer ou deixar de oferecer tool calling.
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = ""
    OPENROUTER_FALLBACK_MODEL: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    AI_PROVIDER: str = "auto"
    SAAS_LIMITS_ENABLED: bool = False
    FILE_UPLOADS_ENABLED: bool = True
    RUN_DB_MIGRATIONS_ON_STARTUP: bool = True

    # Operação
    INTERVALO_CONFIRMACAO_HORAS: int = 24
    INTERVALO_LEMBRETE_HORAS: int = 2
    TIMEZONE: str = "America/Sao_Paulo"

    # Ambiente
    DEBUG: bool = False
    ALLOWED_ORIGINS: str = "https://recepia.app.br,https://app.recepia.app.br"

    # ----------------------------------------------------------------- validators

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalizar_debug(cls, value):
        if isinstance(value, str):
            ambiente = value.strip().lower()
            if ambiente in {"release", "production", "prod"}:
                return False
            if ambiente in {"development", "dev"}:
                return True
        return value

    @field_validator("AI_PROVIDER")
    @classmethod
    def validar_ai_provider(cls, value: str) -> str:
        provider = value.strip().lower()
        if provider not in {"auto", "openrouter", "legacy"}:
            raise ValueError("AI_PROVIDER deve ser auto, openrouter ou legacy")
        return provider

    @field_validator("JWT_SECRET", "ADMIN_API_KEY", "EVOLUTION_API_KEY")
    @classmethod
    def rejeitar_defaults_change_me(cls, v: str, info) -> str:
        if not v:
            return v  # EVOLUTION_API_KEY pode ser vazia em dev
        v_lower = v.lower().strip()
        if v_lower.startswith("change-me") or v_lower in ("changeme", "dev-key", "test", "secret", "password"):
            raise ValueError(
                f"{info.field_name} usa um valor inseguro. "
                "Gere com `openssl rand -hex 32` e configure no .env."
            )
        # JWT precisa ser longo o suficiente pra HS256 (256 bits = 32 bytes hex = 64 chars)
        if info.field_name == "JWT_SECRET" and len(v) < 32:
            raise ValueError(
                f"JWT_SECRET muito curto ({len(v)} chars). Mínimo 32. "
                "Gere com `openssl rand -hex 32`."
            )
        return v

    @model_validator(mode="after")
    def exigir_webhook_secret_em_producao(self):
        """F2: fora de DEBUG o webhook do Evolution NÃO pode ficar sem token.

        Sem esse guard, `_validar_token` aceitaria qualquer requisição e o
        endpoint de mutação (confirmar/cancelar/remarcar) ficaria aberto.
        """
        if not self.DEBUG and not self.EVOLUTION_WEBHOOK_SECRET:
            raise ValueError(
                "EVOLUTION_WEBHOOK_SECRET é obrigatório em produção (DEBUG=false). "
                "Gere com `openssl rand -hex 32` e configure no .env — sem ele o "
                "webhook /api/webhook/evolution ficaria sem autenticação."
            )
        if not self.DEBUG and "*" in {origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")}:
            raise ValueError("ALLOWED_ORIGINS não pode conter * em produção")
        return self

    @property
    def evolution_base_url(self) -> str:
        if self.EVOLUTION_API_HOSTPORT:
            return "http://" + self.EVOLUTION_API_HOSTPORT.strip().removeprefix("http://").rstrip("/")
        return self.EVOLUTION_API_URL.rstrip("/")

    @property
    def openrouter_enabled(self) -> bool:
        return self.AI_PROVIDER != "legacy" and bool(self.OPENROUTER_API_KEY and self.OPENROUTER_MODEL)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Aceita variáveis de infraestrutura e integrações legadas no mesmo .env.
        extra = "ignore"


settings = Settings()


def origens_cors() -> list[str]:
    raw = settings.ALLOWED_ORIGINS or ""
    origens = [o.strip() for o in raw.split(",") if o.strip()]
    if settings.DEBUG:
        origens += ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"]
    return origens
