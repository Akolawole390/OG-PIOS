from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_KEY = "changeme-generate-with-openssl-rand-hex-32"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://og_pios:og_pios_dev_password@db:5432/og_pios"
    secret_key: str = DEFAULT_SECRET_KEY
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cors_origins: str = "http://localhost:3000"
    environment: str = "development"

    # AI Insights module — provider abstraction (services/ai_providers/). "none" (the default)
    # uses NullProvider, a genuinely functional deterministic responder — the app never requires
    # any of these to be set. Never hard-code a real key here or in .env.example.
    ai_provider: str = "none"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    local_ai_base_url: str | None = None
    local_ai_model: str | None = None

    # Password reset / email verification — services/mail_providers/. "console" (the default,
    # and the only implementation today) never sends a real email; it logs the message and the
    # API response echoes the token/link when ENVIRONMENT=development, so the whole flow is
    # testable with zero mail infrastructure. MUST NOT be used in a real deployment — it writes
    # reset/verification tokens straight into application logs. A real SMTP/API-based provider
    # can be added later behind the same MailProvider interface, mirroring services/ai_providers/.
    reset_token_expire_minutes: int = 30
    email_verification_token_expire_minutes: int = 60 * 24
    frontend_url: str = "http://localhost:3000"
    mail_provider: str = "console"
    resend_api_key: str | None = None
    mail_from_address: str = "OG-PIOS <onboarding@resend.dev>"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _forbid_default_secret_key_in_production(self) -> "Settings":
        # A JWT signed with the placeholder default is forgeable by anyone who has read this
        # public repo — fail loudly at startup rather than silently running insecurely.
        if self.environment == "production" and self.secret_key == DEFAULT_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY is still the default placeholder value while ENVIRONMENT=production. "
                "Generate a real random value (e.g. `openssl rand -hex 32`) and set it before "
                "deploying — see backend/.env.example."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
