from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
    )

    # "production" (or "prod") turns on secure cookies, refuses default secrets and blocks dev-only tools.
    app_env: Literal["dev", "test", "production"] = "dev"
    ai_mode: Literal["auto", "mock", "live"] = "auto"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    jwt_secret: str = "change-me"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'showup.db').as_posix()}"
    public_url: str = "http://localhost:5173"  # where links in emails and invites point
    ors_api_key: str = ""
    # Email over HTTPS (item 6). Without a key, emails are printed to the server log as "email skipped".
    email_provider: Literal["", "resend", "brevo"] = ""
    email_api_key: str = ""
    email_from: str = ""
    waitlist_confirm_minutes: int = 15
    frontend_origin: str = "http://localhost:5173"
    static_dir: str = ""  # built frontend to serve from the API (one-service deploys)
    render_external_url: str = ""  # set by Render to the service's public URL

    # Groq (AI helpers: chat safety, search, event Q&A, writing help). Optional; rules are used without it.
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    search_model: str = ""  # optional cheaper model just for search parsing (defaults to GROQ_MODEL)
    seed_dev_password: str = ""  # local sample accounts only (python manage.py seed_dev)

    # Auth hardening
    login_max_failures: int = 5  # failed passwords in a row before the account locks
    login_lock_minutes: int = 15

    # Timetable gaps are computed inside this daily range (section 5.1).
    timetable_day_start_min: int = 8 * 60
    timetable_day_end_min: int = 21 * 60

    @field_validator("app_env", mode="before")
    @classmethod
    def _env_alias(cls, v: str) -> str:
        return "production" if str(v).strip().lower() in ("prod", "production") else str(v).strip().lower()

    @model_validator(mode="after")
    def _check(self) -> "Settings":
        if self.is_production:
            if self.jwt_secret == "change-me" or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be a random value of at least 32 characters when APP_ENV=production.")
            if self.database_url.startswith("sqlite"):
                raise ValueError("APP_ENV=production needs DATABASE_URL pointing at PostgreSQL (see README).")
        if self.ai_mode == "live" and not self.anthropic_api_key:
            raise ValueError("AI_MODE=live needs ANTHROPIC_API_KEY. Use AI_MODE=auto or mock to run without it.")
        if self.email_api_key and not self.email_provider:
            raise ValueError("EMAIL_API_KEY is set but EMAIL_PROVIDER is empty. Use resend or brevo.")
        if self.render_external_url:
            # On Render, links and CORS follow the service's own URL unless set explicitly.
            if "public_url" not in self.model_fields_set:
                self.public_url = self.render_external_url.rstrip("/")
            if "frontend_origin" not in self.model_fields_set:
                self.frontend_origin = self.render_external_url.rstrip("/")
        url = self.database_url
        if url.startswith("postgres://"):  # Render, Neon and Supabase hand out this older scheme
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        if url.startswith("sqlite:///./"):
            # Relative SQLite paths resolve against the backend folder, not the shell's cwd.
            url = f"sqlite:///{(BACKEND_DIR / url[12:]).as_posix()}"
        self.database_url = url
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def use_live_ai(self) -> bool:
        return self.ai_mode == "live" or (self.ai_mode == "auto" and bool(self.anthropic_api_key))


settings = Settings()
