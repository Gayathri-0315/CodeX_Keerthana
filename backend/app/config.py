from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
    )

    app_env: Literal["dev", "test", "prod"] = "dev"
    demo_mode: bool = True
    ai_mode: Literal["auto", "mock", "live"] = "auto"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    jwt_secret: str = "change-me"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'showup.db').as_posix()}"
    public_url: str = "http://localhost:5173"  # where links in emails and invites point
    ors_api_key: str = ""
    smtp_host: str = ""
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = ""
    waitlist_confirm_minutes: int = 15
    frontend_origin: str = "http://localhost:5173"

    # Timetable gaps are computed inside this daily range (section 5.1).
    timetable_day_start_min: int = 8 * 60
    timetable_day_end_min: int = 21 * 60

    @model_validator(mode="after")
    def _check(self) -> "Settings":
        if self.app_env == "prod" and self.jwt_secret == "change-me":
            raise ValueError("JWT_SECRET must be set to a long random value when APP_ENV=prod.")
        if self.ai_mode == "live" and not self.anthropic_api_key:
            raise ValueError("AI_MODE=live needs ANTHROPIC_API_KEY. Use AI_MODE=auto or mock to run without it.")
        if self.database_url.startswith("sqlite:///./"):
            # Relative SQLite paths resolve against the backend folder, not the shell's cwd.
            self.database_url = f"sqlite:///{(BACKEND_DIR / self.database_url[12:]).as_posix()}"
        return self

    @property
    def use_live_ai(self) -> bool:
        return self.ai_mode == "live" or (self.ai_mode == "auto" and bool(self.anthropic_api_key))

    @property
    def effective_waitlist_minutes(self) -> int:
        return 2 if self.demo_mode else self.waitlist_confirm_minutes


settings = Settings()
